"""SMTP email helpers shared across services."""

from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmailSendResult:
    status: str  # sent | failed | skipped
    error: str | None = None


def smtp_configured() -> bool:
    settings = get_settings()
    return bool(settings.smtp_host and settings.smtp_from_email)


def send_email(*, to_email: str, subject: str, body: str) -> EmailSendResult:
    """Send a plain-text email via SMTP."""
    settings = get_settings()
    if not smtp_configured():
        logger.info("Email skipped (SMTP not configured): to=%s subject=%s", to_email, subject)
        return EmailSendResult(status="skipped", error="SMTP not configured")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from_email
    msg["To"] = to_email
    msg.set_content(body)

    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            if settings.smtp_username and settings.smtp_password:
                smtp.starttls()
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(msg)
        logger.info("Email sent to=%s subject=%s", to_email, subject)
        return EmailSendResult(status="sent")
    except Exception as exc:
        logger.exception("Email failed to=%s", to_email)
        return EmailSendResult(status="failed", error=str(exc)[:500])
