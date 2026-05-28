"""Inbound Twilio SMS webhook handling."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.services import lead_service, message_service, phone_number_service

TWILIO_PROVIDER = "twilio"
SUMMARY_MAX_LEN = 500


@dataclass(frozen=True)
class InboundSmsProcessed:
    business_id: uuid.UUID
    lead_id: uuid.UUID
    from_phone: str
    to_phone: str
    body: str


def _summary_snippet(body: str) -> str:
    snippet = body.strip()
    if len(snippet) > SUMMARY_MAX_LEN:
        return snippet[:SUMMARY_MAX_LEN]
    return snippet


def process_inbound_sms(
    db: Session,
    *,
    from_phone: str,
    to_phone: str,
    body: str,
    provider_sid: str | None,
) -> InboundSmsProcessed | None:
    """
    Process inbound SMS. Returns context when a new inbound message was stored.

    Duplicate provider_sid returns None (no outbound auto-response).
    """
    from_trimmed = from_phone.strip()
    to_trimmed = to_phone.strip()
    body_trimmed = body.strip()

    if not from_trimmed or not to_trimmed or not body_trimmed:
        return None

    phone_record = phone_number_service.get_phone_number_by_number(db, to_trimmed)
    if phone_record is None:
        return None

    sid = (provider_sid or "").strip()
    if sid:
        existing = message_service.get_message_by_provider_sid(db, TWILIO_PROVIDER, sid)
        if existing is not None:
            return None

    business_id = phone_record.business_id
    lead = lead_service.get_lead_by_business_and_phone(db, business_id, from_trimmed)
    if lead is None:
        lead = lead_service.create_lead(
            db,
            business_id,
            phone=from_trimmed,
            source="sms",
            summary=_summary_snippet(body_trimmed),
        )

    message_service.create_message(
        db,
        business_id,
        lead.id,
        body=body_trimmed,
        direction="inbound",
        channel="sms",
        from_phone=from_trimmed,
        to_phone=to_trimmed,
        provider=TWILIO_PROVIDER,
        provider_sid=sid or None,
        status="received",
    )
    return InboundSmsProcessed(
        business_id=business_id,
        lead_id=lead.id,
        from_phone=from_trimmed,
        to_phone=to_trimmed,
        body=body_trimmed,
    )
