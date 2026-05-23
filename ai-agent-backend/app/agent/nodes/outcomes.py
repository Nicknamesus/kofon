"""Terminal nodes — write `outcome` to state, fire side effects, emit
the terminal card.

Side effects (CRM lead/ticket, division email) live in
`app.sideeffects.handlers`. Outcome nodes call them but don't know
about the provider — swap Zoho → Salesforce by changing
`CRM_PROVIDER`, no node changes needed.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage

from app.agent.state import AgentState
from app.i18n import t
from app.sideeffects import (
    handle_human_handoff,
    handle_resolved,
    handle_sell,
)


def _merge_slots(base: dict, diff: dict) -> dict:
    """Shallow-merge a slots diff returned by a side-effects handler."""
    out = dict(base or {})
    for key, value in (diff.get("slots") or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = {**out[key], **value}
        else:
            out[key] = value
    return out


async def outcome_sell(state: AgentState) -> dict:
    slots = state.get("slots") or {}
    candidates = slots.get("candidates") or []
    chosen = candidates[0] if candidates else None
    lang = state.get("language")

    diff = await handle_sell(state)
    sideeffects = (diff.get("slots") or {}).get("sideeffects") or {}

    msg = (
        t("os_sell_with_sku", lang, sku=chosen["sku"])
        if chosen
        else t("os_sell_generic", lang)
    )

    return {
        "messages": [AIMessage(content=msg)],
        "outcome": "sell",
        "current_node": "outcome_sell",
        "slots": _merge_slots({}, diff),
        "cards": [
            {
                "kind": "outcome",
                "payload": {
                    "outcome": "sell",
                    "title": t("title_connecting_sales", lang),
                    "chosen_sku": chosen["sku"] if chosen else None,
                    "next_step": "rfq",
                    "rfq_id": sideeffects.get("rfq_id"),
                    "division_code": sideeffects.get("division_code"),
                },
            }
        ],
    }


async def outcome_human(state: AgentState) -> dict:
    slots = state.get("slots") or {}
    postsales = slots.get("postsales") or {}
    lang = state.get("language")
    # Pick a reason / priority based on what brought us here.
    if postsales.get("low_confidence_escalation"):
        reason = "low_confidence_kb_match"
        priority = "normal"
    elif postsales.get("fixed") is False:
        reason = "fix_didnt_work"
        priority = "high"
    elif slots.get("happy") is False:
        reason = "user_rejected_recommendations"
        priority = "normal"
    else:
        reason = "user_requested"
        priority = "normal"

    diff = await handle_human_handoff(state, reason=reason, priority=priority)
    sideeffects = (diff.get("slots") or {}).get("sideeffects") or {}

    msg = t("oh_engineer_msg", lang)
    return {
        "messages": [AIMessage(content=msg)],
        "outcome": "human_handoff",
        "current_node": "outcome_human",
        "slots": _merge_slots({}, diff),
        "cards": [
            {
                "kind": "outcome",
                "payload": {
                    "outcome": "human_handoff",
                    "title": t("title_connecting_engineer", lang),
                    "next_step": "human",
                    "ticket_id": sideeffects.get("ticket_id"),
                    "division_code": sideeffects.get("division_code"),
                },
            }
        ],
    }


async def outcome_resolved(state: AgentState) -> dict:
    """Post-sales happy path — the curated fix worked.

    Surfaces a short closer and an optional feedback prompt the widget
    can wire to a thumbs-up/down later.
    """
    slots = state.get("slots") or {}
    postsales = slots.get("postsales") or {}
    solution = postsales.get("candidate_solution") or {}
    label = postsales.get("candidate_problem_label")
    lang = state.get("language")

    await handle_resolved(state)

    msg = (
        t("ores_glad_worked_label", lang, label=label)
        if label
        else t("ores_glad_worked", lang)
    )

    return {
        "messages": [AIMessage(content=msg)],
        "outcome": "resolved",
        "current_node": "outcome_resolved",
        "cards": [
            {
                "kind": "outcome",
                "payload": {
                    "outcome": "resolved",
                    "title": t("title_issue_resolved", lang),
                    "sop_url": solution.get("sop_url"),
                    "next_step": "feedback",
                },
            }
        ],
    }
