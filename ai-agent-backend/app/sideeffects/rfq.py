"""Build provider-agnostic CRM payloads from agent state.

These functions are the *only* place that knows the shape of
`AgentState.slots`. CRM adapters take a `LeadPayload` / `TicketPayload`
and never look at the raw state. That keeps the agent free to evolve
its slot vocabulary without breaking every CRM integration.

Contact capture (email / company) isn't part of the Phase 3 flows yet
— see `BACKEND_PLAN.md` §7 Q4. When unset, the payload still flows
through and the CRM record is created in an "unknown contact" shape so
sales can chase it.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from app.agent.state import AgentState
from app.crm import LeadPayload, TicketPayload, TranscriptTurn
from app.sideeffects.routing import Division


# ---------------- public builders ----------------


def build_lead_payload(
    state: AgentState,
    *,
    conversation_id: int,
    division: Division,
) -> LeadPayload:
    """outcome_sell → LeadPayload."""
    slots = state.get("slots") or {}
    chosen = _first_candidate(slots)
    customize = slots.get("customize") or {}

    sku = chosen.get("sku") if chosen else None
    product_name = chosen.get("name") if chosen else None
    product_family = (
        (chosen.get("product_type_code") if chosen else None)
        or customize.get("family_code")
    )

    notes = _lead_notes(state, chosen=chosen, customize=customize)

    return LeadPayload(
        conversation_id=conversation_id,
        session_uuid=_session_uuid(state),
        contact_email=_contact(state, "email"),
        contact_company=_contact(state, "company"),
        contact_language=(state.get("slots") or {}).get("language") or "EN",
        sku=sku,
        product_name=product_name,
        product_family=product_family,
        quantity=_pluck(slots, "quantity"),
        division_code=division.code,
        division_inbox=division.inbox,
        notes=notes,
        transcript=_transcript(state),
        extra={
            "filters": slots.get("filters"),
            "customize": customize or None,
        },
    )


def build_ticket_payload(
    state: AgentState,
    *,
    conversation_id: int,
    division: Division,
    reason: str,
    priority: str = "normal",
) -> TicketPayload:
    """outcome_human → TicketPayload."""
    slots = state.get("slots") or {}
    postsales = slots.get("postsales") or {}
    chosen = _first_candidate(slots)

    sku = postsales.get("sku") or (chosen.get("sku") if chosen else None)
    product_family = (
        postsales.get("product_type_code")
        or (chosen.get("product_type_code") if chosen else None)
    )

    notes = _ticket_notes(state, postsales=postsales, chosen=chosen, reason=reason)

    return TicketPayload(
        conversation_id=conversation_id,
        session_uuid=_session_uuid(state),
        contact_email=_contact(state, "email"),
        contact_company=_contact(state, "company"),
        contact_language=slots.get("language") or "EN",
        reason=reason,
        sku=sku,
        product_family=product_family,
        division_code=division.code,
        division_inbox=division.inbox,
        priority=priority,
        notes=notes,
        transcript=_transcript(state),
        extra={
            "postsales": postsales or None,
            "candidate_solution": postsales.get("candidate_solution"),
        },
    )


# ---------------- helpers ----------------


def _first_candidate(slots: dict[str, Any]) -> dict[str, Any] | None:
    cands = slots.get("candidates") or []
    return cands[0] if cands else None


def _pluck(slots: dict[str, Any], key: str) -> Any:
    """Slot lookups that may live at top-level or nested under a flow key."""
    if key in slots:
        return slots[key]
    for flow_key in ("presales", "guide", "postsales"):
        sub = slots.get(flow_key) or {}
        if key in sub:
            return sub[key]
    return None


def _contact(state: AgentState, kind: str) -> str | None:
    slots = state.get("slots") or {}
    contact = slots.get("contact") or {}
    return contact.get(kind)


def _session_uuid(state: AgentState) -> UUID:
    sid = state.get("session_uuid")
    if isinstance(sid, UUID):
        return sid
    if isinstance(sid, str):
        return UUID(sid)
    # Should not happen — agent.py injects the UUID before the graph runs.
    # If it does, generate a sentinel so the payload still serializes.
    from uuid import uuid4
    return uuid4()


def _transcript(state: AgentState) -> list[TranscriptTurn]:
    out: list[TranscriptTurn] = []
    for msg in state.get("messages", []) or []:
        if isinstance(msg, HumanMessage):
            role = "user"
        elif isinstance(msg, AIMessage):
            role = "bot"
        elif isinstance(msg, SystemMessage):
            role = "system"
        else:
            role = "other"
        content = getattr(msg, "content", "")
        text = content if isinstance(content, str) else str(content)
        if not text.strip():
            continue
        out.append(TranscriptTurn(role=role, content_type="text", text=text))
    return out


def _lead_notes(
    state: AgentState,
    *,
    chosen: dict[str, Any] | None,
    customize: dict[str, Any],
) -> str:
    lines: list[str] = ["Chatbot-confirmed sales-qualified lead."]
    if chosen:
        lines.append(f"Picked SKU: {chosen.get('sku')} ({chosen.get('name')}).")
    if customize.get("active"):
        lines.append(f"Custom config request — family {customize.get('family_code')}.")
        modules = customize.get("modules") or {}
        if modules:
            lines.append("Modules: " + ", ".join(f"{k}={v}" for k, v in modules.items()))
    flow = state.get("flow")
    if flow:
        lines.append(f"Primary flow: {flow}.")
    return "\n".join(lines)


def _ticket_notes(
    state: AgentState,
    *,
    postsales: dict[str, Any],
    chosen: dict[str, Any] | None,
    reason: str,
) -> str:
    lines: list[str] = [f"Escalation reason: {reason}."]
    if postsales.get("sku"):
        lines.append(f"SKU: {postsales['sku']}.")
    elif chosen:
        lines.append(f"Discussed SKU: {chosen.get('sku')}.")
    if postsales.get("symptom_text"):
        lines.append(f"Symptom: {postsales['symptom_text']}")
    if postsales.get("candidate_problem_label"):
        lines.append(f"Suspected problem: {postsales['candidate_problem_label']}")
    cand_sol = postsales.get("candidate_solution") or {}
    if cand_sol.get("summary"):
        lines.append(f"Attempted fix: {cand_sol['summary']}")
    flow = state.get("flow")
    if flow:
        lines.append(f"Primary flow: {flow}.")
    return "\n".join(lines)
