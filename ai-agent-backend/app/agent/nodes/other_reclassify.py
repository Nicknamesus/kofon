"""other.reclassify — second-chance routing for free-form input.

The router landed the user in `other` — either off-topic chat or input
the first classifier couldn't read. Per BACKEND_PLAN §5 and the
`feedback-llm-before-human-handoff` memory, we try one cheap LLM call to
re-map the conversation into a primary flow before any forced escalation.

  - If confidence ≥ CONFIDENCE_FLOOR for one of {presales, guide,
    postsales}, switch `state.flow` and let the graph re-dispatch — the
    chosen flow node runs in the same turn.
  - Otherwise produce a single friendly free-chat reply with a clear
    "talk to a human" CTA. We do this at most RECLASSIFY_MAX_ATTEMPTS
    times per session before falling through to outcome_human.

Slot keys (under slots.other):
  reclassify_attempts        int
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.agent.llm import get_chat_llm
from app.agent.state import AgentState

CONFIDENCE_FLOOR = 0.6
RECLASSIFY_MAX_ATTEMPTS = 2

SYSTEM = """You're a second-chance router for a B2B motion-components
chatbot. The first router classified the user's message as 'other'
(greeting, off-topic, ambiguous). Try once more to map it to one of the
real flows.

Flows:
  presales   — exploring options, describing an application
  guide      — choosing or configuring a specific product
  postsales  — they own a unit and it's broken
  other      — still genuinely off-topic / ambiguous

Return confidence ∈ [0, 1]. Be conservative — when in doubt return
'other' with low confidence, and the user gets a graceful free-chat
reply instead of being railroaded into the wrong flow.
"""


class _Reclass(BaseModel):
    flow: str = Field(description="One of: presales, guide, postsales, other")
    confidence: float = Field(ge=0.0, le=1.0)


async def run(state: AgentState) -> dict:
    slots = state.get("slots") or {}
    other = dict(slots.get("other") or {})
    attempts = int(other.get("reclassify_attempts", 0))

    last_human = next(
        (m for m in reversed(state.get("messages", []))
         if isinstance(m, HumanMessage)),
        None,
    )

    if last_human is None:
        return _free_chat_reply(other, attempts, "Hi — what can I help with?")

    llm = get_chat_llm(temperature=0).with_structured_output(_Reclass)
    pick: _Reclass = await llm.ainvoke(
        [SystemMessage(content=SYSTEM), last_human]
    )
    flow = (pick.flow or "other").strip().lower()

    if (
        flow in {"presales", "guide", "postsales"}
        and pick.confidence >= CONFIDENCE_FLOOR
    ):
        # Hand control back to the real flow. The graph's entry dispatch
        # will pick up `flow` and route correctly on the same turn.
        return {
            "flow": flow,
            "slots": {
                "other": {**other, "reclassify_attempts": attempts + 1},
            },
            "current_node": "other.reclassify.routed",
        }

    if attempts + 1 >= RECLASSIFY_MAX_ATTEMPTS:
        # Don't loop forever — drop to human after a couple of unhelpful tries.
        return {
            "outcome": "human_handoff",
            "messages": [
                AIMessage(
                    content=(
                        "I'm not finding a path that fits — let me connect you "
                        "with a human who can help."
                    )
                )
            ],
            "cards": [
                {
                    "kind": "outcome",
                    "payload": {
                        "outcome": "human_handoff",
                        "title": "Connecting you with a human",
                        "next_step": "human",
                    },
                }
            ],
            "slots": {
                "other": {**other, "reclassify_attempts": attempts + 1},
            },
            "current_node": "other.reclassify.exhausted",
        }

    # Genuine free-chat path — short, friendly, with a "talk to a human"
    # nudge so they're never stuck.
    return _free_chat_reply(
        other,
        attempts,
        "Happy to chat — but I'm best at three things: helping you "
        "pick a product, configuring one, or troubleshooting a unit "
        "you already have. Which of those sounds closest? (Or I can "
        "connect you with a human.)",
    )


def _free_chat_reply(other: dict, attempts: int, text: str) -> dict:
    return {
        "messages": [AIMessage(content=text)],
        "slots": {
            "other": {**other, "reclassify_attempts": attempts + 1},
        },
        "cards": [
            {
                "kind": "suggest",
                "payload": {
                    "replies": [
                        "I'm choosing a product",
                        "I have a broken unit",
                        "Talk to a human",
                    ]
                },
            }
        ],
        "current_node": "other.reclassify.free_chat",
    }
