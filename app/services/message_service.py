"""Message records for leads (manual/internal; no Twilio)."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.message import Message
from app.services.business_service import get_business
from app.services.lead_service import get_lead

MESSAGE_DIRECTIONS = frozenset({"inbound", "outbound", "internal"})
MESSAGE_CHANNELS = frozenset({"manual", "sms", "note", "voice"})
MESSAGE_STATUSES = frozenset(
    {
        "recorded",
        "queued",
        "sent",
        "delivered",
        "failed",
        "received",
        "ringing",
        "in-progress",
        "completed",
        "busy",
        "no-answer",
        "canceled",
        "initiated",
    }
)
TWILIO_VOICE_STATUSES = frozenset(
    {"queued", "ringing", "in-progress", "completed", "busy", "failed", "no-answer", "canceled", "initiated"}
)


def _strip(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def create_message(
    db: Session,
    business_id: uuid.UUID,
    lead_id: uuid.UUID,
    body: str,
    direction: str = "internal",
    channel: str = "manual",
    from_phone: str | None = None,
    to_phone: str | None = None,
    provider: str = "manual",
    provider_sid: str | None = None,
    status: str = "recorded",
) -> Message:
    get_business(db, business_id)

    lead = get_lead(db, lead_id)
    if lead.business_id != business_id:
        raise ValueError("Lead does not belong to this business")

    if direction not in MESSAGE_DIRECTIONS:
        raise ValueError(f"Invalid message direction: {direction!r}")
    if channel not in MESSAGE_CHANNELS:
        raise ValueError(f"Invalid message channel: {channel!r}")
    if status not in MESSAGE_STATUSES:
        raise ValueError(f"Invalid message status: {status!r}")

    trimmed_body = body.strip()
    if not trimmed_body:
        raise ValueError("Message body must not be empty")

    message = Message(
        business_id=business_id,
        lead_id=lead_id,
        direction=direction,
        channel=channel,
        from_phone=_strip(from_phone),
        to_phone=_strip(to_phone),
        body=trimmed_body,
        provider=provider,
        provider_sid=_strip(provider_sid),
        status=status,
    )
    db.add(message)
    db.flush()
    return message


def list_messages_for_lead(db: Session, lead_id: uuid.UUID) -> list[Message]:
    get_lead(db, lead_id)
    return (
        db.query(Message)
        .filter(Message.lead_id == lead_id)
        .order_by(Message.created_at.asc(), Message.id.asc())
        .all()
    )


def get_message(db: Session, message_id: uuid.UUID) -> Message:
    message = db.get(Message, message_id)
    if message is None:
        raise ValueError(f"Message {message_id} not found")
    return message


def get_message_by_provider_sid(
    db: Session,
    provider: str,
    provider_sid: str,
) -> Message | None:
    trimmed_sid = provider_sid.strip()
    if not trimmed_sid:
        return None
    return (
        db.query(Message)
        .filter(Message.provider == provider, Message.provider_sid == trimmed_sid)
        .one_or_none()
    )


def create_voice_message(
    db: Session,
    business_id: uuid.UUID,
    lead_id: uuid.UUID,
    *,
    body: str,
    from_phone: str,
    to_phone: str,
    provider_sid: str,
    status: str,
    direction_hint: str | None = None,
) -> Message:
    trimmed_body = body.strip()
    if not trimmed_body:
        raise ValueError("Message body must not be empty")

    normalized_status = status.strip().lower()
    if normalized_status not in MESSAGE_STATUSES and normalized_status not in TWILIO_VOICE_STATUSES:
        normalized_status = "ringing"

    if direction_hint and direction_hint.strip():
        trimmed_body = f"{trimmed_body} [{direction_hint.strip()}]"

    return create_message(
        db,
        business_id,
        lead_id,
        body=trimmed_body,
        direction="inbound",
        channel="voice",
        from_phone=from_phone,
        to_phone=to_phone,
        provider="twilio",
        provider_sid=provider_sid,
        status=normalized_status,
    )


def touch_message(db: Session, message: Message) -> Message:
    db.flush()
    return message
