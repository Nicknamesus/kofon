"""Phase 2b smoke test — drives a full Guide-Find conversation in Python.

Scenario: user asks for a low-backlash planetary gearbox → agent extracts
filters → agent calls search_products → presents 3 SKUs → user says yes
→ outcome_sell terminal fires.

Usage:
    python -m app.agent.setup_checkpointer    # once
    python -m app.agent.smoke_2b
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

from langchain_core.messages import HumanMessage

from app.agent.checkpointer import make_checkpointer
from app.agent.graph import build_graph
from app.runtime import install_async_event_loop_policy


async def main() -> None:
    session_uuid = uuid4()
    config = {"configurable": {"thread_id": str(session_uuid)}}

    async with make_checkpointer() as cp:
        graph = build_graph(checkpointer=cp)

        async def turn(label: str, user_text: str) -> None:
            print(f"\n=== {label} ===")
            print(f"user> {user_text}")
            result = await graph.ainvoke(
                {"messages": [HumanMessage(content=user_text)]},
                config=config,
            )
            ai_msgs = [m for m in result["messages"] if m.type == "ai"]
            if ai_msgs:
                print(f"bot> {ai_msgs[-1].content}")
            slots = result.get("slots") or {}
            cards = result.get("cards") or []
            outcome = result.get("outcome")
            if cards:
                kinds = [c["kind"] for c in cards]
                print(f"cards emitted (cumulative): {kinds}")
            print(
                f"current_node={result.get('current_node')!r}  "
                f"find_phase={slots.get('find_phase')!r}  "
                f"happy={slots.get('happy')!r}  "
                f"outcome={outcome!r}"
            )

        await turn(
            "turn 1 — vague intent (should ask follow-up)",
            "I'm looking for a gearbox",
        )
        await turn(
            "turn 2 — specifics (should trigger search)",
            "Planetary, low backlash, 90mm frame, around 80 Nm.",
        )
        await turn(
            "turn 3 — accept first candidate (should hit outcome_sell)",
            "Yes, the PG090-10-HP looks perfect.",
        )


if __name__ == "__main__":
    install_async_event_loop_policy()
    asyncio.run(main())
