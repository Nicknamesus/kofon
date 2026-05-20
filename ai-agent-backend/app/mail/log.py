"""Log-only email provider — default. Returns a synthetic message id and
never actually sends anything. The orchestrator records an `email_calls`
row alongside, so the audit trail is complete even without a real SMTP."""

from __future__ import annotations

import uuid

from app.mail import EmailMessage, EmailResult


class LogEmailProvider:
    name = "log"

    async def send(self, msg: EmailMessage) -> EmailResult:
        return EmailResult(
            provider_message_id=f"log-{uuid.uuid4().hex[:12]}",
            raw_response={
                "provider": self.name,
                "to": msg.to_address,
                "subject": msg.subject,
                "kind": msg.kind,
            },
        )
