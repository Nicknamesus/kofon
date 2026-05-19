"""postsales.identify — slot-fill SKU + symptom.

Two slots:
  slots.postsales.sku            optional. If the customer doesn't know it,
                                 we proceed with `null` and rely purely on
                                 the symptom text for matching.
  slots.postsales.symptom        required. The free-form problem description.

Once we have a symptom, we hand off to `postsales.match_kb` for the
vector lookup. We don't block on SKU — many tickets land with "I'm not
sure, the label fell off" and the family-agnostic match is still useful.

Slot phase keys:
  slots.postsales.phase = 'collecting' | 'ready'
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, SystemMessage
from pydantic import BaseModel, Field

from app.agent.llm import get_chat_llm
from app.agent.state import AgentState

SYSTEM = """You are the Post-Sales identify node of a B2B motion-components
chatbot. Extract:
  - SKU (e.g. 'PG090-10-HP') — null if not yet provided.
  - SYMPTOM — a one-line description of the problem the customer is seeing,
    null if not yet provided.

Set ready=true once you have at least a symptom. SKU is helpful but
optional — don't block on it. If something's missing, set ready=false and
put ONE targeted question in follow_up_question.

Never invent a SKU or symptom the user didn't state.
"""


class _Extraction(BaseModel):
    sku: str | None = None
    symptom: str | None = None
    ready: bool = Field(description="True when at least a symptom is known.")
    follow_up_question: str | None = None


async def run(state: AgentState) -> dict:
    slots = state.get("slots") or {}
    postsales = dict(slots.get("postsales") or {})
    messages = state.get("messages", [])

    llm = get_chat_llm(temperature=0).with_structured_output(_Extraction)
    extraction: _Extraction = await llm.ainvoke(
        [SystemMessage(content=SYSTEM), *messages]
    )

    # Carry forward anything we already had; the LLM may only see new info.
    sku = extraction.sku or postsales.get("sku")
    symptom = extraction.symptom or postsales.get("symptom")

    if not symptom:
        question = (
            extraction.follow_up_question
            or "What's the symptom — what is the unit doing (or not doing)?"
        )
        return {
            "messages": [AIMessage(content=question)],
            "slots": {
                "postsales": {
                    **postsales,
                    "sku": sku,
                    "symptom": symptom,
                    "phase": "collecting",
                }
            },
            "current_node": "postsales.identify",
        }

    return {
        "slots": {
            "postsales": {
                **postsales,
                "sku": sku,
                "symptom": symptom,
                "phase": "ready",
            }
        },
        "current_node": "postsales.identify.ready",
    }
