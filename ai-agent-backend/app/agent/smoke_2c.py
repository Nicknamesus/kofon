"""Phase 2c smoke test — router + pre-sales handing off to guide.find.

Scenario: a free-form "I need motion for cobot joints" lands in the
router → presales takes over → it recommends CaesarPlanetary → user
accepts → guide.find runs immediately with family seeded → returns SKUs.
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

        async def turn(label: str, user_text: str) -> dict:
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
            print(
                f"flow={result.get('flow')!r}  "
                f"current_node={result.get('current_node')!r}  "
                f"outcome={result.get('outcome')!r}"
            )
            if cards:
                print(f"cards (cumulative kinds): {[c['kind'] for c in cards]}")
            return result

        await turn(
            "turn 1 — vague free-form (router → presales asks)",
            "I need motion for a cobot joint",
        )
        await turn(
            "turn 2 — clarify industry/application (presales recommends)",
            "Robotics, specifically cobot joint actuation.",
        )
        await turn(
            "turn 3 — accept recommendation (presales hands off → guide.find runs same turn)",
            "Yes, show me products in that family — I need low backlash around 90 Nm.",
        )
        await turn(
            "turn 4 — pick a SKU (gate → outcome_sell)",
            "PG090-10-HP looks right.",
        )


if __name__ == "__main__":
    install_async_event_loop_policy()
    asyncio.run(main())
