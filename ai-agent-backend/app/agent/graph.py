"""Graph builders.

`build_echo_graph` — Phase 2a sanity check. Stays around as a plumbing
smoke test.

`build_graph` — the real graph. Phase 2c shape:

    START
      ├── (flow already set) → flow node
      └── (no flow) → entry_router → flow node

    flow node = presales.figure_out | guide.find | guide.happy_gate
                | outcome_human (for postsales/other in 2c — Phase 3
                replaces with real postsales nodes)

    presales.figure_out → (if handed off to guide) guide.find
                       → (else) END

    guide.find → END (await next user message)

    guide.happy_gate → outcome_sell | outcome_human | END

    outcome_* → END
"""

from __future__ import annotations

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from app.agent.nodes import (
    echo,
    entry_router,
    guide_find,
    guide_happy_gate,
    outcomes,
    presales_figure_out,
)
from app.agent.state import AgentState


def build_echo_graph(checkpointer: BaseCheckpointSaver | None = None):
    """One node: echo. Phase 2a only."""
    g = StateGraph(AgentState)
    g.add_node("echo", echo.run)
    g.add_edge(START, "echo")
    g.add_edge("echo", END)
    return g.compile(checkpointer=checkpointer)


# ---------------- Phase 2c: router + pre-sales + guide-find ----------------


def _entry_dispatch(state: AgentState) -> str:
    """First branch on every turn."""
    if state.get("outcome"):
        # Conversation already terminated. Don't re-run anything.
        return END

    flow = state.get("flow")
    slots = state.get("slots") or {}

    if not flow:
        return "entry_router"

    if flow == "guide":
        if (
            slots.get("find_phase") == "presented"
            and slots.get("happy") is None
        ):
            return "guide.happy_gate"
        return "guide.find"

    if flow == "presales":
        return "presales.figure_out"

    # postsales and other land on human handoff for Phase 2c.
    # Phase 3 replaces 'postsales' with its own nodes.
    return "outcome_human"


def _after_router(state: AgentState) -> str:
    flow = state.get("flow")
    if flow == "guide":
        return "guide.find"
    if flow == "presales":
        return "presales.figure_out"
    return "outcome_human"


def _after_presales(state: AgentState) -> str:
    """presales hands off to guide.find in the same turn once a family is chosen."""
    if state.get("flow") == "guide":
        return "guide.find"
    if state.get("outcome"):
        return END
    return END


def _after_gate(state: AgentState) -> str:
    slots = state.get("slots") or {}
    happy = slots.get("happy")
    if happy is True:
        return "outcome_sell"
    if happy is False:
        return "outcome_human"
    return END


def build_graph(checkpointer: BaseCheckpointSaver | None = None):
    g = StateGraph(AgentState)

    g.add_node("entry_router", entry_router.run)
    g.add_node("presales.figure_out", presales_figure_out.run)
    g.add_node("guide.find", guide_find.run)
    g.add_node("guide.happy_gate", guide_happy_gate.run)
    g.add_node("outcome_sell", outcomes.outcome_sell)
    g.add_node("outcome_human", outcomes.outcome_human)

    g.add_conditional_edges(
        START,
        _entry_dispatch,
        [
            "entry_router",
            "presales.figure_out",
            "guide.find",
            "guide.happy_gate",
            "outcome_human",
            END,
        ],
    )

    g.add_conditional_edges(
        "entry_router",
        _after_router,
        ["guide.find", "presales.figure_out", "outcome_human"],
    )

    g.add_conditional_edges(
        "presales.figure_out",
        _after_presales,
        ["guide.find", END],
    )

    g.add_edge("guide.find", END)

    g.add_conditional_edges(
        "guide.happy_gate",
        _after_gate,
        ["outcome_sell", "outcome_human", END],
    )

    g.add_edge("outcome_sell", END)
    g.add_edge("outcome_human", END)

    return g.compile(checkpointer=checkpointer)
