"""postsales.fix_gate — partially deterministic 'easily fixable?' gate.

Per BACKEND_PLAN §5, the gate isn't an LLM call alone. Three signals
combine to decide the outcome:

  1. UI button click (`yes` / `no`) — strongest signal, bypasses the LLM.
  2. The curated `solutions.confidence` we showed (1..5). Low confidence
     biases toward escalation even on a tentative 'yes'.
  3. An LLM classification of the free-text reply into one of yes / no /
     question / unclear, with one re-ask before falling through.

Asking a question about the proposed fix is NOT an escalation signal —
the agent answers it (grounded on the candidate solution) and re-emits
the gate so the user can still confirm or reject.

Slot keys (under slots.postsales):
  fix_gate_attempts            int — only bumped on yes/no/unclear, NOT
                                     on a question turn.
  fixed                        bool — set on the yes path
"""

from __future__ import annotations

import json

from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, Field

from app.agent.llm import get_chat_llm, system_message
from app.agent.sanitize import fence
from app.agent.state import AgentState
from app.i18n import t

_CLASSIFY_SYSTEM = (
    "Classify the user's reply to 'Did that fix the issue?'.\n\n"
    "Buckets (pick exactly one):\n"
    "  yes      — the fix worked.\n"
    "  no       — the fix didn't work or the user wants a human / "
    "service engineer.\n"
    "  question — the user is asking for clarification about the "
    "proposed fix (what a step means, how to verify, how long it "
    "takes, etc.) BEFORE deciding whether it worked.\n"
    "  unclear  — you genuinely can't tell."
)

_ANSWER_SYSTEM = (
    "You are a B2B motion-components support chatbot. The customer "
    "was just shown the following problem / solution and is asking a "
    "follow-up question about it. Answer concisely using ONLY the "
    "data below — if the answer isn't there, say so honestly. Don't "
    "claim to be 'connecting' anyone or restart the diagnostic. "
    "Finish your reply with a brief nudge asking whether the fix "
    "worked or if they need more help.\n\n"
    "Problem & solution (JSON):\n{context_json}"
)

# Solutions with confidence at or below this stay on the human path when
# the customer says 'yes' but the fix is shaky — better a callback than a
# false-resolve.
LOW_CONFIDENCE_FLOOR = 2


class _Verdict(BaseModel):
    verdict: str = Field(description="One of: yes, no, question, unclear")


async def run(state: AgentState) -> dict:
    slots = state.get("slots") or {}
    postsales = dict(slots.get("postsales") or {})
    attempts = int(postsales.get("fix_gate_attempts", 0))
    solution = postsales.get("candidate_solution") or {}
    confidence = int(solution.get("confidence", 0) or 0)
    lang = state.get("language")

    last_human = next(
        (m for m in reversed(state.get("messages", []))
         if isinstance(m, HumanMessage)),
        None,
    )

    if last_human is None:
        return {
            "messages": [AIMessage(content=t("pfg_did_fix", lang))],
            "current_node": "postsales.fix_gate",
        }

    # Fast path: gate-button clicks come through as exact 'yes' / 'no'.
    text = (last_human.content or "").strip().lower()
    if text in {"yes", "no"}:
        verdict = text
    else:
        llm = get_chat_llm(temperature=0).with_structured_output(_Verdict)
        v: _Verdict = await llm.ainvoke(
            [system_message(_CLASSIFY_SYSTEM), last_human]
        )
        verdict = (v.verdict or "unclear").strip().lower()
        if verdict not in {"yes", "no", "question", "unclear"}:
            verdict = "unclear"

    if verdict == "question":
        return await _answer_and_reprompt(state, last_human, postsales, lang)

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
                AIMessage(content=t("pfg_reask", lang))
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


async def _answer_and_reprompt(
    state: AgentState,
    last_human: HumanMessage,
    postsales: dict,
    lang: str | None,
) -> dict:
    """Answer a follow-up question about the proposed fix and re-emit
    the gate. `fixed` stays None and `fix_gate_attempts` is not bumped
    — a question is a normal turn, not a failed gate attempt.
    """
    context = {
        "problem_label": postsales.get("candidate_problem_label"),
        "solution": postsales.get("candidate_solution"),
        "symptom": postsales.get("symptom"),
        "sku": postsales.get("sku"),
    }
    context_json = fence(
        json.dumps(context, ensure_ascii=False, default=str), "context"
    )

    llm = get_chat_llm(temperature=0.2)
    reply = await llm.ainvoke(
        [
            system_message(
                _ANSWER_SYSTEM.format(context_json=context_json),
                lang,
            ),
            last_human,
        ]
    )
    answer = (getattr(reply, "content", "") or "").strip()
    messages: list = []
    if answer:
        messages.append(AIMessage(content=answer))
    return {
        "messages": messages or [AIMessage(content=t("pfg_anything_else", lang))],
        "cards": [
            {
                "kind": "gate",
                "payload": {
                    "question": t("pfg_anything_else", lang),
                    "yes_label": t("gate_yes_fixed", lang),
                    "no_label": t("gate_no_still_broken", lang),
                },
            }
        ],
        "current_node": "postsales.fix_gate.question",
    }
