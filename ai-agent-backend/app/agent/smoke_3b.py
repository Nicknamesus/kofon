"""Phase 3b smoke — postsales end-to-end via the LangGraph.

Drives the full postsales path under a fresh session_uuid:
  turn 1: vague symptom → router → postsales.identify asks for more
  turn 2: SKU + clearer symptom → identify → match_kb → presents problem + gate
  turn 3: 'yes' (button) → fix_gate → outcome_resolved
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

        async def turn(label: str, user_text: str, *, flow: str | None = None) -> dict:
            print(f"\n=== {label} ===")
            print(f"user> {user_text}")
            graph_input: dict = {"messages": [HumanMessage(content=user_text)]}
            if flow:
                graph_input["flow"] = flow
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
            "turn 1 — vague free-form (router → postsales.identify asks)",
            "Something is wrong with my gearbox.",
            flow="postsales",
        )
        await turn(
            "turn 2 — sku + symptom (identify → match_kb presents)",
            "It's a PG090-10-HP. Backlash is way bigger than the datasheet says "
            "after a few hundred hours of cyclic load.",
        )
        result = await turn(
            "turn 3 — yes, that fixed it (fix_gate → outcome_resolved)",
            "yes",
        )

        # With a semantic embedding provider we expect a terminal outcome
        # here. With the `hash` provider (dev default) the top similarity
        # never crosses MATCH_FLOOR — match_kb stays on the 'ambiguous'
        # branch — so we relax the assertion and only check the graph
        # progressed through postsales nodes.
        from app.embeddings import get_provider

        provider_name = get_provider().name
        if provider_name == "hash":
            visited = result.get("current_node", "")
            assert "postsales" in visited, (
                f"expected the postsales subgraph to run, "
                f"got current_node={visited!r}"
            )
            print(
                f"\n(hash provider: graph reached {visited!r}; "
                "swap to bge-m3 / dashscope for semantic-grade match.)"
            )
        else:
            assert result.get("outcome") in {"resolved", "human_handoff"}, (
                f"expected terminal outcome, got {result.get('outcome')!r}"
            )
            print(f"\nfinal outcome: {result.get('outcome')!r}")


if __name__ == "__main__":
    install_async_event_loop_policy()
    asyncio.run(main())
