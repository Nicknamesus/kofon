"""Agent SSE endpoint.

POST /api/messages streams agent events back to the widget as
Server-Sent Events. One endpoint handles every interaction:

  - free-form text:        {"session_uuid": "...", "text": "..."}
  - chip click (entry):    {"session_uuid": "...", "text": "Show me products", "flow": "guide"}
  - gate yes/no:           {"session_uuid": "...", "gate_choice": "yes"}

Event kinds streamed:
  bot_text   {text: string}            — assistant prose
  card       {kind, payload}           — structured card (product_results,
                                         recommendations, gate, outcome)
  outcome    {outcome: string}         — fired when the conversation
                                         terminates (sell | human_handoff
                                         | resolved)
  done       {}                        — last event of the response

A `POST /api/sessions` helper returns a new `session_uuid` for fresh
clients that haven't put one in localStorage yet. Strictly optional —
clients can generate their own UUIDs.

Phase 4: every turn also writes shaped `conversations` / `messages`
rows via `app.persistence`. The LangGraph checkpoint covers resumability;
these tables cover analytics.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field

from app import persistence
from app.agent.checkpointer import make_checkpointer
from app.agent.graph import build_graph

router = APIRouter(prefix="/api", tags=["agent"])


class SessionStartResponse(BaseModel):
    session_uuid: UUID


class MessageRequest(BaseModel):
    session_uuid: UUID
    text: str | None = Field(
        default=None, description="User-typed message; either this or gate_choice is required."
    )
    gate_choice: str | None = Field(
        default=None,
        description="UI signal for the happy gate — 'yes' or 'no'. "
        "Translated into a synthesized HumanMessage so the gate node can read it.",
    )
    flow: str | None = Field(
        default=None,
        description="Optional flow override (chip click). Skips entry_router. "
        "One of: presales | guide | postsales | other.",
    )
    subflow: str | None = Field(
        default=None,
        description="Optional sub-flow within a primary flow. "
        "Currently honoured: 'customize' (inside `flow=guide`).",
    )
    picked_problem_id: int | None = Field(
        default=None,
        description="UI signal: user clicked a candidate from a postsales "
        "ambiguous shortlist. Routes the turn straight to match_kb to "
        "present that specific problem by id (no vector search).",
    )
    language: str | None = Field(
        default=None,
        description="Optional 2-letter language code (e.g. 'EN', 'ZH'). "
        "Persisted on the conversations row for analytics.",
    )


@router.post("/sessions", response_model=SessionStartResponse)
async def start_session() -> SessionStartResponse:
    """Convenience: hand the client a fresh UUID."""
    return SessionStartResponse(session_uuid=uuid4())


@router.post("/messages")
async def post_message(payload: MessageRequest) -> StreamingResponse:
    if not payload.text and not payload.gate_choice and not payload.picked_problem_id:
        # No content to send — empty stream with just `done`.
        async def empty() -> AsyncIterator[str]:
            yield _sse("done", {})

        return StreamingResponse(empty(), media_type="text/event-stream")

    user_text = payload.text or payload.gate_choice or ""

    async def event_stream() -> AsyncIterator[str]:
        # Persist conversation + user message before running the graph,
        # so the conversations.id is available to outcome side-effects.
        conversation_id = await persistence.upsert_conversation(
            payload.session_uuid,
            flow=payload.flow,
            language=payload.language,
        )
        await persistence.append_user_message(
            conversation_id,
            text=payload.text,
            gate_choice=payload.gate_choice,
            flow=payload.flow,
            subflow=payload.subflow,
            picked_problem_id=payload.picked_problem_id,
        )

        config = {"configurable": {"thread_id": str(payload.session_uuid)}}
        graph_input: dict = {
            "session_uuid": payload.session_uuid,
            "conversation_id": conversation_id,
        }
        if user_text:
            graph_input["messages"] = [HumanMessage(content=user_text)]
        if payload.flow:
            graph_input["flow"] = payload.flow
        slot_input: dict = {}
        if payload.subflow == "customize":
            # Trip the guide.customize branch in _guide_dispatch.
            slot_input["customize"] = {"active": True}
        if payload.picked_problem_id:
            slot_input["picked_problem_id"] = payload.picked_problem_id
        if slot_input:
            graph_input["slots"] = slot_input

        async with make_checkpointer() as cp:
            graph = build_graph(checkpointer=cp)

            final_outcome: str | None = None
            last_node: str | None = None
            last_state: dict | None = None

            async for chunk in graph.astream(
                graph_input, config=config, stream_mode="updates"
            ):
                # chunk is {node_name: state_update}
                for node_name, update in chunk.items():
                    if not isinstance(update, dict):
                        continue
                    last_node = node_name
                    last_state = update
                    for msg in update.get("messages") or []:
                        if isinstance(msg, AIMessage) and msg.content:
                            yield _sse("bot_text", {"text": msg.content})
                            await persistence.append_bot_text(
                                conversation_id, msg.content, node=node_name
                            )
                    for card in update.get("cards") or []:
                        yield _sse("card", card)
                        await persistence.append_bot_card(
                            conversation_id, card, node=node_name
                        )
                    if update.get("outcome"):
                        final_outcome = update["outcome"]

            if final_outcome:
                yield _sse("outcome", {"outcome": final_outcome})

            # Patch the conversations row with the latest snapshot. The
            # outcome side-effects handler already wrote outcome/rfq/ticket
            # columns; here we sync current_node and the slim state mirror.
            await persistence.update_conversation_state(
                conversation_id,
                current_node=(last_state or {}).get("current_node") or last_node,
                state_snapshot=last_state,
            )

            yield _sse("done", {})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _sse(event: str, data: dict) -> str:
    """Format one SSE event. Each event is `event: ...\\ndata: ...\\n\\n`."""
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"
