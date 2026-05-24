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

from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.agent.llm import get_chat_llm, system_message
from app.agent.state import AgentState
from app.db import SessionLocal
from app.i18n import t
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
    lang = state.get("language")

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
        # If we already asked and the user replied, try to resolve from text.
        if customize.get("phase") == "collecting":
            family = await _resolve_family_from_conversation(
                state.get("messages", []), lang
            )
            if family is not None:
                schema = family.spec_schema or {}
                return _form_card(
                    family, schema, {},
                    {**customize, "family_code": family.code}, lang,
                )

    if family is None:
        async with SessionLocal() as session:
            examples = (
                await session.execute(
                    select(ProductType.name).order_by(ProductType.code).limit(3)
                )
            ).scalars().all()
        example_block = (
            t("gc_examples_lead_in", lang, examples=", ".join(examples))
            if examples else ""
        )
        return {
            "messages": [
                AIMessage(
                    content=t("gc_which_family", lang, example_block=example_block)
                )
            ],
            "slots": {
                "customize": {**customize, "phase": "collecting"},
            },
            "current_node": "guide.customize.no_family",
        }

    schema = family.spec_schema or {}
    existing_modules = dict(customize.get("modules") or {})

    # --- Fast path: structured form submission from the widget -----------
    submitted = slots.get("custom_modules_submitted")
    if submitted is not None:
        merged = {k: v for k, v in submitted.items() if k in schema and v is not None}
        if sum(1 for v in merged.values() if v is not None) >= 1:
            return await _build_and_present(
                family, {**existing_modules, **merged}, customize, lang,
            )
        # Empty form submitted — re-show the form
        return _form_card(family, schema, existing_modules, customize, lang)

    # --- First visit with a known family: show the structured form ------
    if customize.get("phase") not in ("form_shown", "collecting"):
        return _form_card(family, schema, existing_modules, customize, lang)

    # --- Conversational fallback: user typed text after form was shown ---
    schema_block = _format_schema(schema)
    llm = get_chat_llm(temperature=0).with_structured_output(_Extraction)
    extraction: _Extraction = await llm.ainvoke(
        [
            system_message(
                SYSTEM_TEMPLATE.format(
                    family_name=family.name,
                    schema_block=schema_block,
                    min_filled=MIN_FILLED,
                ),
                lang,
            ),
            *state.get("messages", []),
        ]
    )

    merged: dict[str, Any] = {**existing_modules}
    for key, value in (extraction.modules or {}).items():
        if key in schema and value is not None:
            merged[key] = value

    filled = sum(1 for v in merged.values() if v is not None)
    ready = extraction.ready or filled >= MIN_FILLED

    if not ready:
        question = (
            extraction.follow_up_question
            or t("gc_what_target", lang, key=next(iter(schema.keys()), "value"))
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

    return await _build_and_present(family, merged, customize, lang)


def _form_card(
    family, schema: dict, existing_modules: dict, customize: dict, lang: str | None
) -> dict:
    """Emit a ``custom_config_form`` card so the widget renders a structured form."""
    fields: list[dict] = []
    for key, meta in schema.items():
        meta = meta or {}
        field: dict[str, Any] = {
            "key": key,
            "label": meta.get("label") or key,
            "type": meta.get("type", "string"),
        }
        if "enum" in meta:
            field["enum"] = meta["enum"]
        if key in existing_modules and existing_modules[key] is not None:
            field["value"] = existing_modules[key]
        fields.append(field)

    return {
        "messages": [
            AIMessage(content=t("gc_form_intro", lang, family_name=family.name))
        ],
        "cards": [
            {
                "kind": "custom_config_form",
                "payload": {
                    "family_code": family.code,
                    "family_name": family.name,
                    "fields": fields,
                },
            }
        ],
        "slots": {
            "customize": {
                **customize,
                "family_code": family.code,
                "phase": "form_shown",
            },
            "custom_modules_submitted": None,
        },
        "current_node": "guide.customize.form_shown",
    }


async def _build_and_present(
    family, merged: dict, customize: dict, lang: str | None
) -> dict:
    """Call ``build_custom_config`` and emit the result + quote gate."""
    async with SessionLocal() as session:
        config = await build_custom_config(
            session, family_code=family.code, modules=merged
        )

    closest = (
        t("gc_closest_suffix", lang, sku=config.closest_stock_sku)
        if config.closest_stock_sku
        else ""
    )
    summary = t(
        "gc_summary",
        lang,
        family_name=config.family_name,
        rationale=config.rationale,
        closest=closest,
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
                    "question": t("gc_quote_question", lang),
                    "yes_label": t("gate_yes_request_quote", lang),
                    "no_label": t("gate_no_engineer_first", lang),
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
            "custom_modules_submitted": None,
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


_FAMILY_PICK_SYSTEM = """Pick the product family the user is asking about.

Available families:
{families_block}

Return the exact `code` value from the list above. If no family
clearly matches, set code to null.
"""


class _FamilyChoice(BaseModel):
    code: str | None = Field(description="Exact family code, or null if unclear.")


async def _resolve_family_from_conversation(
    messages: list, lang: str | None
) -> ProductType | None:
    """Try to match the user's latest message to a product family."""
    last_human = next(
        (m for m in reversed(messages) if isinstance(m, HumanMessage)), None
    )
    if last_human is None:
        return None
    text = (last_human.content or "").strip().lower()
    if not text:
        return None

    async with SessionLocal() as session:
        all_families = (await session.execute(select(ProductType))).scalars().all()

    if not all_families:
        return None

    # Fast path: exact code or case-insensitive name match.
    for f in all_families:
        if text == f.code or text == f.name.lower():
            return f
    for f in all_families:
        if f.code in text or f.name.lower() in text:
            return f

    # LLM fallback: ask the model to pick from the catalog.
    families_block = "\n".join(
        f"- `{f.code}` — {f.name} ({f.family})" for f in all_families
    )
    llm = get_chat_llm(temperature=0).with_structured_output(_FamilyChoice)
    pick: _FamilyChoice = await llm.ainvoke(
        [
            system_message(
                _FAMILY_PICK_SYSTEM.format(families_block=families_block), lang
            ),
            last_human,
        ]
    )
    if pick.code:
        for f in all_families:
            if f.code == pick.code:
                return f
    return None
