"""postsales.identify — slot-fill SKU + symptom.

Two slots:
  slots.postsales.sku            optional. If the customer doesn't know it,
                                 we proceed with `null` and rely purely on
                                 the symptom text for matching.
  slots.postsales.symptom        required. The free-form problem description.

Once we have a symptom, we hand off to `postsales.match_kb` for the
vector lookup. We don't block on SKU — many tickets land with "I'm not
sure, the label fell off" and the family-agnostic match is still useful.

Slot phase keys:
  slots.postsales.phase = 'collecting' | 'ready'
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field

from app.agent.llm import get_chat_llm, system_message
from app.agent.state import AgentState
from app.i18n import t

SYSTEM = """You are the Post-Sales identify node of a B2B motion-components
chatbot. Extract:
  - SKU (e.g. 'PG090-10-HP') — null if not yet provided.
  - SYMPTOM — a SPECIFIC one-line description of what the unit is doing
    or failing to do (e.g. 'overheating after 2 hours', 'making a grinding
    noise', 'shaft won't rotate'). null if not yet provided.

A SYMPTOM must describe an observable behavior. Generic statements that
only announce the existence of a problem — e.g. 'I have a problem with
my product', 'something is wrong', 'my unit is broken', 'I have an
issue' — are NOT symptoms. Leave symptom=null in those cases.

Set ready=true once you have a specific symptom. SKU is helpful but
optional — don't block on it. If the symptom is missing or only generic,
set ready=false and put ONE targeted question in follow_up_question,
acknowledging the issue and asking what specifically is happening
(e.g. "I'm sorry to hear that — could you tell me what the unit is
doing, or what's not working as expected?").

Never invent a SKU or symptom the user didn't state.
"""


class _Extraction(BaseModel):
    sku: str | None = None
    symptom: str | None = None
    ready: bool = Field(description="True when at least a symptom is known.")
    follow_up_question: str | None = None


# Phrases that announce a problem without describing it. If the extracted
# symptom is *only* one of these (or close), treat it as not-yet-provided
# regardless of what the LLM said. Belt-and-braces against weak extractors.
_VAGUE_SYMPTOM_FRAGMENTS = (
    "i have a problem",
    "i have an issue",
    "i have a issue",
    "have a problem with a product",
    "have an issue with a product",
    "have a problem with my product",
    "have an issue with my product",
    "something is wrong",
    "something's wrong",
    "my unit is broken",
    "my product is broken",
    "it is broken",
    "it's broken",
    "not working",
    "doesn't work",
    "does not work",
    "problem with my product",
    "issue with my product",
)


def _looks_vague(symptom: str | None) -> bool:
    if not symptom:
        return True
    normalized = symptom.strip().lower().rstrip(".!?")
    if len(normalized) < 12:
        return True
    # If the whole symptom is a vague announcement (no extra detail), reject.
    for frag in _VAGUE_SYMPTOM_FRAGMENTS:
        if normalized == frag or normalized.endswith(frag) or normalized.startswith(frag):
            # Allow if there's substantive trailing detail beyond the fragment.
            remainder = normalized.replace(frag, "").strip(" .,-:;")
            if len(remainder) < 8:
                return True
    return False


async def run(state: AgentState) -> dict:
    slots = state.get("slots") or {}
    postsales = dict(slots.get("postsales") or {})
    messages = state.get("messages", [])
    lang = state.get("language")

    # Fast path: we just presented an ambiguous shortlist and the user
    # replied. Treat that reply as the refined symptom directly — the LLM
    # often refuses to extract short noun-phrase labels (e.g. "input
    # shaft oil weep") and would otherwise fall back to the stale symptom.
    if postsales.get("match_phase") == "ambiguous":
        last_human = next(
            (m for m in reversed(messages) if isinstance(m, HumanMessage)),
            None,
        )
        if last_human and (last_human.content or "").strip():
            refined = last_human.content.strip()
            new_postsales = {
                **postsales,
                "sku": postsales.get("sku"),
                "symptom": refined,
                "phase": "ready",
                "match_phase": None,
                "ambiguous_candidates": None,
            }
            return {
                "slots": {"postsales": new_postsales},
                "current_node": "postsales.identify.refined",
            }

    llm = get_chat_llm(temperature=0).with_structured_output(_Extraction)
    extraction: _Extraction = await llm.ainvoke(
        [system_message(SYSTEM, lang), *messages]
    )

    # Carry forward anything we already had; the LLM may only see new info.
    sku = extraction.sku or postsales.get("sku")
    symptom = extraction.symptom or postsales.get("symptom")

    # Code-level guard: even if the LLM extracted a "symptom", reject it
    # if it's just a generic announcement of having a problem. We'd rather
    # ask one extra question than send the user to a wrong KB match.
    if _looks_vague(symptom) and not postsales.get("symptom"):
        symptom = None

    if not symptom:
        question = (
            extraction.follow_up_question
            or t("pi_sorry_what_doing", lang)
        )
        return {
            "messages": [AIMessage(content=question)],
            "slots": {
                "postsales": {
                    **postsales,
                    "sku": sku,
                    "symptom": symptom,
                    "phase": "collecting",
                }
            },
            "current_node": "postsales.identify",
        }

    # If we just refined a previously-ambiguous match, drop the old
    # match_phase so postsales.match_kb runs again with the new symptom.
    new_postsales = {
        **postsales,
        "sku": sku,
        "symptom": symptom,
        "phase": "ready",
    }
    if postsales.get("match_phase") == "ambiguous":
        new_postsales["match_phase"] = None
        new_postsales["ambiguous_candidates"] = None

    return {
        "slots": {"postsales": new_postsales},
        "current_node": "postsales.identify.ready",
    }
