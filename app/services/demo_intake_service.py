"""Scripted SMS intake for the public live demo business."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from app.models.lead import Lead
from app.services import message_service
from app.services.demo_live_service import DEMO_MISSED_CALL_SMS, is_demo_business_id
from app.services.lead_service import get_lead
from app.services.message_service import MESSAGE_STATUSES
from app.services.twilio_inbound_sms_service import InboundSmsProcessed
from app.services.twilio_inbound_voice_service import VoiceCallProcessed
from app.services.twilio_service import SendSmsResult, TwilioConfigError, TwilioSendError, send_sms

logger = logging.getLogger(__name__)

INTAKE_QUESTIONS = (
    "Is it urgent or actively leaking, and what town are you in?",
    "What's your name?",
    "What's the best email for the appointment/request summary?",
    "Would you prefer a callback today or tomorrow?",
)
INTAKE_THANKS = "Thanks — Joe's team has the details and will follow up."


def _inbound_sms_count(db: Session, lead_id: uuid.UUID) -> int:
    from app.models.message import Message

    return (
        db.query(Message)
        .filter(
            Message.lead_id == lead_id,
            Message.direction == "inbound",
            Message.channel == "sms",
        )
        .count()
    )


def _refresh_summary(lead: Lead) -> None:
    parts: list[str] = []
    if lead.service_needed:
        parts.append(f"Issue: {lead.service_needed}")
    if lead.urgency:
        parts.append(f"Urgency: {lead.urgency}")
    if lead.location:
        parts.append(f"Location: {lead.location}")
    if lead.name:
        parts.append(f"Name: {lead.name}")
    if lead.email:
        parts.append(f"Email: {lead.email}")
    if lead.preferred_contact_time:
        parts.append(f"Callback: {lead.preferred_contact_time}")
    lead.summary = " | ".join(parts) if parts else "Demo plumbing intake"


def _normalize_outbound_status(raw_status: str) -> str:
    normalized = raw_status.strip().lower()
    if normalized in MESSAGE_STATUSES:
        return normalized
    if normalized in {"accepted", "sending"}:
        return "queued"
    if normalized in {"undelivered"}:
        return "failed"
    return "sent"


def _send_demo_sms(
    db: Session,
    *,
    business_id: uuid.UUID,
    lead_id: uuid.UUID,
    to_phone: str,
    body: str,
) -> None:
    from app.core.config import get_settings

    settings = get_settings()
    from_phone = (settings.twilio_phone_number or "").strip()
    try:
        result: SendSmsResult = send_sms(
            to_phone=to_phone,
            body=body,
            from_phone=from_phone or None,
            business_id=business_id,
            lead_id=lead_id,
        )
        status = _normalize_outbound_status(result.status)
        sid = result.sid or None
    except (TwilioConfigError, TwilioSendError) as exc:
        logger.warning("Demo SMS skipped: %s", exc)
        status = "failed"
        sid = None
    except Exception:
        logger.exception("Demo SMS send failed", extra={"lead_id": str(lead_id)})
        status = "failed"
        sid = None

    message_service.create_message(
        db,
        business_id,
        lead_id,
        body=body,
        direction="outbound",
        channel="sms",
        from_phone=from_phone,
        to_phone=to_phone,
        provider="twilio",
        provider_sid=sid,
        status=status,
    )


def send_demo_missed_call_textback(db: Session, processed: VoiceCallProcessed) -> None:
    if not is_demo_business_id(db, processed.business_id):
        return
    _send_demo_sms(
        db,
        business_id=processed.business_id,
        lead_id=processed.lead_id,
        to_phone=processed.from_phone,
        body=DEMO_MISSED_CALL_SMS,
    )
    lead = get_lead(db, processed.lead_id)
    if lead.status == "new":
        lead.status = "qualifying"
    _refresh_summary(lead)


def _reply_for_step(db: Session, lead: Lead, step: int, inbound_body: str) -> str:
    body = inbound_body.strip()
    if step == 1:
        lead.service_needed = body[:255]
        lead.status = "qualifying"
        _refresh_summary(lead)
        return INTAKE_QUESTIONS[0]
    if step == 2:
        lead.urgency = body[:100]
        if "," in body:
            lead.location = body.split(",", 1)[-1].strip()[:255]
        elif " in " in body.lower():
            lead.location = body.lower().split(" in ", 1)[-1].strip()[:255]
        else:
            lead.location = body[:255]
        _refresh_summary(lead)
        return INTAKE_QUESTIONS[1]
    if step == 3:
        lead.name = body[:255]
        _refresh_summary(lead)
        return INTAKE_QUESTIONS[2]
    if step == 4:
        lead.email = body[:255]
        _refresh_summary(lead)
        return INTAKE_QUESTIONS[3]
    if step == 5:
        lead.preferred_contact_time = body[:100]
        lead.status = "qualified"
        _refresh_summary(lead)
        return INTAKE_THANKS
    return INTAKE_THANKS


def handle_demo_inbound_sms(db: Session, processed: InboundSmsProcessed) -> None:
    if not is_demo_business_id(db, processed.business_id):
        return

    lead = get_lead(db, processed.lead_id)
    step = _inbound_sms_count(db, processed.lead_id)
    reply = _reply_for_step(db, lead, step, processed.body)
    _send_demo_sms(
        db,
        business_id=processed.business_id,
        lead_id=processed.lead_id,
        to_phone=processed.from_phone,
        body=reply,
    )
