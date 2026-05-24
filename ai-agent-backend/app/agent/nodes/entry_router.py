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

from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from app.agent.llm import get_chat_llm, system_message
from app.agent.state import AgentState

ALLOWED_FLOWS = {"presales", "guide", "postsales", "other"}

# Deterministic customize-intent detector. The LLM also flags this, but
# these phrases are unambiguous enough that we should never miss them —
# missing them poisons routing because stale find_phase/happy slots end
# up sending the user to the gate instead of the configurator.
_CUSTOMIZE_PHRASES = (
    "custom build",
    "custom-build",
    "customize",
    "customise",
    "customized",
    "customised",
    "configure a",
    "configure my",
    "configure one",
    "spec a custom",
    "build me a custom",
    "build a custom",
    "make me a custom",
)


def _wants_customize(text: str) -> bool:
    t = (text or "").lower()
    return any(p in t for p in _CUSTOMIZE_PHRASES)

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

Also set `customize=true` ONLY when the user explicitly wants to build,
configure, or customize a product rather than pick a stock SKU — e.g.
"I want to custom build…", "configure a gearbox with…", "spec out a
custom unit", "build me one with…". For ordinary product searches
("show me planetary gearboxes", "find a 90 mm unit") leave it false.
`customize` is meaningful only when flow=guide; ignored otherwise.

Output the structured result. No prose.
"""


class _Route(BaseModel):
    flow: str = Field(description="One of: presales, guide, postsales, other")
    customize: bool = Field(
        default=False,
        description="True if the user explicitly asked to custom-build or "
        "configure a product (only meaningful when flow=guide).",
    )


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
        [system_message(SYSTEM), last_human]
    )

    flow = route.flow.strip().lower()
    if flow not in ALLOWED_FLOWS:
        flow = "other"

    # Hybrid customize-intent: LLM ∨ keyword. If keywords match we also
    # force flow=guide, since "I want to custom build a gearbox" should
    # never route to presales/other regardless of how the LLM classifies.
    keyword_customize = _wants_customize(str(last_human.content or ""))
    wants_customize = (flow == "guide" and route.customize) or keyword_customize
    if keyword_customize:
        flow = "guide"

    update: dict = {"flow": flow, "current_node": "entry_router"}
    if wants_customize:
        # Mirror the button-click path: wipe stale slots that could
        # short-circuit dispatch (find_phase=presented → happy_gate,
        # an old customize.phase=presented → happy_gate, etc.).
        update["slots"] = {
            "customize": {"active": True},
            "find_phase": None,
            "happy": None,
            "gate_attempts": 0,
            "candidates": None,
        }
    return update
