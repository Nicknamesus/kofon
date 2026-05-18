"""Graph state schema — shared across all nodes.

LangGraph runs each node with the full state; nodes return partial dicts
that the framework merges in. `messages` uses `add_messages` so message
returns are *appended* rather than replacing the channel.

A slim denormalized mirror of this state is also written to
`conversations.state` for analytics (see BACKEND_PLAN §3.6).
"""

from __future__ import annotations

from typing import Annotated, Any, TypedDict
from uuid import UUID

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


def merge_slots(left: dict[str, Any] | None, right: dict[str, Any] | None) -> dict[str, Any]:
    """Shallow-merge reducer for the `slots` channel.

    Nodes return only the keys they changed; this reducer combines them
    with the existing state. Nested dicts are replaced wholesale — a node
    that owns `slots.filters` must return the full filters dict, not a
    partial. Keeps the contract simple.
    """
    return {**(left or {}), **(right or {})}


class AgentState(TypedDict, total=False):
    """The channel set the graph operates on.

    Fields are intentionally optional (`total=False`) so nodes only have
    to return the keys they care about.
    """

    # Stable identifiers.
    session_uuid: UUID
    conversation_id: int | None

    # Routing.
    flow: str | None          # 'presales' | 'guide' | 'postsales' | 'other'
    current_node: str | None  # e.g. 'guide.find.results'

    # Slot filling.
    # Free-form collected facts: industry, application, sku, symptom, etc.
    # Keys are flow-specific. Node prompts read/write here, never elsewhere.
    slots: Annotated[dict[str, Any], merge_slots]

    # Per-turn message log. Appended via `add_messages`.
    messages: Annotated[list[AnyMessage], add_messages]

    # Card events the SSE layer will stream. Each entry: {kind, payload}.
    # Cleared by the SSE layer once it drains them — for now, nodes just append.
    cards: Annotated[list[dict[str, Any]], lambda l, r: (l or []) + (r or [])]

    # Terminal state — set by outcome_* nodes only.
    outcome: str | None       # 'sell' | 'human_handoff' | 'resolved' | 'abandoned'
