"""Zoho CRM adapter.

Implements `CrmProvider` against Zoho's REST API v6. Uses the OAuth
refresh-token grant: a long-lived refresh token (obtained once via the
Zoho Developer Console) is exchanged for short-lived access tokens at
runtime.

Region matters. Zoho runs separate data centers per region and the OAuth
+ API endpoints differ:

    region   accounts host          api host
    us       accounts.zoho.com      www.zohoapis.com
    eu       accounts.zoho.eu       www.zohoapis.eu
    in       accounts.zoho.in       www.zohoapis.in
    au       accounts.zoho.com.au   www.zohoapis.com.au
    jp       accounts.zoho.jp       www.zohoapis.jp
    cn       accounts.zoho.com.cn   www.zohoapis.com.cn   ← Kofon will likely use this

`ZOHO_REGION` env var selects the region; if `ZOHO_ACCOUNTS_URL` /
`ZOHO_API_URL` are set explicitly they win (handy for sandbox or proxy
setups).

Module mapping:

    LeadPayload    → Deals     (Phase 4 treats a confirmed sell as a Deal,
                                with Stage='Qualification'; can be flipped
                                to Leads later if sales process prefers it)
    TicketPayload  → Cases     (CRM Plus / Desk integration)
    ActivityPayload→ Tasks     (lightweight log)

Token caching: access tokens are kept in-process for ~50 minutes (Zoho
issues 1h tokens). On 401 the cache is invalidated and we retry once.
"""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.crm import (
    ActivityPayload,
    CrmResult,
    LeadPayload,
    TicketPayload,
)

_REGION_HOSTS = {
    "us": ("https://accounts.zoho.com", "https://www.zohoapis.com"),
    "eu": ("https://accounts.zoho.eu", "https://www.zohoapis.eu"),
    "in": ("https://accounts.zoho.in", "https://www.zohoapis.in"),
    "au": ("https://accounts.zoho.com.au", "https://www.zohoapis.com.au"),
    "jp": ("https://accounts.zoho.jp", "https://www.zohoapis.jp"),
    "cn": ("https://accounts.zoho.com.cn", "https://www.zohoapis.com.cn"),
}


class ZohoCrmProvider:
    name = "zoho"

    def __init__(self) -> None:
        from app.config import get_settings

        s = get_settings()
        self._client_id = s.zoho_client_id
        self._client_secret = s.zoho_client_secret
        self._refresh_token = s.zoho_refresh_token

        region = (s.zoho_region or "us").lower()
        default_accounts, default_api = _REGION_HOSTS.get(
            region, _REGION_HOSTS["us"]
        )
        self._accounts_url = s.zoho_accounts_url or default_accounts
        self._api_url = s.zoho_api_url or default_api

        if not (self._client_id and self._client_secret and self._refresh_token):
            raise RuntimeError(
                "CRM_PROVIDER=zoho requires ZOHO_CLIENT_ID, "
                "ZOHO_CLIENT_SECRET and ZOHO_REFRESH_TOKEN."
            )

        self._token: str | None = None
        self._token_expires_at: float = 0.0

    # ---------------- public api ----------------

    async def create_lead(self, payload: LeadPayload) -> CrmResult:
        """Create a Deal in Zoho. Most B2B teams want this as a Deal at
        Qualification stage; flip the `module` constant below to "Leads"
        if the sales team prefers the lead flow."""
        body = {
            "data": [
                {
                    "Deal_Name": _deal_name(payload),
                    "Stage": "Qualification",
                    "Description": payload.notes,
                    "Lead_Source": "Chatbot",
                    # Custom fields are dropped silently by Zoho if not defined
                    # on the org's layout — that's fine. Pre-create these in
                    # the Zoho admin to capture them: CF_SKU, CF_Family,
                    # CF_Division, CF_Session_UUID, CF_Transcript.
                    "CF_SKU": payload.sku,
                    "CF_Family": payload.product_family,
                    "CF_Division": payload.division_code,
                    "CF_Session_UUID": str(payload.session_uuid),
                    "CF_Transcript": _transcript_text(payload.transcript),
                    "Contact_Name": _contact_ref(payload),
                }
            ]
        }
        resp = await self._call("POST", "/crm/v6/Deals", json=body)
        record_id = _extract_record_id(resp)
        return CrmResult(record_id=record_id, raw_response=resp)

    async def create_ticket(self, payload: TicketPayload) -> CrmResult:
        """Create a Case in Zoho Desk-style sense (CRM Cases module)."""
        body = {
            "data": [
                {
                    "Subject": _case_subject(payload),
                    "Description": payload.notes,
                    "Priority": payload.priority.title(),
                    "Case_Origin": "Chat",
                    "Status": "Open",
                    "CF_Reason": payload.reason,
                    "CF_SKU": payload.sku,
                    "CF_Family": payload.product_family,
                    "CF_Division": payload.division_code,
                    "CF_Session_UUID": str(payload.session_uuid),
                    "CF_Transcript": _transcript_text(payload.transcript),
                }
            ]
        }
        resp = await self._call("POST", "/crm/v6/Cases", json=body)
        record_id = _extract_record_id(resp)
        return CrmResult(record_id=record_id, raw_response=resp)

    async def log_activity(self, payload: ActivityPayload) -> CrmResult:
        body = {
            "data": [
                {
                    "Subject": payload.summary,
                    "Description": payload.body,
                    "Status": "Completed",
                    "CF_Session_UUID": str(payload.session_uuid),
                    # When `related_record_id` is set, link the Task to a
                    # parent module record (Deal / Case). Module name must
                    # match the parent — left blank means a standalone Task.
                    "What_Id": payload.related_record_id,
                }
            ]
        }
        resp = await self._call("POST", "/crm/v6/Tasks", json=body)
        record_id = _extract_record_id(resp)
        return CrmResult(record_id=record_id, raw_response=resp)

    # ---------------- transport ----------------

    async def _call(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        _retry: bool = True,
    ) -> dict[str, Any]:
        token = await self._get_access_token()
        url = self._api_url.rstrip("/") + path
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.request(
                method,
                url,
                json=json,
                headers={"Authorization": f"Zoho-oauthtoken {token}"},
            )
        if resp.status_code == 401 and _retry:
            # Token expired or revoked — drop the cache and retry once.
            self._token = None
            self._token_expires_at = 0.0
            return await self._call(method, path, json=json, _retry=False)
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    async def _get_access_token(self) -> str:
        now = time.time()
        if self._token and now < self._token_expires_at:
            return self._token
        url = self._accounts_url.rstrip("/") + "/oauth/v2/token"
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                url,
                data={
                    "grant_type": "refresh_token",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "refresh_token": self._refresh_token,
                },
            )
        resp.raise_for_status()
        payload = resp.json()
        access = payload.get("access_token")
        if not access:
            raise RuntimeError(
                f"Zoho refresh-token grant did not return access_token: {payload}"
            )
        # Zoho issues 1h tokens; refresh 10m before expiry to be safe.
        expires_in = int(payload.get("expires_in", 3600))
        self._token = access
        self._token_expires_at = now + max(60, expires_in - 600)
        return access


# ---------------- helpers ----------------


def _deal_name(p: LeadPayload) -> str:
    parts = [p.contact_company or "Chatbot lead", p.sku or p.product_family or ""]
    return " — ".join(x for x in parts if x).strip(" —") or "Chatbot lead"


def _case_subject(p: TicketPayload) -> str:
    parts = [p.contact_company or "Chatbot escalation", p.sku or p.product_family or ""]
    return " — ".join(x for x in parts if x).strip(" —") or "Chatbot escalation"


def _contact_ref(p: LeadPayload) -> dict | None:
    """Zoho lookup field — set Contact_Name to {"name": ...} when we have
    a company; the layout's matching rule will create or find the contact.
    Returning None drops the key, which Zoho accepts."""
    if not (p.contact_email or p.contact_company):
        return None
    return {"name": p.contact_company or p.contact_email or ""}


def _transcript_text(turns: list) -> str:
    lines: list[str] = []
    for t in turns:
        role = getattr(t, "role", "?")
        text = getattr(t, "text", "")
        if text:
            lines.append(f"[{role}] {text}")
    return "\n".join(lines)[:32000]  # Zoho rejects giant text fields.


def _extract_record_id(resp: dict[str, Any]) -> str | None:
    try:
        return resp["data"][0]["details"]["id"]
    except (KeyError, IndexError, TypeError):
        return None
