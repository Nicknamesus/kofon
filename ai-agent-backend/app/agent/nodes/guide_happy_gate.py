"""guide.happy_gate — interprets the user's reply to the candidate cards.

Partially deterministic per BACKEND_PLAN §5: the chip-click path is a
plain UI signal (no LLM); the free-text path uses a narrow LLM
classification ('yes' | 'no' | 'unclear'). If unclear we re-ask once,
then route to human handoff to avoid loops.

Slot keys:
    slots.happy           bool | None
    slots.gate_attempts   int (defaults to 0)
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel

from app.agent.llm import get_chat_llm
from app.agent.state import AgentState

SYSTEM = (
    "Classify the user's last message as a reply to the question "
    "'Do any of these products look right?'. "
    "Return 'yes' if they accept one, 'no' if they reject all, "
    "or 'unclear' if you cannot tell."
)


class _Verdict(BaseModel):
    verdict: str  # 'yes' | 'no' | 'unclear'


async def run(state: AgentState) -> dict:
    last_human = next(
        (m for m in reversed(state.get("messages", []))
         if isinstance(m, HumanMessage)),
        None,
    )

    slots = state.get("slots") or {}
    attempts = int(slots.get("gate_attempts", 0))

    if last_human is None:
        return {
            "messages": [
                AIMessage(content="Do any of these products look right?")
            ],
            "current_node": "guide.happy_gate",
        }

    llm = get_chat_llm(temperature=0).with_structured_output(_Verdict)
    verdict: _Verdict = await llm.ainvoke(
        [SystemMessage(content=SYSTEM), last_human]
    )

    if verdict.verdict == "yes":
        return {
            "slots": {"happy": True, "gate_attempts": attempts + 1},
            "current_node": "guide.happy_gate",
        }
    if verdict.verdict == "no":
        return {
            "slots": {"happy": False, "gate_attempts": attempts + 1},
            "current_node": "guide.happy_gate",
        }

    # Unclear. Re-ask once, then fall through on the next attempt.
    if attempts == 0:
        return {
            "messages": [
                AIMessage(
                    content=(
                        "Just to confirm — do any of those look like the right "
                        "fit, or should I connect you with someone?"
                    )
                )
            ],
            "slots": {"gate_attempts": attempts + 1},
            "current_node": "guide.happy_gate",
        }

    # Two unclear answers in a row — route to human to avoid loops.
    return {
        "slots": {"happy": False, "gate_attempts": attempts + 1},
        "current_node": "guide.happy_gate",
    }
