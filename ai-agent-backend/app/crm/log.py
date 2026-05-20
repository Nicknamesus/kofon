"""Log-only CRM provider — the default.

Returns synthetic record ids and never talks to a third party. The
orchestrator still writes a `crm_calls` audit row around every call, so
running with `CRM_PROVIDER=log` gives a complete record of what *would
have* been sent. Useful for the demo and CI.

Switching to a real provider (`zoho`, future `salesforce`) is one env
var — the orchestrator and the outcome nodes don't change.
"""

from __future__ import annotations

import uuid

from app.crm import (
    ActivityPayload,
    CrmResult,
    LeadPayload,
    TicketPayload,
)


def _synthetic_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


class LogCrmProvider:
    name = "log"

    async def create_lead(self, payload: LeadPayload) -> CrmResult:
        return CrmResult(
            record_id=_synthetic_id("lead"),
            raw_response={"provider": self.name, "echo": _summary(payload)},
        )

    async def create_ticket(self, payload: TicketPayload) -> CrmResult:
        return CrmResult(
            record_id=_synthetic_id("ticket"),
            raw_response={"provider": self.name, "echo": _summary(payload)},
        )

    async def log_activity(self, payload: ActivityPayload) -> CrmResult:
        return CrmResult(
            record_id=_synthetic_id("activity"),
            raw_response={"provider": self.name, "summary": payload.summary},
        )


def _summary(payload: object) -> dict:
    """Slim dict shown in raw_response — no transcript, just headline fields."""
    if isinstance(payload, LeadPayload):
        return {
            "kind": "lead",
            "sku": payload.sku,
            "product_family": payload.product_family,
            "division_code": payload.division_code,
            "contact_email": payload.contact_email,
        }
    if isinstance(payload, TicketPayload):
        return {
            "kind": "ticket",
            "reason": payload.reason,
            "division_code": payload.division_code,
            "priority": payload.priority,
            "contact_email": payload.contact_email,
        }
    return {}
