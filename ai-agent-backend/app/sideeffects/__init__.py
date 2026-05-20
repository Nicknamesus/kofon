"""Side-effects orchestration — Phase 4.

This package is the single seam between the agent's terminal nodes and
the outside world (CRM, email, RFQ payload generation). The outcome
nodes call one of `handle_sell`, `handle_human_handoff`,
`handle_resolved` and that's it — provider swap (Zoho → Salesforce →
other) is a one-file change in `app/crm/`.

Design:

- The CRM and email providers are bare Protocols (see `app/crm/` and
  `app/mail/`) — they do one thing and return a result.
- This module wraps every call with audit-row persistence (`crm_calls`
  / `email_calls`) and swallows errors per `SIDEEFFECTS_SOFT_FAIL`
  (default True) so the user-facing flow never breaks.
- The `RFQ` and `Ticket` rows are written here too — they survive even
  if the external provider fails, so we always have an internal record.

Future white-label extraction: this is the file that becomes a
`SideEffects` service class. For now it's module-level functions
because that's the fastest thing that works.
"""

from __future__ import annotations

from app.sideeffects.handlers import (
    handle_human_handoff,
    handle_resolved,
    handle_sell,
)
from app.sideeffects.routing import Division, resolve_division
from app.sideeffects.rfq import build_lead_payload, build_ticket_payload

__all__ = [
    "handle_sell",
    "handle_human_handoff",
    "handle_resolved",
    "Division",
    "resolve_division",
    "build_lead_payload",
    "build_ticket_payload",
]
