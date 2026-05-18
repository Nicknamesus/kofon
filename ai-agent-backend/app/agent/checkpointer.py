"""Postgres-backed LangGraph checkpointer.

After every node fires, LangGraph writes the full state snapshot here.
That gives us two properties:

1. **Resumption** — a client posting the same `session_uuid` after a
   disconnect picks up at `current_node` with all slots intact.
2. **Audit** — every turn's state is inspectable in Postgres for
   debugging and analytics.

The checkpointer uses psycopg (sync-driver under the hood, async wrapped)
because that's what `langgraph-checkpoint-postgres` ships with. SQLAlchemy
in `app.db` keeps using asyncpg for app code — they coexist on the same
database without interfering.

Tables created (under the public schema) by `setup_checkpointer`:
    checkpoints, checkpoint_blobs, checkpoint_writes, checkpoint_migrations

These live alongside our Alembic-managed tables (`conversations`, etc.).
Alembic ignores them because they're not in `Base.metadata`.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.config import get_settings


@asynccontextmanager
async def make_checkpointer() -> AsyncIterator[AsyncPostgresSaver]:
    """Open an async checkpointer scoped to one workflow run.

    Usage:
        async with make_checkpointer() as cp:
            graph = builder.compile(checkpointer=cp)
            await graph.ainvoke(...)
    """
    settings = get_settings()
    async with AsyncPostgresSaver.from_conn_string(
        settings.checkpointer_database_url
    ) as cp:
        yield cp


async def setup_checkpointer() -> None:
    """One-time: create the checkpointer's tables. Idempotent."""
    async with make_checkpointer() as cp:
        await cp.setup()
