"""postsales.fix_gate — partially deterministic 'easily fixable?' gate.

Per BACKEND_PLAN §5, the gate isn't an LLM call alone. Three signals
combine to decide the outcome:

  1. UI button click (`yes` / `no`) — strongest signal, bypasses the LLM.
  2. The curated `solutions.confidence` we showed (1..5). Low confidence
     biases toward escalation even on a tentative 'yes'.
  3. An LLM 'yes' / 'no' / 'unclear' classification of the free-text
     reply, with one re-ask before falling through.

The LLM only paraphrases the outcome — it doesn't decide it.

Slot keys (under slots.postsales):
  fix_gate_attempts            int
  fixed                        bool — set on the yes path
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel

from app.agent.llm import get_chat_llm
from app.agent.state import AgentState

SYSTEM = (
    "Classify the user's reply to 'Did that fix the issue?'. "
    "Return 'yes' if the fix worked, 'no' if it didn't, 'unclear' otherwise."
)

# Solutions with confidence at or below this stay on the human path when
# the customer says 'yes' but the fix is shaky — better a callback than a
# false-resolve.
LOW_CONFIDENCE_FLOOR = 2


class _Verdict(BaseModel):
    verdict: str  # 'yes' | 'no' | 'unclear'


async def run(state: AgentState) -> dict:
    slots = state.get("slots") or {}
    postsales = dict(slots.get("postsales") or {})
    attempts = int(postsales.get("fix_gate_attempts", 0))
    solution = postsales.get("candidate_solution") or {}
    confidence = int(solution.get("confidence", 0) or 0)

    last_human = next(
        (m for m in reversed(state.get("messages", []))
         if isinstance(m, HumanMessage)),
        None,
    )

    if last_human is None:
        return {
            "messages": [AIMessage(content="Did that fix the issue?")],
            "current_node": "postsales.fix_gate",
        }

    # Fast path: gate-button clicks come through as exact 'yes' / 'no'.
    text = (last_human.content or "").strip().lower()
    if text in {"yes", "no"}:
        verdict = text
    else:
        llm = get_chat_llm(temperature=0).with_structured_output(_Verdict)
        v: _Verdict = await llm.ainvoke(
            [SystemMessage(content=SYSTEM), last_human]
        )
        verdict = v.verdict.strip().lower()
        if verdict not in {"yes", "no"}:
            verdict = "unclear"

    if verdict == "yes":
        # Low-confidence solution? Don't claim resolved — bump to human
        # so an engineer can verify.
        if confidence and confidence <= LOW_CONFIDENCE_FLOOR:
            return {
                "slots": {
                    "postsales": {
                        **postsales,
                        "fix_gate_attempts": attempts + 1,
                        "fixed": False,
                        "low_confidence_escalation": True,
                    }
                },
                "current_node": "postsales.fix_gate.low_conf",
            }
        return {
            "slots": {
                "postsales": {
                    **postsales,
                    "fix_gate_attempts": attempts + 1,
                    "fixed": True,
                }
            },
            "current_node": "postsales.fix_gate",
        }

    if verdict == "no":
        return {
            "slots": {
                "postsales": {
                    **postsales,
                    "fix_gate_attempts": attempts + 1,
                    "fixed": False,
                }
            },
            "current_node": "postsales.fix_gate",
        }

    # Unclear — one re-ask, then fall through to human.
    if attempts == 0:
        return {
            "messages": [
                AIMessage(
                    content=(
                        "Sorry — just to confirm, did that resolve the issue, "
                        "or is it still happening?"
                    )
                )
            ],
            "slots": {
                "postsales": {
                    **postsales,
                    "fix_gate_attempts": attempts + 1,
                }
            },
            "current_node": "postsales.fix_gate",
        }

    return {
        "slots": {
            "postsales": {
                **postsales,
                "fix_gate_attempts": attempts + 1,
                "fixed": False,
            }
        },
        "current_node": "postsales.fix_gate",
    }
