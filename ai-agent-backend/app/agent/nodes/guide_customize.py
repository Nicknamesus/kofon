"""guide.customize — configurator sub-flow.

When the user wants a build that doesn't match a stock SKU (or just
wants to explore the spec space), this node walks them through their
chosen family's `spec_schema`:

  1. Resolve / ask for the target family.
  2. Slot-fill the spec_schema keys one at a time. The LLM extracts
     values from the running conversation and asks ONE targeted
     follow-up if anything's still missing.
  3. Once enough keys are set (≥ MIN_FILLED), call build_custom_config
     to surface the closest stock SKU + a rationale, then emit a
     configurator card and a Yes/No gate that reuses `guide.happy_gate`
     for the verdict.

Slot keys (under slots.customize):
  family_code         resolved from slots.filters.family or asked here.
  modules             dict of spec_schema key → value
  phase               'collecting' | 'presented'

MIN_FILLED is intentionally low (2). The configurator is a discovery
tool, not a CAD; over-asking kills the flow.
"""

from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, SystemMessage
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.agent.llm import get_chat_llm
from app.agent.state import AgentState
from app.db import SessionLocal
from app.models import ProductType
from app.tools import build_custom_config

MIN_FILLED = 2

SYSTEM_TEMPLATE = """You are the Guide-Customize node for a B2B
motion-components chatbot. The user is configuring a custom build of
the **{family_name}** family. Extract their chosen module values from
the conversation, mapping to these keys:

{schema_block}

Rules:
- Only return values you can ground in the user's messages.
- If a key isn't yet set but the user has stated others, keep it null.
- Set ready=true once at least {min_filled} keys have values, OR the
  user explicitly says they're done.
- If ready=false, put ONE targeted question in follow_up_question — pick
  a key the user is most likely to know off-hand (frame size, torque,
  ratio before more obscure ones).
"""


class _Extraction(BaseModel):
    modules: dict[str, Any] = Field(default_factory=dict)
    ready: bool
    follow_up_question: str | None = None


async def run(state: AgentState) -> dict:
    slots = state.get("slots") or {}
    customize = dict(slots.get("customize") or {})

    family_code = customize.get("family_code") or (
        slots.get("filters") or {}
    ).get("family")

    async with SessionLocal() as session:
        family = None
        if family_code:
            family = (
                await session.execute(
                    select(ProductType).where(ProductType.code == family_code)
                )
            ).scalar_one_or_none()
        if family is None:
            # No family in scope yet — but if the catalog only has one,
            # picking it for the user is much friendlier than asking.
            all_families = (
                await session.execute(select(ProductType))
            ).scalars().all()
            if len(all_families) == 1:
                family = all_families[0]

    if family is None:
        # Genuinely ambiguous — multiple families and none chosen. Ask.
        return {
            "messages": [
                AIMessage(
                    content=(
                        "Which family do you want to configure? "
                        "(e.g. CaesarPlanetary for planetary gearboxes)"
                    )
                )
            ],
            "slots": {
                "customize": {**customize, "phase": "collecting"},
            },
            "current_node": "guide.customize.no_family",
        }

    schema = family.spec_schema or {}
    schema_block = _format_schema(schema)
    existing_modules = dict(customize.get("modules") or {})

    llm = get_chat_llm(temperature=0).with_structured_output(_Extraction)
    extraction: _Extraction = await llm.ainvoke(
        [
            SystemMessage(
                content=SYSTEM_TEMPLATE.format(
                    family_name=family.name,
                    schema_block=schema_block,
                    min_filled=MIN_FILLED,
                )
            ),
            *state.get("messages", []),
        ]
    )

    # Merge: existing values stand unless the LLM extracted a non-null override.
    merged: dict[str, Any] = {**existing_modules}
    for key, value in (extraction.modules or {}).items():
        if key in schema and value is not None:
            merged[key] = value

    filled = sum(1 for v in merged.values() if v is not None)
    ready = extraction.ready or filled >= MIN_FILLED

    if not ready:
        question = (
            extraction.follow_up_question
            or f"What {next(iter(schema.keys()), 'value')} are you targeting?"
        )
        return {
            "messages": [AIMessage(content=question)],
            "slots": {
                "customize": {
                    **customize,
                    "family_code": family.code,
                    "modules": merged,
                    "phase": "collecting",
                }
            },
            "current_node": "guide.customize.collecting",
        }

    async with SessionLocal() as session:
        config = await build_custom_config(
            session, family_code=family.code, modules=merged
        )

    closest = (
        f"\n\nClosest stock SKU: **{config.closest_stock_sku}** — we could "
        "start from there if you don't need a custom."
        if config.closest_stock_sku
        else ""
    )
    summary = (
        f"Here's the custom **{config.family_name}** build I've put "
        f"together:\n\n_{config.rationale}_{closest}\n\nWant me to send "
        "this to a sales engineer for pricing?"
    )

    return {
        "messages": [AIMessage(content=summary)],
        "cards": [
            {
                "kind": "custom_config",
                "payload": config.model_dump(),
            },
            {
                "kind": "gate",
                "payload": {
                    "question": "Send this to sales for a quote?",
                    "yes_label": "Yes, request a quote",
                    "no_label": "No, talk to an engineer first",
                },
            },
        ],
        "slots": {
            "customize": {
                **customize,
                "family_code": family.code,
                "modules": merged,
                "phase": "presented",
            },
            # Reuse the happy-gate verdict path: 'happy=true' → outcome_sell
            # (RFQ), 'happy=false' → outcome_human. find_phase signals the
            # graph dispatcher that the next user reply should hit the gate.
            "find_phase": "presented",
            "candidates": [
                {
                    "sku": config.closest_stock_sku
                    or f"CUSTOM-{family.code.upper()}",
                    "name": f"Custom {config.family_name}",
                    "family": family.family,
                    "product_type_code": family.code,
                    "specs": merged,
                    "datasheet_url": None,
                    "cad_url": None,
                    "lead_time_days": None,
                    "status": "custom",
                }
            ],
        },
        "current_node": "guide.customize.presented",
    }


def _format_schema(schema: dict) -> str:
    if not schema:
        return "  (no spec keys declared)"
    lines: list[str] = []
    for key, meta in schema.items():
        meta = meta or {}
        label = meta.get("label") or key
        enum = meta.get("enum")
        tail = f" — one of {enum}" if enum else ""
        lines.append(f"  - {key}: {label}{tail}")
    return "\n".join(lines)
