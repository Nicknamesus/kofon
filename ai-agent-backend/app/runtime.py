"""Process-wide runtime tweaks. Call before creating any event loop.

Currently just one tweak: on Windows, swap the default ProactorEventLoop
for a SelectorEventLoop so psycopg's async driver can talk to Postgres
(the LangGraph checkpointer needs this). No-op on every other platform.
"""

from __future__ import annotations

import asyncio
import sys


def install_async_event_loop_policy() -> None:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
