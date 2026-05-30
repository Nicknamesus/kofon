"""guide.find — pre-curated product lookup flow.

Single node, three phases driven by current state:

  phase 1 (no candidates yet)
    LLM extracts SearchProductsFilters from the conversation. If it has
    enough to search, we run search_products and present results +
    "are these good?" question. If not, we ask a targeted follow-up.

  phase 2 (candidates exist, user hasn't answered yet)
    The next user reply lands here; we let `guide.happy_gate` interpret
    it. This node is bypassed by the graph's conditional edge in that
    case — see graph.py.

Slot keys this node owns:
    slots.filters              dict of SearchProductsFilters
    slots.candidates           list[dict] of ProductOut
    slots.find_phase           'asking' | 'presented'
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.llm import get_chat_llm, system_message
from app.agent.state import AgentState
from app.db import SessionLocal
from app.i18n import t
from app.models import ProductType, has_active_products
from app.schemas.tools import ProductOut, SearchProductsFilters
from app.tools import search_products

SYSTEM_TEMPLATE = """You are the Guide-Find node of a B2B motion-components chatbot.
Your job is to translate the user's free-form description of what they
need into a structured SearchProductsFilters object that the search tool
can consume.

Besides the structured filters, capture any literal model code, SKU, or
product-name fragment the user typed into the top-level `query` field,
VERBATIM (e.g. 'RF080', 'KGR070', 'R080-2-20'). This is matched directly
against the catalog's SKUs and names, so it finds the right product even
when you can't map the code to a family code below. Do NOT invent a code
the user didn't type, and do NOT guess a `family` from a code you don't
recognise — leave `family` unset and let `query` do the work.

Available filters (all optional):
  family                — product family code (one of the catalog codes below)
  frame_size_mm         — number (catalog-specific; common values vary by family)
  ratio                 — reduction ratio, the N in 'N:1' (e.g. '20:1' -> 20)
  stages                — number of stages (e.g. '2 stage' / '2-stage' -> 2)
  min_nominal_torque_nm — number
  max_backlash_arcmin   — number
  variant               — family-specific variant tag (e.g. 'HP' / 'HT' on caesarplanetary)

Product family codes available in the catalog (use one of these literally
when you set `family`):
{families_block}

Set ready_to_search=true when there's enough signal to return a useful
shortlist — that includes any time `query` holds a model code/SKU, or when
1-2 filters meaningfully narrow. If you need more info, set
ready_to_search=false and put ONE clarifying question into
follow_up_question. Never make up facts the user didn't say.
"""


async def _build_system_prompt(session: AsyncSession) -> str:
    """Format SYSTEM_TEMPLATE with the live catalog.

    Loading from DB on every call keeps the LLM accurate as new
    families ship — no stale hardcoded list to maintain. The query is
    tiny (~30 rows of (code, name)) and the result goes into one
    SystemMessage that the LLM caches across turns anyway."""
    rows = (
        await session.execute(
            select(ProductType.code, ProductType.name, ProductType.family)
            .where(ProductType.id.in_(has_active_products()))
            .order_by(ProductType.code)
        )
    ).all()
    if not rows:
        families_block = "  (catalog is empty — ask the user what they need)"
    else:
        families_block = "\n".join(
            f"  {code:33s} — {name} [{family}]" for code, name, family in rows
        )
    return SYSTEM_TEMPLATE.format(families_block=families_block)


class _Extraction(BaseModel):
    filters: SearchProductsFilters = Field(default_factory=SearchProductsFilters)
    query: str | None = Field(
        default=None,
        description="Literal model code / SKU / name fragment the user typed.",
    )
    ready_to_search: bool
    follow_up_question: str | None = None


async def run(state: AgentState) -> dict:
    messages = state.get("messages", [])
    slots = state.get("slots") or {}
    existing_filters = slots.get("filters") or {}
    existing_query = slots.get("query") or ""
    lang = state.get("language")

    # Build the SYSTEM prompt with the current catalog so the LLM knows
    # which family codes are valid. Short-lived session — released before
    # the LLM call so we don't hold a pool connection during the slow hop.
    async with SessionLocal() as session:
        prompt_content = await _build_system_prompt(session)

    # Extract filters from the full conversation so the LLM sees prior turns.
    llm = get_chat_llm().with_structured_output(_Extraction)
    extraction: _Extraction = await llm.ainvoke(
        [system_message(prompt_content, lang), *messages]
    )

    # Merge: existing filters (e.g. seeded by presales) win unless the LLM
    # extracted a non-null override for that key.
    merged: dict[str, Any] = {**existing_filters}
    for key, value in extraction.filters.model_dump(exclude_none=True).items():
        merged[key] = value
    merged_filters = SearchProductsFilters(**merged)

    # The literal model code/SKU persists across turns just like filters:
    # the user may type "RF080" then "2 stage 20:1" in separate messages.
    # Latest non-empty extraction wins.
    query = (extraction.query or "").strip() or existing_query

    # Re-evaluate readiness with merged context — if presales seeded a family,
    # we may already have enough to search even if this turn's extraction
    # alone wouldn't. A bare model code is also enough to search.
    ready = extraction.ready_to_search or any(merged.values()) or bool(query)

    if not ready:
        question = (
            extraction.follow_up_question
            or t("gf_clarify", lang)
        )
        return {
            "messages": [AIMessage(content=question)],
            "slots": {
                "filters": merged,
                "query": query,
                "find_phase": "asking",
            },
            "current_node": "guide.find",
        }

    # Ready: run the search. Pass the literal model code/SKU as `query` so
    # the tool's SKU/name match can find the exact product even when the
    # code doesn't map to a family code (e.g. "RF080" -> r_series SKUs).
    async with SessionLocal() as session:
        results: list[ProductOut] = await search_products(
            session, query=query, filters=merged_filters, limit=3
        )

        # Relaxation ladder for over-constrained searches — drop the
        # strictest signals before dead-ending, since a shortlist beats
        # "no results" every time.
        #   1. Keep the literal model code, drop the structured filters. The
        #      LLM often reads "KGR070" as family + frame_size_mm and stacks
        #      filters that, combined, match nothing.
        if not results and query and any(merged.values()):
            results = await search_products(session, query=query, limit=3)
        #   2. Fall back to the family alone (e.g. frame size stored as the
        #      string "KGR070" rather than the numeric frame_size_mm).
        if not results and merged.get("family") and len(merged) > 1:
            results = await search_products(
                session,
                filters=SearchProductsFilters(family=merged["family"]),
                limit=3,
            )

    if not results:
        msg = t("gf_no_results", lang)
        return {
            "messages": [AIMessage(content=msg)],
            "slots": {
                "filters": merged,
                "query": query,
                "find_phase": "asking",
            },
            "current_node": "guide.find",
        }

    summary = _format_results(results, lang)
    return {
        "messages": [AIMessage(content=summary)],
        "slots": {
            "filters": merged,
            "query": query,
            "candidates": [r.model_dump() for r in results],
            "find_phase": "presented",
        },
        "cards": [
            {
                "kind": "product_results",
                "payload": {
                    "results": [r.model_dump() for r in results],
                    "title": t("gf_card_title", lang),
                },
            },
            {
                "kind": "gate",
                "payload": {
                    "question": t("gf_do_any_fit", lang),
                    "yes_label": t("gate_yes_works", lang),
                    "no_label": t("gate_no_fit", lang),
                    "dismiss_label": t("gate_just_browsing", lang),
                },
            },
        ],
        "current_node": "guide.find.presented",
    }


def _format_results(results: list[ProductOut], lang: str | None) -> str:
    lines = [t("gf_results_header", lang)]
    for r in results:
        torque = r.specs.get("nominal_torque_nm")
        ratio = r.specs.get("ratio")
        backlash = r.specs.get("backlash_arcmin")
        bits: list[str] = []
        if ratio is not None:
            bits.append(f"{ratio}:1 ratio")
        if torque is not None:
            bits.append(f"{torque} Nm nominal")
        if backlash is not None:
            bits.append(f"{backlash} arcmin backlash")
        detail = ", ".join(bits) if bits else r.family or ""
        link = f"\n    {r.datasheet_url}" if r.datasheet_url else ""
        lines.append(f"  - {r.sku} ({r.name}) — {detail}{link}")
    lines.append("\n" + t("gf_do_any_fit", lang))
    return "\n".join(lines)


def should_present_results(state: AgentState) -> bool:
    """Used by the graph to decide if guide.find needs to run.

    True when there are no candidates yet, OR the user's last reply isn't
    a clear yes/no on the existing candidates (would be handled by the
    gate). Phase 2b keeps this simple — if candidates exist, route to
    the gate.
    """
    slots = state.get("slots") or {}
    return "candidates" not in slots
