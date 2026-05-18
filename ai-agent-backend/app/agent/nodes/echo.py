"""Phase 2a placeholder node — proves the LangGraph + DeepSeek + checkpointer
plumbing works end-to-end before we wire any real flow logic.

What it does: takes the latest user message, asks DeepSeek to echo it
back with a tiny acknowledgement. That's it. Will be deleted once the
real nodes (entry_router, guide.find, etc.) are in.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agent.llm import get_chat_llm
from app.agent.state import AgentState

SYSTEM = (
    "You are a smoke-test node for the Kofon chatbot backend. "
    "Repeat the user's last message back to them, prefixed with 'echo: '. "
    "Keep it under 30 words."
)


async def run(state: AgentState) -> dict:
    last_user = next(
        (m for m in reversed(state.get("messages", []))
         if isinstance(m, HumanMessage)),
        None,
    )
    if last_user is None:
        return {"messages": [AIMessage(content="echo: (no user message)")]}

    llm = get_chat_llm()
    response = await llm.ainvoke(
        [SystemMessage(content=SYSTEM), last_user]
    )
    return {
        "messages": [response],
        "current_node": "echo",
    }
