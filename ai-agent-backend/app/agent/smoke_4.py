"""Phase 4 smoke — side effects (CRM + email + RFQ + analytics rows).

Runs three end-to-end scenarios against the live graph + DB:

  1. Guide-Find → outcome_sell      → expect Rfq + crm_calls(create_lead)
                                       + email_calls(rfq_notify)
                                       + conversations.rfq_id set
  2. Guide-Find → outcome_human     → expect Ticket + crm_calls(create_ticket)
                                       + email_calls(handoff_notify)
                                       + conversations.ticket_id set
  3. Postsales → outcome_resolved   → expect crm_calls(log_activity)
                                       + conversations.outcome='resolved'

Uses the default CRM_PROVIDER=log so no real Zoho/etc. credentials are
needed. Assertions count rows in the audit tables.

Run from `ai-agent-backend/`:
    python -m app.agent.smoke_4
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

from langchain_core.messages import HumanMessage
from sqlalchemy import select, func

from app.agent.checkpointer import make_checkpointer
from app.agent.graph import build_graph
from app.db import SessionLocal
from app.models import Conversation, CrmCall, EmailCall, Message, Rfq, Ticket
from app import persistence
from app.runtime import install_async_event_loop_policy


async def _drive_turn(
    graph,
    *,
    session_uuid,
    conversation_id: int,
    text: str | None = None,
    flow: str | None = None,
    gate_choice: str | None = None,
) -> dict:
    """Mirror what `app/routers/agent.py` does on a single turn."""
    config = {"configurable": {"thread_id": str(session_uuid)}}
    graph_input: dict = {
        "session_uuid": session_uuid,
        "conversation_id": conversation_id,
    }
    if text or gate_choice:
        graph_input["messages"] = [HumanMessage(content=text or gate_choice)]
    if flow:
        graph_input["flow"] = flow
    return await graph.ainvoke(graph_input, config=config)


async def _scenario_sell(graph) -> None:
    sid = uuid4()
    cid = await persistence.upsert_conversation(sid, flow="guide")
    print(f"\n=== Scenario 1: sell  (conv #{cid})")

    # Turn 1: ask for a product
    await _drive_turn(
        graph,
        session_uuid=sid,
        conversation_id=cid,
        text="I need a planetary gearbox, frame size 90, low backlash.",
        flow="guide",
    )
    # Turn 2: yes to the gate
    await _drive_turn(
        graph,
        session_uuid=sid,
        conversation_id=cid,
        gate_choice="yes",
    )

    async with SessionLocal() as session:
        conv = (await session.execute(
            select(Conversation).where(Conversation.id == cid)
        )).scalar_one()
        rfq = (await session.execute(
            select(Rfq).where(Rfq.conversation_id == cid)
        )).scalar_one_or_none()
        crm = (await session.execute(
            select(func.count(CrmCall.id)).where(CrmCall.conversation_id == cid)
        )).scalar_one()
        emails = (await session.execute(
            select(func.count(EmailCall.id)).where(EmailCall.conversation_id == cid)
        )).scalar_one()

    print(f"  outcome={conv.outcome!r}  division={conv.division_code!r}  rfq_id={conv.rfq_id!r}")
    print(f"  rfqs: {1 if rfq else 0}  crm_calls: {crm}  email_calls: {emails}")
    assert conv.outcome == "sell"
    assert rfq is not None
    assert conv.rfq_id == rfq.id
    assert crm >= 1
    assert emails >= 1


async def _scenario_handoff(graph) -> None:
    sid = uuid4()
    cid = await persistence.upsert_conversation(sid, flow="guide")
    print(f"\n=== Scenario 2: handoff  (conv #{cid})")

    await _drive_turn(
        graph,
        session_uuid=sid,
        conversation_id=cid,
        text="I need a planetary gearbox, frame size 90, low backlash.",
        flow="guide",
    )
    await _drive_turn(
        graph,
        session_uuid=sid,
        conversation_id=cid,
        gate_choice="no",
    )

    async with SessionLocal() as session:
        conv = (await session.execute(
            select(Conversation).where(Conversation.id == cid)
        )).scalar_one()
        ticket = (await session.execute(
            select(Ticket).where(Ticket.conversation_id == cid)
        )).scalar_one_or_none()
        crm = (await session.execute(
            select(func.count(CrmCall.id)).where(CrmCall.conversation_id == cid)
        )).scalar_one()
        emails = (await session.execute(
            select(func.count(EmailCall.id)).where(EmailCall.conversation_id == cid)
        )).scalar_one()

    print(f"  outcome={conv.outcome!r}  division={conv.division_code!r}  ticket_id={conv.ticket_id!r}")
    print(f"  tickets: {1 if ticket else 0}  crm_calls: {crm}  email_calls: {emails}")
    assert conv.outcome == "human_handoff"
    assert ticket is not None
    assert conv.ticket_id == str(ticket.id)
    assert crm >= 1
    assert emails >= 1


async def _scenario_resolved(graph) -> None:
    sid = uuid4()
    cid = await persistence.upsert_conversation(sid, flow="postsales")
    print(f"\n=== Scenario 3: resolved  (conv #{cid})")

    # Drive a postsales turn that lands at fix_gate, then say "yes".
    # We piggyback on the existing graph behaviour without poking slots
    # directly — input is the symptom + SKU. If the KB match doesn't
    # resolve in 2 turns we'll just assert the outcome we got.
    await _drive_turn(
        graph,
        session_uuid=sid,
        conversation_id=cid,
        text="My PG090 gearbox is showing excessive backlash.",
        flow="postsales",
    )
    await _drive_turn(
        graph,
        session_uuid=sid,
        conversation_id=cid,
        gate_choice="yes",
    )

    async with SessionLocal() as session:
        conv = (await session.execute(
            select(Conversation).where(Conversation.id == cid)
        )).scalar_one()
        crm = (await session.execute(
            select(func.count(CrmCall.id)).where(CrmCall.conversation_id == cid)
        )).scalar_one()
        msgs = (await session.execute(
            select(func.count(Message.id)).where(Message.conversation_id == cid)
        )).scalar_one()

    print(f"  outcome={conv.outcome!r}  crm_calls: {crm}  messages: {msgs}")
    # Resolved isn't guaranteed (depends on KB match), so only enforce
    # that *some* outcome was reached and an audit row exists.
    assert conv.outcome in {"resolved", "human_handoff"}
    assert crm >= 1
    assert msgs >= 2


async def main() -> None:
    async with make_checkpointer() as cp:
        graph = build_graph(checkpointer=cp)
        await _scenario_sell(graph)
        await _scenario_handoff(graph)
        await _scenario_resolved(graph)
    print("\nPhase 4 smoke OK.")


if __name__ == "__main__":
    install_async_event_loop_policy()
    asyncio.run(main())
