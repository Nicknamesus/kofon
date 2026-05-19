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
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field

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


@router.post("/sessions", response_model=SessionStartResponse)
async def start_session() -> SessionStartResponse:
    """Convenience: hand the client a fresh UUID."""
    return SessionStartResponse(session_uuid=uuid4())


@router.post("/messages")
async def post_message(payload: MessageRequest) -> StreamingResponse:
    if not payload.text and not payload.gate_choice:
        # No content to send — empty stream with just `done`.
        async def empty() -> AsyncIterator[str]:
            yield _sse("done", {})

        return StreamingResponse(empty(), media_type="text/event-stream")

    user_text = payload.text or payload.gate_choice or ""

    async def event_stream() -> AsyncIterator[str]:
        config = {"configurable": {"thread_id": str(payload.session_uuid)}}
        graph_input: dict = {
            "messages": [HumanMessage(content=user_text)],
        }
        if payload.flow:
            graph_input["flow"] = payload.flow
        if payload.subflow == "customize":
            # Trip the guide.customize branch in _guide_dispatch.
            graph_input["slots"] = {"customize": {"active": True}}

        async with make_checkpointer() as cp:
            graph = build_graph(checkpointer=cp)

            # If this thread already terminated, the dispatch will short-
            # circuit to END and the stream would be empty (typing dots
            # would just disappear). Surface that explicitly so the user
            # knows to start a new conversation.
            try:
                snapshot = await graph.aget_state(config)
                if snapshot and snapshot.values.get("outcome"):
                    yield _sse("bot_text", {
                        "text": "This conversation already wrapped up — "
                                "head back to the menu and pick a new path "
                                "to start fresh."
                    })
                    yield _sse("done", {})
                    return
            except Exception:  # noqa: BLE001
                # No prior state — first turn on this thread. Nothing to do.
                pass

            final_outcome: str | None = None

            async for chunk in graph.astream(
                graph_input, config=config, stream_mode="updates"
            ):
                # chunk is {node_name: state_update}
                for _node, update in chunk.items():
                    if not isinstance(update, dict):
                        continue
                    for msg in update.get("messages") or []:
                        if isinstance(msg, AIMessage) and msg.content:
                            yield _sse("bot_text", {"text": msg.content})
                    for card in update.get("cards") or []:
                        yield _sse("card", card)
                    if update.get("outcome"):
                        final_outcome = update["outcome"]

            if final_outcome:
                yield _sse("outcome", {"outcome": final_outcome})

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
