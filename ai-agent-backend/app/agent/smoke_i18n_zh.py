"""Run the Phase-4 scenarios with language='ZH' and dump every bot
message + card label that streams back, so we can eyeball the
localization. Mirrors smoke_4.py's structure but doesn't assert.

Run from `ai-agent-backend/`:
    python -m app.agent.smoke_i18n_zh
"""

from __future__ import annotations

import asyncio
import json
from uuid import uuid4

from langchain_core.messages import AIMessage, HumanMessage

from app import persistence
from app.agent.checkpointer import make_checkpointer
from app.agent.graph import build_graph
from app.runtime import install_async_event_loop_policy


LANG = "ZH"


async def _drive_turn(
    graph,
    *,
    session_uuid,
    conversation_id: int,
    text: str | None = None,
    flow: str | None = None,
    gate_choice: str | None = None,
    picked_problem_id: int | None = None,
) -> dict:
    config = {"configurable": {"thread_id": str(session_uuid)}}
    graph_input: dict = {
        "session_uuid": session_uuid,
        "conversation_id": conversation_id,
        "language": LANG,
    }
    user_text = text or gate_choice or ""
    if user_text:
        graph_input["messages"] = [HumanMessage(content=user_text)]
    if flow:
        graph_input["flow"] = flow
    if picked_problem_id:
        graph_input["slots"] = {"picked_problem_id": picked_problem_id}

    await persistence.append_user_message(
        conversation_id,
        text=text,
        gate_choice=gate_choice,
        flow=flow,
        subflow=None,
        picked_problem_id=picked_problem_id,
    )

    print(f"\n  >> user: {user_text!r}")

    last_state: dict | None = None
    async for chunk in graph.astream(
        graph_input, config=config, stream_mode="updates"
    ):
        for node_name, update in chunk.items():
            if not isinstance(update, dict):
                continue
            last_state = update
            for msg in update.get("messages") or []:
                if isinstance(msg, AIMessage) and msg.content:
                    print(f"  << [{node_name}] bot: {msg.content}")
                    await persistence.append_bot_text(
                        conversation_id, msg.content, node=node_name
                    )
            for card in update.get("cards") or []:
                kind = card.get("kind")
                payload = card.get("payload") or {}
                shown = {
                    k: v for k, v in payload.items()
                    if k in {"title", "question", "yes_label", "no_label",
                             "outcome", "next_step"}
                }
                # Also peek at problem.label / solution.summary for the
                # match cards.
                if "problem" in payload:
                    shown["problem.label"] = (payload["problem"] or {}).get("label")
                if "solution" in payload:
                    shown["solution.summary"] = (payload["solution"] or {}).get("summary")
                print(f"  << [{node_name}] card<{kind}>: {json.dumps(shown, ensure_ascii=False)}")
                await persistence.append_bot_card(
                    conversation_id, card, node=node_name
                )
            if update.get("outcome"):
                print(f"  << [{node_name}] OUTCOME: {update['outcome']}")

    await persistence.update_conversation_state(
        conversation_id,
        current_node=(last_state or {}).get("current_node"),
        state_snapshot=last_state,
    )

    snapshot = await graph.aget_state(config)
    return snapshot.values if snapshot else {}


async def _scenario_guide_sell(graph) -> None:
    sid = uuid4()
    cid = await persistence.upsert_conversation(sid, flow="guide", language=LANG)
    print(f"\n=== Scenario A: guide → sell  (conv #{cid}, lang={LANG})")
    await _drive_turn(
        graph, session_uuid=sid, conversation_id=cid,
        text="我需要一台行星减速机,机座 90,低背隙。",
        flow="guide",
    )
    await _drive_turn(
        graph, session_uuid=sid, conversation_id=cid,
        gate_choice="yes",
    )


async def _scenario_guide_human(graph) -> None:
    sid = uuid4()
    cid = await persistence.upsert_conversation(sid, flow="guide", language=LANG)
    print(f"\n=== Scenario B: guide → human handoff  (conv #{cid}, lang={LANG})")
    await _drive_turn(
        graph, session_uuid=sid, conversation_id=cid,
        text="我需要一台行星减速机,机座 90,低背隙。",
        flow="guide",
    )
    await _drive_turn(
        graph, session_uuid=sid, conversation_id=cid,
        gate_choice="no",
    )


async def _scenario_postsales(graph) -> None:
    sid = uuid4()
    cid = await persistence.upsert_conversation(sid, flow="postsales", language=LANG)
    print(f"\n=== Scenario C: postsales  (conv #{cid}, lang={LANG})")
    await _drive_turn(
        graph, session_uuid=sid, conversation_id=cid,
        text="我的 PG090 减速机背隙变大了。",
        flow="postsales",
    )
    await _drive_turn(
        graph, session_uuid=sid, conversation_id=cid,
        text="使用几个月后背隙明显变大。",
    )
    await _drive_turn(
        graph, session_uuid=sid, conversation_id=cid,
        gate_choice="no",
    )


async def _scenario_presales(graph) -> None:
    sid = uuid4()
    cid = await persistence.upsert_conversation(sid, flow="presales", language=LANG)
    print(f"\n=== Scenario D: presales  (conv #{cid}, lang={LANG})")
    await _drive_turn(
        graph, session_uuid=sid, conversation_id=cid,
        text="我在机器人行业,需要用于协作机器人关节驱动。",
        flow="presales",
    )
    await _drive_turn(
        graph, session_uuid=sid, conversation_id=cid,
        gate_choice="yes",
    )


async def _scenario_other(graph) -> None:
    sid = uuid4()
    cid = await persistence.upsert_conversation(sid, flow="other", language=LANG)
    print(f"\n=== Scenario E: other (free chat)  (conv #{cid}, lang={LANG})")
    await _drive_turn(
        graph, session_uuid=sid, conversation_id=cid,
        text="你们公司在哪里?",
        flow="other",
    )


async def _scenario_gate_question(graph) -> None:
    """User asks a question at the happy gate — must NOT escalate."""
    sid = uuid4()
    cid = await persistence.upsert_conversation(sid, flow="presales", language=LANG)
    print(f"\n=== Scenario F: gate question (no escalation)  (conv #{cid}, lang={LANG})")
    # Drive into the recommendations gate via presales.
    await _drive_turn(
        graph, session_uuid=sid, conversation_id=cid,
        text="我在机器人行业,需要用于协作机器人关节驱动。",
        flow="presales",
    )
    # Accept the recommendation gate → goes to guide.find.
    await _drive_turn(
        graph, session_uuid=sid, conversation_id=cid,
        gate_choice="yes",
    )
    # Now we should be on the happy gate. Ask about #2 instead of yes/no.
    state = await _drive_turn(
        graph, session_uuid=sid, conversation_id=cid,
        text="第二个的扭矩具体是多少?能和第一个对比一下吗?",
    )
    outcome = state.get("outcome")
    happy = (state.get("slots") or {}).get("happy")
    print(f"  state after question: outcome={outcome!r} happy={happy!r}")
    assert outcome is None, f"expected NO outcome on a question turn, got {outcome!r}"
    assert happy is None, f"expected happy=None on a question turn, got {happy!r}"
    # Now answer 'yes' — should now escalate to sell.
    await _drive_turn(
        graph, session_uuid=sid, conversation_id=cid,
        gate_choice="yes",
    )


async def main() -> None:
    async with make_checkpointer() as cp:
        graph = build_graph(checkpointer=cp)
        await _scenario_guide_sell(graph)
        await _scenario_guide_human(graph)
        await _scenario_postsales(graph)
        await _scenario_presales(graph)
        await _scenario_other(graph)
        await _scenario_gate_question(graph)
    print("\nZH smoke complete.")


if __name__ == "__main__":
    install_async_event_loop_policy()
    asyncio.run(main())
