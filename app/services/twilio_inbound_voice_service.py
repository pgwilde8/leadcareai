"""Inbound Twilio voice webhook handling (missed-call text-back)."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.services import lead_service, message_service, phone_number_service

logger = logging.getLogger(__name__)

TWILIO_PROVIDER = "twilio"
VOICE_CHANNEL = "voice"
LEAD_SOURCE_MISSED_CALL = "missed_call"


@dataclass(frozen=True)
class VoiceCallProcessed:
    business_id: uuid.UUID
    lead_id: uuid.UUID
    from_phone: str
    to_phone: str
    call_sid: str


def _call_event_body(call_status: str, from_phone: str) -> str:
    status = call_status.strip().lower()
    if status in {"no-answer", "busy", "failed", "canceled"}:
        return f"Missed call from {from_phone}"
    return f"Inbound call from {from_phone}"


def process_inbound_voice(
    db: Session,
    *,
    from_phone: str,
    to_phone: str,
    call_sid: str,
    call_status: str,
    direction: str | None = None,
) -> VoiceCallProcessed | None:
    """
    Process inbound voice webhook. Returns context when a new call event was stored.

    Duplicate CallSid returns None (no duplicate SMS).
    """
    from_trimmed = from_phone.strip()
    to_trimmed = to_phone.strip()
    sid = call_sid.strip()
    status_trimmed = (call_status or "ringing").strip()

    if not from_trimmed or not to_trimmed or not sid:
        return None

    phone_record = phone_number_service.get_phone_number_by_number(db, to_trimmed)
    if phone_record is None:
        logger.info(
            "Voice webhook ignored: no active phone number for To=%s",
            to_trimmed,
        )
        return None

    existing = message_service.get_message_by_provider_sid(db, TWILIO_PROVIDER, sid)
    if existing is not None:
        return None

    business_id = phone_record.business_id
    lead = lead_service.get_lead_by_business_and_phone(db, business_id, from_trimmed)
    summary = _call_event_body(status_trimmed, from_trimmed)
    if lead is None:
        lead = lead_service.create_lead(
            db,
            business_id,
            phone=from_trimmed,
            source=LEAD_SOURCE_MISSED_CALL,
            summary=summary,
        )
    elif not lead.summary or lead.summary.strip() == "":
        lead.summary = summary

    message_service.create_voice_message(
        db,
        business_id,
        lead.id,
        body=summary,
        from_phone=from_trimmed,
        to_phone=to_trimmed,
        provider_sid=sid,
        status=status_trimmed,
        direction_hint=direction,
    )

    return VoiceCallProcessed(
        business_id=business_id,
        lead_id=lead.id,
        from_phone=from_trimmed,
        to_phone=to_trimmed,
        call_sid=sid,
    )


def update_voice_call_status(
    db: Session,
    *,
    call_sid: str,
    call_status: str,
    from_phone: str | None = None,
    to_phone: str | None = None,
    call_duration: str | None = None,
) -> bool:
    """Update stored voice message status by CallSid. Returns True if updated."""
    sid = call_sid.strip()
    if not sid:
        return False

    message = message_service.get_message_by_provider_sid(db, TWILIO_PROVIDER, sid)
    if message is None or message.channel != VOICE_CHANNEL:
        logger.info(
            "Voice status webhook: no voice message for CallSid=%s status=%s",
            sid,
            call_status,
        )
        return False

    new_status = call_status.strip().lower()
    if new_status:
        message.status = new_status

    if call_duration and call_duration.strip().isdigit():
        duration = call_duration.strip()
        message.body = f"{message.body} (duration {duration}s)"

    message_service.touch_message(db, message)
    logger.info(
        "Voice call status updated CallSid=%s status=%s from=%s to=%s",
        sid,
        new_status,
        from_phone or "",
        to_phone or "",
    )
    return True
