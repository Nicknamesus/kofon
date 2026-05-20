"""Outcome handlers — the only thing outcome nodes import.

Each handler:
  1. Resolves a `Division` from the routing matrix.
  2. Builds a provider-agnostic payload from agent state.
  3. Persists an `Rfq` / `Ticket` row first (internal source of truth).
  4. Calls the configured CRM provider, recording the attempt in
     `crm_calls`. Updates the Rfq/Ticket with the returned record id.
  5. Sends a division notification email via the configured email
     provider, recording the attempt in `email_calls`.
  6. Updates the parent `Conversation` row (outcome, ticket_id, rfq_id,
     division_code).

Errors are swallowed by default (`settings.sideeffects_soft_fail`) — a
provider outage should never break the user's terminal card. The audit
rows let ops re-drive the failures later.

Return value is the diff to merge back into agent state (record ids,
division code) so outcome nodes can surface them on the terminal card.
"""

from __future__ import annotations

import logging
import traceback
from dataclasses import asdict
from typing import Any

from sqlalchemy import update

from app import crm as crm_module
from app import mail as mail_module
from app.agent.state import AgentState
from app.config import get_settings
from app.crm import (
    ActivityPayload,
    CrmResult,
    LeadPayload,
    TicketPayload,
)
from app.db import SessionLocal
from app.mail import EmailMessage, EmailResult
from app.models import Conversation, CrmCall, EmailCall, Rfq, Ticket
from app.sideeffects.rfq import (
    build_lead_payload,
    build_ticket_payload,
)
from app.sideeffects.routing import resolve_division

log = logging.getLogger(__name__)


# ---------------- public handlers ----------------


async def handle_sell(state: AgentState) -> dict[str, Any]:
    """outcome_sell side effects. Returns a slots-shaped diff."""
    conversation_id = await _conversation_id_for(state)
    if conversation_id is None:
        return {}

    slots = state.get("slots") or {}
    family = _resolve_family(state)
    division = resolve_division(state.get("flow") or "guide", family)

    payload = build_lead_payload(
        state, conversation_id=conversation_id, division=division
    )

    async with SessionLocal() as session:
        # Insert Rfq first so we always have an internal record even if
        # the CRM call dies.
        rfq = Rfq(
            conversation_id=conversation_id,
            sku=payload.sku,
            product_family=payload.product_family,
            division_code=division.code,
            payload=_jsonable(payload),
            crm_provider=_provider_name(),
            status="created",
        )
        session.add(rfq)
        await session.flush()
        rfq_id = rfq.id

        result = await _safe_crm_call(
            session,
            conversation_id=conversation_id,
            operation="create_lead",
            payload=payload,
            call=lambda p: crm_module.get_provider().create_lead(p),
        )
        if result and result.record_id:
            rfq.crm_record_id = result.record_id
            rfq.status = "synced"

        # Notify the division (best-effort).
        if division.inbox:
            await _safe_email_send(
                session,
                conversation_id=conversation_id,
                msg=EmailMessage(
                    to_address=division.inbox,
                    subject=_lead_subject(payload),
                    body=_lead_email_body(payload, rfq_id=rfq_id),
                    kind="rfq_notify",
                ),
            )

        await session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(
                outcome="sell",
                rfq_id=rfq_id,
                division_code=division.code,
            )
        )
        await session.commit()

    return {
        "slots": {
            "sideeffects": {
                "rfq_id": rfq_id,
                "crm_record_id": result.record_id if result else None,
                "division_code": division.code,
            }
        }
    }


async def handle_human_handoff(
    state: AgentState,
    *,
    reason: str = "user_requested",
    priority: str = "normal",
) -> dict[str, Any]:
    conversation_id = await _conversation_id_for(state)
    if conversation_id is None:
        return {}

    family = _resolve_family(state)
    division = resolve_division(state.get("flow") or "other", family)

    payload = build_ticket_payload(
        state,
        conversation_id=conversation_id,
        division=division,
        reason=reason,
        priority=priority,
    )

    async with SessionLocal() as session:
        ticket = Ticket(
            conversation_id=conversation_id,
            reason=reason,
            division_code=division.code,
            payload=_jsonable(payload),
            crm_provider=_provider_name(),
            status="open",
        )
        session.add(ticket)
        await session.flush()
        ticket_id = ticket.id

        result = await _safe_crm_call(
            session,
            conversation_id=conversation_id,
            operation="create_ticket",
            payload=payload,
            call=lambda p: crm_module.get_provider().create_ticket(p),
        )
        if result and result.record_id:
            ticket.crm_record_id = result.record_id
            ticket.status = "synced"

        if division.inbox:
            await _safe_email_send(
                session,
                conversation_id=conversation_id,
                msg=EmailMessage(
                    to_address=division.inbox,
                    subject=_ticket_subject(payload),
                    body=_ticket_email_body(payload, ticket_id=ticket_id),
                    kind="handoff_notify",
                ),
            )

        await session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(
                outcome="human_handoff",
                ticket_id=str(ticket_id),
                division_code=division.code,
            )
        )
        await session.commit()

    return {
        "slots": {
            "sideeffects": {
                "ticket_id": ticket_id,
                "crm_record_id": result.record_id if result else None,
                "division_code": division.code,
            }
        }
    }


async def handle_resolved(state: AgentState) -> dict[str, Any]:
    """outcome_resolved — log activity only (no CRM record creation)."""
    conversation_id = await _conversation_id_for(state)
    if conversation_id is None:
        return {}

    slots = state.get("slots") or {}
    postsales = slots.get("postsales") or {}
    label = postsales.get("candidate_problem_label") or "issue"
    sol = postsales.get("candidate_solution") or {}

    payload = ActivityPayload(
        conversation_id=conversation_id,
        session_uuid=_session_uuid_strict(state),
        summary=f"Chatbot resolved: {label}",
        body=f"Solution surfaced: {sol.get('summary') or '(no summary)'}",
    )

    async with SessionLocal() as session:
        await _safe_crm_call(
            session,
            conversation_id=conversation_id,
            operation="log_activity",
            payload=payload,
            call=lambda p: crm_module.get_provider().log_activity(p),
        )
        await session.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(outcome="resolved")
        )
        await session.commit()
    return {}


# ---------------- internal: provider wrappers ----------------


async def _safe_crm_call(
    session,
    *,
    conversation_id: int | None,
    operation: str,
    payload: object,
    call,
) -> CrmResult | None:
    """Run a CRM call inside an audit-row. Soft-fails per settings."""
    provider_name = _provider_name()
    req_json = _jsonable(payload)
    soft = get_settings().sideeffects_soft_fail

    try:
        result: CrmResult = await call(payload)
    except Exception as exc:  # noqa: BLE001
        log.warning(
            "CRM call failed (provider=%s op=%s): %s",
            provider_name, operation, exc,
        )
        session.add(CrmCall(
            conversation_id=conversation_id,
            provider=provider_name,
            operation=operation,
            request=req_json,
            response=None,
            status="error",
            error=f"{exc.__class__.__name__}: {exc}\n{traceback.format_exc()[:2000]}",
        ))
        if not soft:
            raise
        return None

    session.add(CrmCall(
        conversation_id=conversation_id,
        provider=provider_name,
        operation=operation,
        request=req_json,
        response=result.raw_response,
        status="ok",
        error=None,
    ))
    return result


async def _safe_email_send(
    session,
    *,
    conversation_id: int | None,
    msg: EmailMessage,
) -> EmailResult | None:
    provider = mail_module.get_provider()
    soft = get_settings().sideeffects_soft_fail
    try:
        result = await provider.send(msg)
    except Exception as exc:  # noqa: BLE001
        log.warning("Email send failed (provider=%s kind=%s): %s",
                    provider.name, msg.kind, exc)
        session.add(EmailCall(
            conversation_id=conversation_id,
            provider=provider.name,
            to_address=msg.to_address,
            subject=msg.subject,
            body=msg.body,
            kind=msg.kind,
            status="error",
            error=f"{exc.__class__.__name__}: {exc}",
        ))
        if not soft:
            raise
        return None

    session.add(EmailCall(
        conversation_id=conversation_id,
        provider=provider.name,
        to_address=msg.to_address,
        subject=msg.subject,
        body=msg.body,
        kind=msg.kind,
        status="ok",
        error=None,
    ))
    return result


# ---------------- internal: helpers ----------------


def _provider_name() -> str:
    try:
        return crm_module.get_provider().name
    except Exception:  # noqa: BLE001
        return "unknown"


async def _conversation_id_for(state: AgentState) -> int | None:
    """Outcome handlers need a `conversations.id`. The SSE layer upserts
    the row before the graph runs and injects the id into state — fast
    path is the value already in state. As a fallback, look up by
    session_uuid; if even that fails we skip (no audit possible)."""
    cid = state.get("conversation_id")
    if isinstance(cid, int):
        return cid

    sid = state.get("session_uuid")
    if not sid:
        log.warning("sideeffects: no session_uuid in state — skipping")
        return None

    from sqlalchemy import select
    async with SessionLocal() as session:
        row = await session.execute(
            select(Conversation.id).where(Conversation.session_uuid == sid)
        )
        result = row.scalar_one_or_none()
        return result


def _resolve_family(state: AgentState) -> str | None:
    slots = state.get("slots") or {}
    cands = slots.get("candidates") or []
    if cands and cands[0].get("product_type_code"):
        return cands[0]["product_type_code"]
    postsales = slots.get("postsales") or {}
    if postsales.get("product_type_code"):
        return postsales["product_type_code"]
    customize = slots.get("customize") or {}
    if customize.get("family_code"):
        return customize["family_code"]
    filters = slots.get("filters") or {}
    return filters.get("family")


def _session_uuid_strict(state: AgentState):
    from uuid import UUID, uuid4
    sid = state.get("session_uuid")
    if isinstance(sid, UUID):
        return sid
    if isinstance(sid, str):
        return UUID(sid)
    return uuid4()


def _jsonable(obj: object) -> dict[str, Any]:
    """asdict() for dataclasses, str-coercion for non-JSON-native values."""
    try:
        raw = asdict(obj)  # type: ignore[arg-type]
    except TypeError:
        raw = dict(getattr(obj, "__dict__", {}))
    return _coerce(raw)


def _coerce(value: Any) -> Any:
    from uuid import UUID
    if isinstance(value, dict):
        return {k: _coerce(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_coerce(v) for v in value]
    if isinstance(value, UUID):
        return str(value)
    return value


def _lead_subject(p: LeadPayload) -> str:
    parts = ["[Chatbot] Sales-qualified lead"]
    if p.contact_company:
        parts.append(p.contact_company)
    if p.sku:
        parts.append(p.sku)
    return " — ".join(parts)


def _lead_email_body(p: LeadPayload, *, rfq_id: int) -> str:
    return (
        f"<p>The chatbot has produced a sales-qualified lead.</p>"
        f"<ul>"
        f"<li><b>Internal RFQ:</b> #{rfq_id}</li>"
        f"<li><b>Division:</b> {p.division_code}</li>"
        f"<li><b>SKU:</b> {p.sku or '—'}</li>"
        f"<li><b>Family:</b> {p.product_family or '—'}</li>"
        f"<li><b>Contact:</b> {p.contact_email or '(not captured)'} "
        f"/ {p.contact_company or '(unknown company)'}</li>"
        f"<li><b>Session:</b> {p.session_uuid}</li>"
        f"</ul>"
        f"<p><b>Notes:</b><br/>{p.notes.replace(chr(10), '<br/>')}</p>"
        f"<p><b>Transcript:</b><br/>"
        + "<br/>".join(f"[{t.role}] {t.text}" for t in p.transcript[-20:])
        + "</p>"
    )


def _ticket_subject(p: TicketPayload) -> str:
    parts = [f"[Chatbot] Escalation ({p.priority})"]
    if p.contact_company:
        parts.append(p.contact_company)
    if p.sku:
        parts.append(p.sku)
    return " — ".join(parts)


def _ticket_email_body(p: TicketPayload, *, ticket_id: int) -> str:
    return (
        f"<p>The chatbot escalated a conversation.</p>"
        f"<ul>"
        f"<li><b>Internal ticket:</b> #{ticket_id}</li>"
        f"<li><b>Division:</b> {p.division_code}</li>"
        f"<li><b>Reason:</b> {p.reason}</li>"
        f"<li><b>Priority:</b> {p.priority}</li>"
        f"<li><b>SKU:</b> {p.sku or '—'}</li>"
        f"<li><b>Family:</b> {p.product_family or '—'}</li>"
        f"<li><b>Contact:</b> {p.contact_email or '(not captured)'} "
        f"/ {p.contact_company or '(unknown company)'}</li>"
        f"<li><b>Session:</b> {p.session_uuid}</li>"
        f"</ul>"
        f"<p><b>Notes:</b><br/>{p.notes.replace(chr(10), '<br/>')}</p>"
        f"<p><b>Transcript:</b><br/>"
        + "<br/>".join(f"[{t.role}] {t.text}" for t in p.transcript[-20:])
        + "</p>"
    )
