"""Graph builders.

`build_echo_graph` — Phase 2a sanity check. Stays around as a plumbing
smoke test.

`build_graph` — the real graph. Phase 3 shape:

    START
      ├── (flow already set) → flow node
      └── (no flow) → entry_router → flow node

    flow node = presales.figure_out | guide.find | guide.customize |
                guide.happy_gate | postsales.identify |
                postsales.match_kb | postsales.fix_gate |
                other.reclassify | outcome_*

    presales.figure_out → guide.find (handoff) | END
    guide.find / guide.customize → END (await reply, then happy_gate)
    guide.happy_gate → outcome_sell | outcome_human | END
    postsales.identify → postsales.match_kb (when symptom present) | END
    postsales.match_kb → END (await reply, then fix_gate) | outcome_human
    postsales.fix_gate → outcome_resolved | outcome_human |
                        postsales.match_kb (retry on 'no') | END
    other.reclassify → re-dispatch via flow | END
    outcome_* → END
"""

from __future__ import annotations

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from app.agent.nodes import (
    echo,
    entry_router,
    guide_customize,
    guide_find,
    guide_happy_gate,
    other_reclassify,
    outcomes,
    post_outcome_chat,
    postsales_fix_gate,
    postsales_identify,
    postsales_match_kb,
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


# ------------------------- Phase 3 dispatch -------------------------


def _guide_dispatch(slots: dict) -> str:
    """Pick the right guide-* node based on slot state."""
    customize = slots.get("customize") or {}

    # Customize takes precedence: a fresh "I want to custom build…" must
    # not be intercepted by a stale find_phase=presented from an earlier
    # product search. Only fall through to the gate when customize itself
    # is the thing waiting for an answer.
    if customize.get("active") and customize.get("phase") != "presented":
        return "guide.customize"

    # Gate — a result (search or customize) was presented and the user
    # hasn't answered yet.
    if (
        slots.get("find_phase") == "presented"
        and slots.get("happy") is None
    ):
        return "guide.happy_gate"

    if customize.get("active"):
        return "guide.customize"

    return "guide.find"


def _postsales_dispatch(slots: dict) -> str:
    """Pick the right postsales-* node based on slot state."""
    postsales = slots.get("postsales") or {}
    phase = postsales.get("match_phase")

    # Deterministic candidate pick from the UI: go straight to match_kb,
    # which will look the problem up by id and present it.
    if slots.get("picked_problem_id"):
        return "postsales.match_kb"

    if phase == "presented" and postsales.get("fixed") is None:
        return "postsales.fix_gate"

    # If we previously presented an ambiguous shortlist, the user's next
    # turn is either picking a label or clarifying. Re-run identify so the
    # symptom slot gets refreshed before re-matching.
    if phase == "ambiguous":
        return "postsales.identify"

    if postsales.get("phase") == "ready" and phase != "no_match":
        return "postsales.match_kb"

    return "postsales.identify"


def _entry_dispatch(state: AgentState) -> str:
    """First branch on every turn."""
    if state.get("outcome"):
        # Flow has terminated — don't re-run it, but still answer the user
        # via the post-outcome chat node so the conversation stays open.
        return "post_outcome_chat"

    flow = state.get("flow")
    slots = state.get("slots") or {}

    if not flow:
        return "entry_router"

    if flow == "guide":
        return _guide_dispatch(slots)

    if flow == "presales":
        return "presales.figure_out"

    if flow == "postsales":
        return _postsales_dispatch(slots)

    # other
    return "other.reclassify"


def _after_router(state: AgentState) -> str:
    flow = state.get("flow")
    slots = state.get("slots") or {}
    if flow == "guide":
        return _guide_dispatch(slots)
    if flow == "presales":
        return "presales.figure_out"
    if flow == "postsales":
        return _postsales_dispatch(slots)
    return "other.reclassify"


def _after_presales(state: AgentState) -> str:
    """presales hands off to guide.find in the same turn once a family is chosen."""
    if state.get("outcome"):
        return END
    if state.get("flow") == "guide":
        return "guide.find"
    return END


def _after_gate(state: AgentState) -> str:
    slots = state.get("slots") or {}
    happy = slots.get("happy")
    if happy is True:
        return "outcome_sell"
    if happy is False:
        return "outcome_human"
    return END


def _after_postsales_identify(state: AgentState) -> str:
    if state.get("outcome"):
        return END
    postsales = (state.get("slots") or {}).get("postsales") or {}
    if postsales.get("phase") == "ready":
        return "postsales.match_kb"
    return END


def _after_postsales_match(state: AgentState) -> str:
    if state.get("outcome"):
        return END
    # Presenting candidates: hand back to the user; the next turn will
    # re-enter via `_postsales_dispatch` and pick the gate or re-match.
    return END


def _after_postsales_fix_gate(state: AgentState) -> str:
    if state.get("outcome"):
        return END
    postsales = (state.get("slots") or {}).get("postsales") or {}
    if postsales.get("low_confidence_escalation"):
        return "outcome_human"
    fixed = postsales.get("fixed")
    if fixed is True:
        return "outcome_resolved"
    if fixed is False:
        return "outcome_human"
    return END  # asked a clarifying question; await the user.


def _after_reclassify(state: AgentState) -> str:
    """If reclassify rerouted, run the new flow's node this same turn."""
    if state.get("outcome"):
        return END
    flow = state.get("flow")
    slots = state.get("slots") or {}
    if flow == "presales":
        return "presales.figure_out"
    if flow == "guide":
        return _guide_dispatch(slots)
    if flow == "postsales":
        return _postsales_dispatch(slots)
    return END


def build_graph(checkpointer: BaseCheckpointSaver | None = None):
    g = StateGraph(AgentState)

    g.add_node("entry_router", entry_router.run)
    g.add_node("presales.figure_out", presales_figure_out.run)
    g.add_node("guide.find", guide_find.run)
    g.add_node("guide.customize", guide_customize.run)
    g.add_node("guide.happy_gate", guide_happy_gate.run)
    g.add_node("postsales.identify", postsales_identify.run)
    g.add_node("postsales.match_kb", postsales_match_kb.run)
    g.add_node("postsales.fix_gate", postsales_fix_gate.run)
    g.add_node("other.reclassify", other_reclassify.run)
    g.add_node("outcome_sell", outcomes.outcome_sell)
    g.add_node("outcome_human", outcomes.outcome_human)
    g.add_node("outcome_resolved", outcomes.outcome_resolved)
    g.add_node("post_outcome_chat", post_outcome_chat.run)

    flow_nodes = [
        "entry_router",
        "presales.figure_out",
        "guide.find",
        "guide.customize",
        "guide.happy_gate",
        "postsales.identify",
        "postsales.match_kb",
        "postsales.fix_gate",
        "other.reclassify",
    ]

    g.add_conditional_edges(
        START,
        _entry_dispatch,
        flow_nodes + ["outcome_human", "post_outcome_chat", END],
    )

    g.add_conditional_edges(
        "entry_router",
        _after_router,
        [
            "guide.find",
            "guide.customize",
            "guide.happy_gate",
            "presales.figure_out",
            "postsales.identify",
            "postsales.match_kb",
            "postsales.fix_gate",
            "other.reclassify",
        ],
    )

    g.add_conditional_edges(
        "presales.figure_out",
        _after_presales,
        ["guide.find", END],
    )

    g.add_edge("guide.find", END)
    g.add_edge("guide.customize", END)

    g.add_conditional_edges(
        "guide.happy_gate",
        _after_gate,
        ["outcome_sell", "outcome_human", END],
    )

    g.add_conditional_edges(
        "postsales.identify",
        _after_postsales_identify,
        ["postsales.match_kb", END],
    )

    g.add_conditional_edges(
        "postsales.match_kb",
        _after_postsales_match,
        [END],
    )

    g.add_conditional_edges(
        "postsales.fix_gate",
        _after_postsales_fix_gate,
        ["outcome_resolved", "outcome_human", END],
    )

    g.add_conditional_edges(
        "other.reclassify",
        _after_reclassify,
        [
            "presales.figure_out",
            "guide.find",
            "guide.customize",
            "guide.happy_gate",
            "postsales.identify",
            "postsales.match_kb",
            "postsales.fix_gate",
            END,
        ],
    )

    g.add_edge("outcome_sell", END)
    g.add_edge("outcome_human", END)
    g.add_edge("outcome_resolved", END)
    g.add_edge("post_outcome_chat", END)

    return g.compile(checkpointer=checkpointer)
