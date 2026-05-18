"""entry_router — classifies free-form input into one of four primary flows.

Two paths:
  - Chip click: the frontend sets `state.flow` before invoking. Router
    is bypassed entirely by the START dispatch.
  - Free-form text: the router runs an LLM classifier.

The LLM here is narrow on purpose — it picks one of four codes and
returns nothing else. No tools, no slot-filling, no chat. Other nodes
take over from there.
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.agent.llm import get_chat_llm
from app.agent.state import AgentState

ALLOWED_FLOWS = {"presales", "guide", "postsales", "other"}

SYSTEM = """You route incoming user messages on a B2B motion-components
chatbot to one of four primary flows. Pick exactly one.

  presales   — User is exploring options and hasn't picked a product
               family. They describe an industry and an application
               (e.g. 'I need motion for a packaging dial').
  guide      — User knows roughly what they need; they're choosing
               between specific products or configuring a variant
               (e.g. 'show me planetary gearboxes under 5 arcmin').
  postsales  — User owns a Kofon product and is reporting a problem
               (e.g. 'my PG090 is leaking oil').
  other      — Anything else — greetings, questions about the company,
               jokes, off-topic.

Output a single code. No explanation.
"""


class _Route(BaseModel):
    flow: str = Field(description="One of: presales, guide, postsales, other")


async def run(state: AgentState) -> dict:
    last_human = next(
        (m for m in reversed(state.get("messages", []))
         if isinstance(m, HumanMessage)),
        None,
    )
    if last_human is None:
        return {"flow": "other", "current_node": "entry_router"}

    llm = get_chat_llm(temperature=0).with_structured_output(_Route)
    route: _Route = await llm.ainvoke(
        [SystemMessage(content=SYSTEM), last_human]
    )

    flow = route.flow.strip().lower()
    if flow not in ALLOWED_FLOWS:
        flow = "other"

    return {"flow": flow, "current_node": "entry_router"}
