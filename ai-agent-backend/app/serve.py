"""Programmatic uvicorn entry point — fixes Windows/Python 3.14 loop choice.

On Python 3.14, `asyncio.set_event_loop_policy(...)` no longer reliably
controls the loop that uvicorn ends up using — `asyncio.run` constructs
its loop via the default loop factory, and uvicorn's own setup runs
after our import. The robust fix is to create the SelectorEventLoop
ourselves and run uvicorn's Server.serve() inside it.

(psycopg async — which the LangGraph checkpointer uses — cannot run on
Windows' default ProactorEventLoop. SelectorEventLoop is the only loop
on Windows where both psycopg async and our HTTP stack coexist.)

Usage:
    python -m app.serve --port 8001

On Linux / Mac this is functionally equivalent to `uvicorn app.main:app`.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

import uvicorn


def _make_loop() -> asyncio.AbstractEventLoop:
    if sys.platform == "win32":
        return asyncio.SelectorEventLoop()
    return asyncio.new_event_loop()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()

    config = uvicorn.Config(
        "app.main:app",
        host=args.host,
        port=args.port,
        loop="asyncio",
    )
    server = uvicorn.Server(config)

    loop = _make_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(server.serve())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
