"""One-time CLI: create the LangGraph checkpointer's Postgres tables.

Idempotent — safe to re-run on every deploy. Tables created live in the
public schema alongside our Alembic-managed tables; Alembic ignores
them because they're not in `Base.metadata`.

Usage:
    python -m app.agent.setup_checkpointer
"""

from __future__ import annotations

import asyncio

from app.agent.checkpointer import setup_checkpointer
from app.runtime import install_async_event_loop_policy


def main() -> None:
    install_async_event_loop_policy()
    asyncio.run(setup_checkpointer())
    print("checkpointer tables ready")


if __name__ == "__main__":
    main()
