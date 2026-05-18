"""Terminal nodes — write `outcome` to state and emit the terminal card.

Side effects (creating an RFQ, paging a human, sending a datasheet) come
in Phase 4. For now we just record the agent's verdict and surface a
user-facing terminal card.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage

from app.agent.state import AgentState


async def outcome_sell(state: AgentState) -> dict:
    slots = state.get("slots") or {}
    candidates = slots.get("candidates") or []
    # First candidate is the highest-ranked match.
    chosen = candidates[0] if candidates else None

    msg = (
        f"Great — {chosen['sku']} is a solid fit. "
        "I'll have a sales engineer reach out with a quote and lead time."
        if chosen
        else "Great — I'll have a sales engineer reach out with next steps."
    )

    return {
        "messages": [AIMessage(content=msg)],
        "outcome": "sell",
        "current_node": "outcome_sell",
        "cards": [
            {
                "kind": "outcome",
                "payload": {
                    "outcome": "sell",
                    "title": "Connecting you with sales",
                    "chosen_sku": chosen["sku"] if chosen else None,
                    "next_step": "rfq",
                },
            }
        ],
    }


async def outcome_human(state: AgentState) -> dict:
    msg = (
        "Got it — let me hand you off to one of our application engineers. "
        "They'll have more options than my catalog covers."
    )
    return {
        "messages": [AIMessage(content=msg)],
        "outcome": "human_handoff",
        "current_node": "outcome_human",
        "cards": [
            {
                "kind": "outcome",
                "payload": {
                    "outcome": "human_handoff",
                    "title": "Connecting you with an engineer",
                    "next_step": "human",
                },
            }
        ],
    }
