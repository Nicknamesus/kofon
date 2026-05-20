"""Email provider — pluggable Protocol with multiple backends.

The chatbot sends two kinds of email today:

  - `datasheet` — to the user, after they request a product datasheet
  - `handoff_notify` / `rfq_notify` — to the receiving division's inbox
    when outcome_human or outcome_sell fires

Provider choice is independent of the CRM. Defaults to a log-only
provider so the demo doesn't need credentials.

Configure via env (see `app/config.py`):

    MAIL_PROVIDER=log         # default — writes only to email_calls table.
    MAIL_PROVIDER=aliyun      # Aliyun DirectMail (China-native).

Package is named `mail` to avoid colliding with Python's stdlib `email`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class EmailMessage:
    to_address: str
    subject: str
    body: str
    kind: str  # 'datasheet' | 'handoff_notify' | 'rfq_notify'
    from_address: str | None = None
    reply_to: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class EmailResult:
    provider_message_id: str | None
    raw_response: dict[str, Any]


class EmailProvider(Protocol):
    name: str

    async def send(self, msg: EmailMessage) -> EmailResult: ...


_provider: EmailProvider | None = None


def get_provider() -> EmailProvider:
    global _provider
    if _provider is not None:
        return _provider

    from app.config import get_settings

    name = (get_settings().mail_provider or "log").lower()
    if name == "log":
        from app.mail.log import LogEmailProvider
        _provider = LogEmailProvider()
    elif name == "aliyun":
        from app.mail.aliyun import AliyunDirectMailProvider
        _provider = AliyunDirectMailProvider()
    else:
        raise ValueError(
            f"Unknown MAIL_PROVIDER={name!r}. "
            "Use 'log' or 'aliyun' (or add a new adapter under app/mail/)."
        )
    return _provider


def reset_provider_cache() -> None:
    global _provider
    _provider = None
