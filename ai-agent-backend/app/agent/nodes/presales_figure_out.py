"""presales.figure_out — slot-fill industry/application, recommend a family,
then hand off to guide.find with the family seeded.

Two phases:

  phase 1: extract industry + application. If either is missing, ask a
           targeted follow-up.
  phase 2: call `recommend_categories`, present the top result, set
           `flow='guide'` and `slots.filters.family` so the next node
           (guide.find) can pick up.

Slot keys (all under slots.presales for namespacing):
    slots.presales.industry
    slots.presales.application
    slots.presales.recommendations_shown   bool
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.agent.llm import get_chat_llm, system_message
from app.agent.state import AgentState
from app.db import SessionLocal
from app.i18n import t
from app.models import ProductType
from app.tools import recommend_categories

SYSTEM_EXTRACT = """You are the Pre-Sales node of a B2B motion-components
chatbot. Extract the user's INDUSTRY and APPLICATION from the
conversation.

Industry examples: Robotics, Packaging, Machine tool, Solar, Aerospace
ground support.
Application examples: Cobot joint actuation, AGV / AMR wheel drive,
Servo indexing table, Rotary axis (B/C), Heliostat / tracker drive,
Antenna positioner.

If either is missing or unclear, set ready=false and put ONE targeted
clarifying question into follow_up_question. Don't ask for both at once.
Never invent values the user didn't actually say.
"""


class _Extraction(BaseModel):
    industry: str | None = None
    application: str | None = None
    ready: bool = Field(description="True if both industry and application are known")
    follow_up_question: str | None = None


async def run(state: AgentState) -> dict:
    slots = state.get("slots") or {}
    presales = dict(slots.get("presales") or {})
    lang = state.get("language")

    # Phase 2: we've shown recommendations; classify the user's reply.
    if presales.get("recommendations_shown"):
        top_family = presales.get("top_family_code")
        verdict = await _classify_recommendation_reply(state.get("messages", []), lang)

        if verdict == "no":
            return {
                "messages": [
                    AIMessage(content=t("pfo_handoff_engineer", lang))
                ],
                "outcome": "human_handoff",
                "cards": [
                    {
                        "kind": "outcome",
                        "payload": {
                            "outcome": "human_handoff",
                            "title": t("title_connecting_engineer", lang),
                            "next_step": "human",
                        },
                    }
                ],
                "current_node": "presales.figure_out.rejected",
            }

        if top_family:
            return {
                "flow": "guide",
                "slots": {
                    "filters": {"family": top_family},
                    "presales": {**presales, "handed_off": True},
                },
                "current_node": "presales.figure_out.handed_off",
            }
        # No top family was set (shouldn't happen given the no-match branch
        # already escalates) — fall through to a soft handoff.
        return {
            "messages": [
                AIMessage(content=t("pfo_connect_engineer", lang))
            ],
            "outcome": "human_handoff",
            "current_node": "presales.figure_out",
        }

    # Phase 1: extract industry + application from the running conversation.
    messages = state.get("messages", [])
    llm = get_chat_llm(temperature=0).with_structured_output(_Extraction)
    extraction: _Extraction = await llm.ainvoke(
        [system_message(SYSTEM_EXTRACT, lang), *messages]
    )

    if not extraction.ready:
        question = (
            extraction.follow_up_question
            or t("pfo_industry_question", lang)
        )
        return {
            "messages": [AIMessage(content=question)],
            "slots": {
                "presales": {
                    **presales,
                    "industry": extraction.industry,
                    "application": extraction.application,
                }
            },
            "current_node": "presales.figure_out",
        }

    # Both slots present → call recommend_categories.
    async with SessionLocal() as session:
        recs = await recommend_categories(
            session,
            industry=extraction.industry or "",
            application=extraction.application or "",
            limit=3,
        )

    if not recs.recommendations:
        # SQL-curated match missed. Before escalating, give the LLM a
        # chance to pick the best-fitting product family from what we
        # actually carry — one cheap call is far better UX (and cheaper)
        # than a forced human handoff when the seed simply doesn't
        # cover the exact (industry, application) pair.
        async with SessionLocal() as session:
            fallback = await _llm_pick_family(
                session,
                industry=extraction.industry or "",
                application=extraction.application or "",
                lang=lang,
            )

        if fallback is not None:
            family_code, family_name, family_desc, rationale, page_url = fallback
            summary = t(
                "pfo_no_curated_fit",
                lang,
                industry=extraction.industry,
                application=extraction.application,
                family_name=family_name,
                rationale=rationale,
            )
            return {
                "messages": [AIMessage(content=summary)],
                "slots": {
                    "presales": {
                        **presales,
                        "industry": extraction.industry,
                        "application": extraction.application,
                        "recommendations_shown": True,
                        "top_family_code": family_code,
                    }
                },
                "cards": [
                    {
                        "kind": "recommendations",
                        "payload": {
                            "industry": extraction.industry,
                            "application": extraction.application,
                            "use_case_matched": False,
                            "title": t("pfo_rec_card_title", lang),
                            "recommendations": [
                                {
                                    "product_type_code": family_code,
                                    "name": family_name,
                                    "family": family_name,
                                    "description": family_desc,
                                    "product_page_url": page_url,
                                    "fit_score": 3,
                                    "rationale": rationale,
                                }
                            ],
                        },
                    },
                    _proceed_gate_card(family_name, lang),
                ],
                "current_node": "presales.figure_out.llm_fallback",
            }

        msg = t(
            "pfo_no_match",
            lang,
            industry=extraction.industry,
            application=extraction.application,
        )
        return {
            "messages": [AIMessage(content=msg)],
            "outcome": "human_handoff",
            "slots": {
                "presales": {
                    **presales,
                    "industry": extraction.industry,
                    "application": extraction.application,
                    "recommendations_shown": True,
                    "top_family_code": None,
                }
            },
            "current_node": "presales.figure_out.no_match",
        }

    top = recs.recommendations[0]
    summary = t(
        "pfo_summary",
        lang,
        industry=recs.industry,
        application=recs.application,
        name=top.name,
        fit_score=top.fit_score,
        rationale=top.rationale,
    )

    rec_payload = recs.model_dump()
    rec_payload["title"] = t("pfo_rec_card_title", lang)
    return {
        "messages": [AIMessage(content=summary)],
        "slots": {
            "presales": {
                **presales,
                "industry": extraction.industry,
                "application": extraction.application,
                "recommendations_shown": True,
                "top_family_code": top.product_type_code,
            }
        },
        "cards": [
            {
                "kind": "recommendations",
                "payload": rec_payload,
            },
            _proceed_gate_card(top.name, lang),
        ],
        "current_node": "presales.figure_out.recommended",
    }


def _proceed_gate_card(family_name: str, lang: str | None) -> dict:
    """Yes/No gate the widget shows after a recommendation."""
    return {
        "kind": "gate",
        "payload": {
            "question": t("pfo_proceed_question", lang, family_name=family_name),
            "yes_label": t("gate_yes_show_products", lang),
            "no_label": t("gate_no_engineer", lang),
        },
    }


_PROCEED_SYSTEM = (
    "Classify the user's last message as a reply to the question "
    "'Want me to pull up specific products in this family?'. "
    "Return 'yes' if they accept, 'no' if they decline. "
    "Treat unclear or off-topic answers as 'yes' (most users who keep "
    "talking want to see options)."
)


class _ProceedVerdict(BaseModel):
    verdict: str = Field(description="'yes' or 'no'")


async def _classify_recommendation_reply(messages: list, lang: str | None = None) -> str:
    """Return 'yes' or 'no' for the user's latest reply."""
    last_human = next(
        (m for m in reversed(messages) if isinstance(m, HumanMessage)), None
    )
    if last_human is None:
        return "yes"

    # Fast path: explicit gate signals coming from gate buttons.
    text = (last_human.content or "").strip().lower()
    if text == "yes":
        return "yes"
    if text == "no":
        return "no"

    llm = get_chat_llm(temperature=0).with_structured_output(_ProceedVerdict)
    result: _ProceedVerdict = await llm.ainvoke(
        [system_message(_PROCEED_SYSTEM, lang), last_human]
    )
    return "no" if result.verdict.strip().lower() == "no" else "yes"


# ---------------- LLM fallback when the seed has no curated match ----------------


class _FamilyPick(BaseModel):
    """LLM's choice of product family for an uncurated (industry, application)."""

    no_match: bool = Field(
        description="True if NO family in the catalog reasonably fits."
    )
    family_code: str | None = Field(
        default=None,
        description="Exact `product_types.code` from the provided list "
        "(e.g. 'caesarplanetary'). Required unless no_match=true.",
    )
    rationale: str | None = Field(
        default=None,
        description="One sentence (≤25 words) explaining the fit, "
        "shown to the user verbatim. Required unless no_match=true.",
    )


_SYSTEM_TEMPLATE = """You are a fallback matcher for the Kofon pre-sales
chatbot. The curated industry × application table didn't return a
match for the user's described need. Pick the closest-fitting product
family from this catalog — or honestly say nothing fits.

Available families:
{families_block}

Rules:
- Only return `family_code` values that appear literally in the list above.
- Set no_match=true if the user's described application is genuinely
  outside what these families do (e.g. fluid power, electronics, software).
- The rationale will be shown verbatim to a B2B engineer — be technical
  and specific, not generic. Don't oversell.
"""


async def _llm_pick_family(
    session,
    *,
    industry: str,
    application: str,
    lang: str | None = None,
) -> tuple[str, str, str, str, str | None] | None:
    """If the LLM picks a real family, return (code, name, description, rationale, product_page_url)."""

    rows = (
        await session.execute(
            select(
                ProductType.code,
                ProductType.name,
                ProductType.family,
                ProductType.description,
                ProductType.product_page_url,
            )
        )
    ).all()
    if not rows:
        return None

    families_block = "\n".join(
        f"- `{code}` — {name} ({family}): {desc}"
        for code, name, family, desc, _url in rows
    )

    llm = get_chat_llm(temperature=0).with_structured_output(_FamilyPick)
    pick: _FamilyPick = await llm.ainvoke(
        [
            system_message(
                _SYSTEM_TEMPLATE.format(families_block=families_block),
                lang,
            ),
            HumanMessage(content=f"Industry: {industry}\nApplication: {application}"),
        ]
    )

    if pick.no_match or not pick.family_code:
        return None

    # Validate the LLM didn't hallucinate a code.
    for code, name, _family, desc, page_url in rows:
        if code == pick.family_code:
            return code, name, desc, pick.rationale or "Closest fit in our current catalog.", page_url

    return None
