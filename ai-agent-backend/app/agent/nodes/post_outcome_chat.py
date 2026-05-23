"""post_outcome_chat — keep talking after the flow has terminated.

The graph's flow nodes finish at an outcome (`sell`, `human_handoff`,
`resolved`). The conversation is technically done — a human or sales rep
will follow up out-of-band — but the user may still want to ask a
question or add context. Dead-ending with "this conversation already
wrapped up" is rude.

This node handles any post-outcome turn: it reads the conversation
history plus the recorded outcome and answers conversationally with a
single LLM call. It never re-opens the flow or changes state.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, SystemMessage

from app.agent.llm import get_chat_llm
from app.agent.state import AgentState
from app.i18n import language_instruction, t


_BASE = (
    "You are Kofon's chat agent. The structured conversation already "
    "concluded with outcome={outcome}. A human teammate will follow up "
    "out-of-band. Your job now is to keep being helpful and friendly to "
    "anything else the user says.\n\n"
    "Rules:\n"
    "- Keep replies short (1–3 sentences).\n"
    "- Don't restart the diagnostic / sales flow or ask for SKUs again.\n"
    "- If the user adds detail about their problem, acknowledge it and "
    "tell them you've noted it for the engineer who'll be in touch.\n"
    "- If they ask a general question you can answer briefly, do so.\n"
    "- Don't promise specific timelines, prices, or shipping dates.\n"
    "- Never tell the user the conversation is over or to start a new one."
)


_OUTCOME_FLAVOR = {
    "human_handoff": (
        "An application engineer will reach out shortly. Anything the "
        "user adds now should be acknowledged as extra context that "
        "will reach the engineer."
    ),
    "sell": (
        "A sales engineer will follow up with a quote and lead time. "
        "Anything the user adds now is context for the sales handoff."
    ),
    "resolved": (
        "The user's reported issue was resolved. If they bring up a "
        "follow-up problem, answer briefly; only suggest opening a new "
        "chat if they explicitly want to start over."
    ),
}


async def run(state: AgentState) -> dict:
    outcome = state.get("outcome") or "human_handoff"
    messages = state.get("messages", [])
    lang = state.get("language")

    system = SystemMessage(
        content=(
            _BASE.format(outcome=outcome)
            + "\n\n"
            + _OUTCOME_FLAVOR.get(outcome, "")
            + language_instruction(lang)
        )
    )

    llm = get_chat_llm(temperature=0.3)
    try:
        reply = await llm.ainvoke([system, *messages])
        text = (getattr(reply, "content", "") or "").strip()
    except Exception:  # noqa: BLE001
        text = ""

    if not text:
        text = t("poc_fallback", lang)

    return {
        "messages": [AIMessage(content=text)],
        "current_node": "post_outcome_chat",
    }
