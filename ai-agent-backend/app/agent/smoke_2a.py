"""Phase 2a smoke test.

Runs two turns against the echo graph under the same `session_uuid` and
prints what comes back. The second turn proves the checkpointer
restored the first turn's state — if it had not, the message log would
not include the first exchange.

Usage:
    python -m app.agent.setup_checkpointer    # once
    python -m app.agent.smoke_2a
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

from langchain_core.messages import HumanMessage

from app.agent.checkpointer import make_checkpointer
from app.agent.graph import build_echo_graph
from app.runtime import install_async_event_loop_policy


async def main() -> None:
    session_uuid = uuid4()
    config = {"configurable": {"thread_id": str(session_uuid)}}

    async with make_checkpointer() as cp:
        graph = build_echo_graph(checkpointer=cp)

        print(f"\n=== turn 1 (session {session_uuid}) ===")
        result = await graph.ainvoke(
            {
                "session_uuid": session_uuid,
                "messages": [HumanMessage(content="hello from phase 2a")],
                "slots": {},
            },
            config=config,
        )
        for m in result["messages"]:
            print(f"  [{m.type}] {m.content}")

        print(f"\n=== turn 2 (same session — should see turn 1 in history) ===")
        result = await graph.ainvoke(
            {"messages": [HumanMessage(content="and again")]},
            config=config,
        )
        for m in result["messages"]:
            print(f"  [{m.type}] {m.content}")

        print(f"\n=== persisted state ===")
        snapshot = await graph.aget_state(config)
        print(f"  current_node: {snapshot.values.get('current_node')}")
        print(f"  message count: {len(snapshot.values.get('messages', []))}")


if __name__ == "__main__":
    install_async_event_loop_policy()
    asyncio.run(main())
