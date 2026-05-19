"""Phase 3d smoke — other.reclassify.

Validates that ambiguous input no longer dead-ends in human_handoff:
  turn 1: pure greeting → reclassify free-chat with suggestions
  turn 2: real intent surfaces → reclassify reroutes to a primary flow
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
            cards = result.get("cards") or []
            print(
                f"flow={result.get('flow')!r}  "
                f"current_node={result.get('current_node')!r}  "
                f"outcome={result.get('outcome')!r}"
            )
            if cards:
                print(f"card kinds (cumulative): {[c['kind'] for c in cards]}")
            return result

        await turn(
            "turn 1 — pure greeting (router → other → free-chat with suggestions)",
            "hi there",
        )
        result = await turn(
            "turn 2 — actual intent (reclassify → primary flow)",
            "I'm choosing a planetary gearbox for a cobot.",
        )

        assert result.get("flow") in {"presales", "guide"}, (
            f"expected reclassify to route to presales/guide, "
            f"got flow={result.get('flow')!r}"
        )
        print(f"\nfinal flow: {result.get('flow')!r}")


if __name__ == "__main__":
    install_async_event_loop_policy()
    asyncio.run(main())
