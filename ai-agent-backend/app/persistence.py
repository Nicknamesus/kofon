"""Analytics persistence for conversations / messages — Phase 4.

LangGraph already writes its checkpoint blob to Postgres; that's enough
to resume a session, but it's not queryable for analytics (funnel
drop-offs, outcome counts, time-to-resolve). These helpers maintain the
shaped `conversations` and `messages` tables in lock-step with each
turn.

The SSE router (`app/routers/agent.py`) is the only caller — it knows
the user input and sees every event the graph emits. Doing persistence
there keeps graph nodes free of DB-write concerns.

`upsert_conversation` is idempotent on `session_uuid` — the first turn
inserts, every later turn UPDATEs the timestamp / current_node / state.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db import SessionLocal
from app.models import Conversation, Message


async def upsert_conversation(
    session_uuid: UUID,
    *,
    flow: str | None = None,
    language: str | None = None,
) -> int:
    """Return the conversations.id, creating the row on first call."""
    stmt = (
        pg_insert(Conversation)
        .values(
            session_uuid=session_uuid,
            main_type_code=flow,
            language=(language or "EN")[:2].upper(),
        )
        .on_conflict_do_update(
            index_elements=["session_uuid"],
            set_={
                # Don't clobber main_type_code with NULL on a later turn that
                # didn't carry a flow chip.
                **({"main_type_code": flow} if flow else {}),
                "last_message_at": __now_sql_expr(),
            },
        )
        .returning(Conversation.id)
    )
    async with SessionLocal() as session:
        result = await session.execute(stmt)
        cid = result.scalar_one()
        await session.commit()
        return cid


async def append_user_message(
    conversation_id: int,
    *,
    text: str | None,
    gate_choice: str | None,
    flow: str | None,
    subflow: str | None,
    picked_problem_id: int | None,
) -> None:
    """Record the user's turn. content_type reflects what kind of input it was."""
    if gate_choice:
        content_type = "gate_choice"
        content: dict[str, Any] = {"gate_choice": gate_choice}
    elif picked_problem_id is not None:
        content_type = "picked_problem"
        content = {"picked_problem_id": picked_problem_id}
    elif text and (flow or subflow):
        content_type = "chip"
        content = {"text": text, "flow": flow, "subflow": subflow}
    else:
        content_type = "text"
        content = {"text": text or ""}
    await _append(
        conversation_id,
        role="user",
        content_type=content_type,
        content=content,
        node=None,
    )


async def append_bot_text(
    conversation_id: int, text: str, *, node: str | None
) -> None:
    await _append(
        conversation_id,
        role="bot",
        content_type="text",
        content={"text": text},
        node=node,
    )


async def append_bot_card(
    conversation_id: int, card: dict[str, Any], *, node: str | None
) -> None:
    await _append(
        conversation_id,
        role="bot",
        content_type="card",
        content=card,
        node=node,
    )


async def update_conversation_state(
    conversation_id: int,
    *,
    current_node: str | None,
    state_snapshot: dict[str, Any] | None,
) -> None:
    """Patch the conversations row with the latest current_node / state.

    `state` is JSONB and only stores a slim mirror — we strip messages
    (they live in their own table) and any non-JSONable values.
    """
    values: dict[str, Any] = {"last_message_at": __now_sql_expr()}
    if current_node is not None:
        values["current_node"] = current_node
    if state_snapshot is not None:
        values["state"] = _slim_state(state_snapshot)
    async with SessionLocal() as session:
        await session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(**values)
        )
        await session.commit()


# ---------------- internals ----------------


async def _append(
    conversation_id: int,
    *,
    role: str,
    content_type: str,
    content: dict[str, Any],
    node: str | None,
) -> None:
    async with SessionLocal() as session:
        session.add(
            Message(
                conversation_id=conversation_id,
                role=role,
                content_type=content_type,
                content=_jsonable(content),
                node=node,
            )
        )
        await session.commit()


def _slim_state(state: dict[str, Any]) -> dict[str, Any]:
    """Drop messages (own table) and coerce values into JSON-safe form."""
    slim = {k: v for k, v in state.items() if k != "messages"}
    return _jsonable(slim)


def _jsonable(obj: Any) -> Any:
    """Best-effort JSON-coerce. Anything that survives a json round-trip
    is kept; everything else is stringified."""
    try:
        return json.loads(json.dumps(obj, default=str))
    except (TypeError, ValueError):
        return {"_repr": repr(obj)}


def __now_sql_expr():
    from sqlalchemy import func
    return func.now()
