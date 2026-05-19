"""Phase 3c smoke — guide.customize sub-flow.

Frontend opts in via `subflow=customize` on the message payload; we
emulate that here by seeding `slots.customize.active=true` and
`slots.filters.family=caesarplanetary`.

  turn 1: vague — customize asks for more specs
  turn 2: 90mm frame, ratio 10:1 — should present config + gate
  turn 3: 'yes' → outcome_sell (custom RFQ path)
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

        async def turn(label: str, user_text: str, *, extra: dict | None = None) -> dict:
            print(f"\n=== {label} ===")
            print(f"user> {user_text}")
            graph_input: dict = {"messages": [HumanMessage(content=user_text)]}
            if extra:
                graph_input.update(extra)
            result = await graph.ainvoke(graph_input, config=config)
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
            "turn 1 — customize a planetary, no specs yet",
            "I want to spec a custom planetary gearbox.",
            extra={
                "flow": "guide",
                "slots": {
                    "customize": {"active": True},
                    "filters": {"family": "caesarplanetary"},
                },
            },
        )
        await turn(
            "turn 2 — supply specs",
            "Frame size 90mm, ratio 10:1, low backlash variant.",
        )
        result = await turn(
            "turn 3 — accept and send to sales",
            "yes",
        )
        assert result.get("outcome") in {"sell", "human_handoff"}, (
            f"expected terminal, got {result.get('outcome')!r}"
        )
        print(f"\nfinal outcome: {result.get('outcome')!r}")


if __name__ == "__main__":
    install_async_event_loop_policy()
    asyncio.run(main())
