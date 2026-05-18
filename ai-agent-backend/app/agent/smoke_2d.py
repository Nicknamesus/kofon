"""Phase 2d smoke test — hit the SSE endpoint and parse the event stream.

Requires uvicorn running on port 8000 in another shell:

    uvicorn app.main:app --port 8000
"""

from __future__ import annotations

import asyncio
import json
from uuid import uuid4

import httpx

API = "http://127.0.0.1:8001"


async def post_message_streaming(
    client: httpx.AsyncClient,
    session_uuid: str,
    *,
    text: str | None = None,
    flow: str | None = None,
    gate_choice: str | None = None,
) -> list[tuple[str, dict]]:
    body: dict = {"session_uuid": session_uuid}
    if text is not None:
        body["text"] = text
    if flow is not None:
        body["flow"] = flow
    if gate_choice is not None:
        body["gate_choice"] = gate_choice

    events: list[tuple[str, dict]] = []
    async with client.stream("POST", f"{API}/api/messages", json=body, timeout=60) as r:
        r.raise_for_status()
        event_name: str | None = None
        async for raw in r.aiter_lines():
            if raw.startswith("event:"):
                event_name = raw.removeprefix("event:").strip()
            elif raw.startswith("data:"):
                payload = json.loads(raw.removeprefix("data:").strip())
                events.append((event_name or "message", payload))
                event_name = None
    return events


def fmt(events: list[tuple[str, dict]]) -> str:
    out: list[str] = []
    for name, data in events:
        if name == "bot_text":
            out.append(f"  [bot_text] {data.get('text', '')[:120]}")
        elif name == "card":
            out.append(f"  [card]     kind={data.get('kind')}")
        elif name == "outcome":
            out.append(f"  [outcome]  {data.get('outcome')}")
        elif name == "done":
            out.append(f"  [done]")
        else:
            out.append(f"  [{name}] {data}")
    return "\n".join(out)


async def main() -> None:
    session_uuid = str(uuid4())
    print(f"session: {session_uuid}\n")

    async with httpx.AsyncClient() as client:
        # turn 1 — chip click: user picks Guide directly
        print("=== turn 1 — chip 'guide' + free-form spec ===")
        ev = await post_message_streaming(
            client,
            session_uuid,
            text="Planetary, low backlash, 90mm frame, around 80 Nm.",
            flow="guide",
        )
        print(fmt(ev))

        # turn 2 — gate yes via the explicit `gate_choice` channel
        print("\n=== turn 2 — gate yes (via gate_choice) ===")
        ev = await post_message_streaming(
            client, session_uuid, gate_choice="yes"
        )
        print(fmt(ev))


if __name__ == "__main__":
    asyncio.run(main())
