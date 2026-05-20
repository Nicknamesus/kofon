"""CRM provider — pluggable Protocol with multiple backends.

Why pluggable: Kofon picked Zoho CRM for the demo but the client may
switch to Salesforce, a Chinese-native CRM, or an in-house system. The
agent should not care which one is wired underneath. Same pattern as
`app/embeddings.py`.

Configure via env (see `app/config.py`):

    CRM_PROVIDER=log        # default — writes only to crm_calls table.
    CRM_PROVIDER=zoho       # requires ZOHO_* env vars (see app.crm.zoho).

The provider Protocol is intentionally small (3 operations). Anything
larger lives in the orchestration layer (`app.sideeffects`) so that
swapping a provider is a single-file change.

Provider is a process-wide singleton; first call constructs it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID


# ---------------- payloads ----------------


@dataclass
class TranscriptTurn:
    """One turn from the conversation log. Provider-agnostic."""

    role: str         # 'user' | 'bot' | 'system'
    content_type: str # 'text' | 'card' | 'gate_choice' | ...
    text: str         # human-readable rendering (cards flattened to a summary)


@dataclass
class LeadPayload:
    """What outcome_sell hands to a CRM. Field names are CRM-neutral —
    each adapter maps them to its own schema (Zoho Lead/Deal, Salesforce
    Opportunity, etc.)."""

    conversation_id: int
    session_uuid: UUID
    contact_email: str | None
    contact_company: str | None
    contact_language: str
    sku: str | None
    product_name: str | None
    product_family: str | None
    quantity: int | None
    division_code: str | None
    division_inbox: str | None
    notes: str
    transcript: list[TranscriptTurn] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class TicketPayload:
    """What outcome_human hands to a CRM."""

    conversation_id: int
    session_uuid: UUID
    contact_email: str | None
    contact_company: str | None
    contact_language: str
    reason: str
    sku: str | None
    product_family: str | None
    division_code: str | None
    division_inbox: str | None
    priority: str  # 'low' | 'normal' | 'high'
    notes: str
    transcript: list[TranscriptTurn] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class ActivityPayload:
    """What outcome_resolved (and other in-flight nodes) can log against
    an existing CRM record. Used for 'issue resolved by chatbot' notes."""

    conversation_id: int
    session_uuid: UUID
    summary: str
    body: str
    related_record_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class CrmResult:
    """Provider return value. Orchestrator persists the audit row."""

    record_id: str | None
    raw_response: dict[str, Any]


# ---------------- Protocol ----------------


class CrmProvider(Protocol):
    name: str

    async def create_lead(self, payload: LeadPayload) -> CrmResult: ...

    async def create_ticket(self, payload: TicketPayload) -> CrmResult: ...

    async def log_activity(self, payload: ActivityPayload) -> CrmResult: ...


# ---------------- factory ----------------


_provider: CrmProvider | None = None


def get_provider() -> CrmProvider:
    """Return the configured provider (cached after first call)."""
    global _provider
    if _provider is not None:
        return _provider

    from app.config import get_settings

    name = (get_settings().crm_provider or "log").lower()
    if name == "log":
        from app.crm.log import LogCrmProvider
        _provider = LogCrmProvider()
    elif name == "zoho":
        from app.crm.zoho import ZohoCrmProvider
        _provider = ZohoCrmProvider()
    else:
        raise ValueError(
            f"Unknown CRM_PROVIDER={name!r}. "
            "Use 'log' or 'zoho' (or add a new adapter under app/crm/)."
        )
    return _provider


def reset_provider_cache() -> None:
    """Tests/smokes — drop the cached instance so a new env can take effect."""
    global _provider
    _provider = None
