"""guide.happy_gate — interprets the user's reply to the candidate cards.

Partially deterministic per BACKEND_PLAN §5: chip-click is a plain UI
signal (no LLM); free-text goes through a narrow classifier. The
classifier has four buckets:

  yes       — user accepts a candidate / wants to proceed
  no        — user rejects all / explicitly wants a human
  question  — user is asking about the candidates (specs, comparison,
              datasheet, lead time, …) before deciding. We answer it
              with a follow-up LLM call (using `slots.candidates` as
              grounding) and re-emit the gate so they can still pick.
  unclear   — genuine ambiguity → re-ask once, then escalate to avoid
              loops.

Escalation only happens when the user asks for it (no) or we can't
parse them twice in a row (unclear → unclear). A question is NOT an
escalation signal — answering it is the whole point of the gate.

Slot keys:
    slots.happy           bool | None
    slots.gate_attempts   int (only bumped on yes/no/unclear paths;
                              questions are normal turns)
"""

from __future__ import annotations

import json

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.agent.llm import get_chat_llm
from app.agent.state import AgentState
from app.i18n import language_instruction, t

# Verdict-only classification — no answer text here, so we can keep this
# call cheap (temperature 0, structured output).
_CLASSIFY_SYSTEM = (
    "Classify the user's last message as a reply to "
    "'Do any of these products look right?'.\n\n"
    "Buckets (pick exactly one):\n"
    "  yes      — the user accepts one of the candidates or wants to "
    "proceed with a quote.\n"
    "  no       — the user rejects all candidates or explicitly asks "
    "to talk to a human / engineer.\n"
    "  question — the user is asking for more information about the "
    "candidates BEFORE deciding: specs, comparison, lead time, "
    "datasheet, dimensions, price ballpark, etc. Anything that "
    "expects an answer rather than a routing decision.\n"
    "  unclear  — you genuinely can't tell.\n\n"
    "Asking a question is NOT acceptance. 'Tell me more about #2' or "
    "'what's the torque on the second one?' are 'question', not 'yes'."
)

# Used when the verdict is 'question' — a second, slightly more
# permissive call that actually writes the answer. Grounded on the
# candidates dict so it doesn't invent specs.
_ANSWER_SYSTEM = (
    "You are a B2B motion-components chatbot helping a customer choose "
    "between the candidate products listed below. Answer the user's "
    "question concisely using ONLY the data provided — if the answer "
    "isn't in the data, say so honestly rather than guessing. Don't "
    "restart the flow or claim to be 'connecting' anyone. Finish your "
    "reply with a brief nudge asking whether they'd like to proceed "
    "with one of the candidates or need anything else.\n\n"
    "Candidates (JSON):\n{candidates_json}"
)


class _Verdict(BaseModel):
    verdict: str = Field(description="One of: yes, no, question, unclear")


async def run(state: AgentState) -> dict:
    last_human = next(
        (m for m in reversed(state.get("messages", []))
         if isinstance(m, HumanMessage)),
        None,
    )

    slots = state.get("slots") or {}
    attempts = int(slots.get("gate_attempts", 0))
    lang = state.get("language")

    if last_human is None:
        return {
            "messages": [
                AIMessage(content=t("ghg_ask_fit", lang))
            ],
            "current_node": "guide.happy_gate",
        }

    # Fast path: gate-button clicks come through as bare 'yes' / 'no'.
    text = (last_human.content or "").strip().lower()
    if text == "yes":
        verdict = "yes"
    elif text == "no":
        verdict = "no"
    else:
        llm = get_chat_llm(temperature=0).with_structured_output(_Verdict)
        v: _Verdict = await llm.ainvoke(
            [SystemMessage(content=_CLASSIFY_SYSTEM), last_human]
        )
        verdict = (v.verdict or "unclear").strip().lower()
        if verdict not in {"yes", "no", "question", "unclear"}:
            verdict = "unclear"

    if verdict == "yes":
        return {
            "slots": {"happy": True, "gate_attempts": attempts + 1},
            "current_node": "guide.happy_gate",
        }
    if verdict == "no":
        return {
            "slots": {"happy": False, "gate_attempts": attempts + 1},
            "current_node": "guide.happy_gate",
        }

    if verdict == "question":
        return await _answer_and_reprompt(state, last_human, slots, lang)

    # Unclear. Re-ask once, then fall through on the next attempt.
    if attempts == 0:
        return {
            "messages": [
                AIMessage(content=t("ghg_reask", lang))
            ],
            "slots": {"gate_attempts": attempts + 1},
            "current_node": "guide.happy_gate",
        }

    # Two unclear answers in a row — route to human to avoid loops.
    return {
        "slots": {"happy": False, "gate_attempts": attempts + 1},
        "current_node": "guide.happy_gate",
    }


async def _answer_and_reprompt(
    state: AgentState,
    last_human: HumanMessage,
    slots: dict,
    lang: str | None,
) -> dict:
    """The user is asking about the candidates rather than picking.

    Answer the question (grounded on `slots.candidates`) and re-emit
    the gate card so the next turn can still land on the yes/no path.
    `happy` stays None and `gate_attempts` is not bumped — a question
    is a normal turn, not a failed gate attempt.
    """
    candidates = slots.get("candidates") or []
    candidates_json = json.dumps(candidates, ensure_ascii=False, default=str)

    llm = get_chat_llm(temperature=0.2)
    reply = await llm.ainvoke(
        [
            SystemMessage(
                content=_ANSWER_SYSTEM.format(candidates_json=candidates_json)
                + language_instruction(lang)
            ),
            last_human,
        ]
    )
    answer = (getattr(reply, "content", "") or "").strip()
    messages: list = []
    if answer:
        messages.append(AIMessage(content=answer))
    # Always follow up with the gate prompt so the UI shows yes/no again
    # — even if the LLM already nudged in prose, the structured card is
    # what the widget keys off of for the chip-click fast path.
    return {
        "messages": messages or [AIMessage(content=t("ghg_anything_else", lang))],
        "cards": [
            {
                "kind": "gate",
                "payload": {
                    "question": t("ghg_anything_else", lang),
                    "yes_label": t("gate_yes_works", lang),
                    "no_label": t("gate_no_fit", lang),
                },
            }
        ],
        "current_node": "guide.happy_gate.question",
    }
