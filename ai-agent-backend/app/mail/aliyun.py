"""Aliyun DirectMail adapter.

Aliyun DirectMail is the standard transactional email service inside the
GFW. The endpoint follows the Aliyun API style (signed query
parameters), region typically `cn-hangzhou`.

Required env (see `app/config.py`):
    ALIYUN_ACCESS_KEY_ID
    ALIYUN_ACCESS_KEY_SECRET
    ALIYUN_DM_REGION                e.g. 'cn-hangzhou' (default)
    ALIYUN_DM_ACCOUNT_NAME          the verified sender address
    ALIYUN_DM_FROM_ALIAS            display name (optional)

We sign with HMAC-SHA1 per the standard Aliyun signing rules; no SDK
dependency. If the call fails the orchestrator records the error in
`email_calls` and the conversation continues — email is best-effort.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
import urllib.parse
import uuid
from typing import Any

import httpx

from app.mail import EmailMessage, EmailResult


class AliyunDirectMailProvider:
    name = "aliyun"

    def __init__(self) -> None:
        from app.config import get_settings

        s = get_settings()
        self._access_key = s.aliyun_access_key_id
        self._secret = s.aliyun_access_key_secret
        self._region = s.aliyun_dm_region or "cn-hangzhou"
        self._account_name = s.aliyun_dm_account_name
        self._from_alias = s.aliyun_dm_from_alias or ""
        if not (self._access_key and self._secret and self._account_name):
            raise RuntimeError(
                "MAIL_PROVIDER=aliyun requires ALIYUN_ACCESS_KEY_ID, "
                "ALIYUN_ACCESS_KEY_SECRET and ALIYUN_DM_ACCOUNT_NAME."
            )
        self._endpoint = f"https://dm.{self._region}.aliyuncs.com/"

    async def send(self, msg: EmailMessage) -> EmailResult:
        params = {
            "Action": "SingleSendMail",
            "AccountName": self._account_name,
            "ReplyToAddress": "true" if msg.reply_to else "false",
            "AddressType": "1",
            "ToAddress": msg.to_address,
            "Subject": msg.subject,
            "HtmlBody": msg.body,
            "FromAlias": self._from_alias,
            # ---- common Aliyun signing params ----
            "Format": "JSON",
            "Version": "2015-11-23",
            "AccessKeyId": self._access_key,
            "SignatureMethod": "HMAC-SHA1",
            "Timestamp": time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
            ),
            "SignatureVersion": "1.0",
            "SignatureNonce": uuid.uuid4().hex,
        }
        if msg.reply_to:
            params["ReplyAddress"] = msg.reply_to

        params["Signature"] = _sign(params, self._secret)

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(self._endpoint, data=params)
        resp.raise_for_status()
        body: dict[str, Any] = resp.json() if resp.content else {}
        return EmailResult(
            provider_message_id=body.get("EnvId"),
            raw_response=body,
        )


def _sign(params: dict[str, str], secret: str) -> str:
    """Aliyun POP signing — HMAC-SHA1 of the canonicalized request."""
    items = sorted((k, v) for k, v in params.items() if v is not None)
    canonical = "&".join(
        f"{_percent(k)}={_percent(v)}" for k, v in items
    )
    string_to_sign = "POST&%2F&" + _percent(canonical)
    digest = hmac.new(
        (secret + "&").encode("utf-8"),
        string_to_sign.encode("utf-8"),
        hashlib.sha1,
    ).digest()
    return base64.b64encode(digest).decode("ascii")


def _percent(s: str) -> str:
    return urllib.parse.quote(str(s), safe="~")
