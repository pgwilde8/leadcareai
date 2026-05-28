"""Twilio REST API (outbound SMS only; no Messaging Service in V1)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class TwilioConfigError(Exception):
    """Missing or invalid Twilio configuration."""


class TwilioSendError(Exception):
    """Twilio API rejected or failed the send."""


@dataclass(frozen=True)
class SendSmsResult:
    sid: str
    status: str


def send_sms(
    to_phone: str,
    body: str,
    *,
    from_phone: str | None = None,
    business_id: Any = None,
    lead_id: Any = None,
    client: Any = None,
) -> SendSmsResult:
    """
    Send SMS via Twilio REST API using TWILIO_PHONE_NUMBER (or explicit from_phone).

    business_id / lead_id are accepted for call-site context only (logging metadata).
  """
    settings = get_settings()
    to_trimmed = to_phone.strip()
    body_trimmed = body.strip()
    if not to_trimmed:
        raise TwilioConfigError("Recipient phone number must not be empty")
    if not body_trimmed:
        raise TwilioConfigError("SMS body must not be empty")

    from_number = (from_phone or settings.twilio_phone_number or "").strip()
    if not from_number:
        raise TwilioConfigError("TWILIO_PHONE_NUMBER is not configured")

    account_sid = (settings.twilio_account_sid or "").strip()
    auth_token = settings.twilio_auth_token
    if not account_sid or not auth_token:
        raise TwilioConfigError("Twilio credentials are not configured")

    log_extra = {
        "to_phone": to_trimmed,
        "from_phone": from_number,
        "business_id": str(business_id) if business_id else None,
        "lead_id": str(lead_id) if lead_id else None,
    }
    logger.info("Sending Twilio SMS", extra=log_extra)

    try:
        if client is None:
            from twilio.rest import Client

            client = Client(account_sid, auth_token)

        message = client.messages.create(
            from_=from_number,
            to=to_trimmed,
            body=body_trimmed,
        )
    except TwilioConfigError:
        raise
    except Exception as exc:
        logger.exception(
            "Twilio SMS send failed",
            extra={**log_extra, "error_type": type(exc).__name__},
        )
        raise TwilioSendError("Twilio SMS send failed") from exc

    sid = message.sid or ""
    status = message.status or "queued"
    logger.info(
        "Twilio SMS sent",
        extra={**log_extra, "provider_sid": sid, "provider_status": status},
    )
    return SendSmsResult(sid=sid, status=status)
