"""SMS business logic (AI-guided intake reply + Twilio outbound)."""

from __future__ import annotations

import logging
import re
import uuid

from sqlalchemy.orm import Session

from app.schemas.lead_ai import LeadAIAnalysis
from app.services import lead_service, message_service
from app.services.ai_service import analyze_inbound_sms_for_lead
from app.services.business_service import get_business
from app.services.business_settings_service import build_missed_call_textback_body
from app.services.lead_service import apply_ai_analysis, build_lead_context_for_ai, get_lead
from app.services.message_service import MESSAGE_STATUSES
from app.services.twilio_inbound_sms_service import InboundSmsProcessed, TWILIO_PROVIDER
from app.services.twilio_inbound_voice_service import VoiceCallProcessed
from app.services.twilio_service import SendSmsResult, TwilioConfigError, send_sms

logger = logging.getLogger(__name__)

STOP_SUFFIX = " Reply STOP to opt out."

_FORBIDDEN_REPLY_PATTERNS = re.compile(
    r"(\$\s?\d|€\s?\d|\bprice\b|\bcost\b|\bfree estimate\b|available now|call you (right )?back in \d)",
    re.IGNORECASE,
)


def _simple_auto_response_body(business_name: str | None) -> str:
    if business_name and business_name.strip():
        return (
            f"Thanks — this is {business_name.strip()}. "
            "We received your message and will follow up shortly."
            f"{STOP_SUFFIX}"
        )
    return f"Thanks — we received your message and will follow up shortly.{STOP_SUFFIX}"


def _ai_guided_response_body(business_name: str | None, analysis: LeadAIAnalysis) -> str:
    next_q = analysis.capped_next_question()
    if next_q and _FORBIDDEN_REPLY_PATTERNS.search(next_q):
        next_q = None

    if next_q:
        prefix = f"{business_name.strip()}: " if business_name and business_name.strip() else ""
        return f"{prefix}Thanks — we received your message. {next_q}{STOP_SUFFIX}"

    return _simple_auto_response_body(business_name)


def _normalize_outbound_status(raw_status: str) -> str:
    normalized = raw_status.strip().lower()
    if normalized in MESSAGE_STATUSES:
        return normalized
    if normalized in {"accepted", "sending"}:
        return "queued"
    if normalized in {"undelivered"}:
        return "failed"
    return "sent"


def _store_outbound_message(
    db: Session,
    *,
    business_id: uuid.UUID,
    lead_id: uuid.UUID,
    body: str,
    customer_phone: str,
    from_phone: str,
    status: str,
    provider_sid: str | None,
) -> None:
    message_service.create_message(
        db,
        business_id,
        lead_id,
        body=body,
        direction="outbound",
        channel="sms",
        from_phone=from_phone,
        to_phone=customer_phone,
        provider=TWILIO_PROVIDER,
        provider_sid=provider_sid,
        status=status,
    )


def send_missed_call_textback(db: Session, processed: VoiceCallProcessed) -> None:
    """
    Send one SMS after an inbound voice event. Never raises to the webhook caller.
    """
    business = get_business(db, processed.business_id)
    body = build_missed_call_textback_body(business)

    from app.core.config import get_settings

    settings = get_settings()
    from_phone = (settings.twilio_phone_number or "").strip()

    try:
        result: SendSmsResult = send_sms(
            to_phone=processed.from_phone,
            body=body,
            from_phone=from_phone or None,
            business_id=processed.business_id,
            lead_id=processed.lead_id,
        )
        _store_outbound_message(
            db,
            business_id=processed.business_id,
            lead_id=processed.lead_id,
            body=body,
            customer_phone=processed.from_phone,
            from_phone=from_phone,
            status=_normalize_outbound_status(result.status),
            provider_sid=result.sid or None,
        )
    except TwilioConfigError as exc:
        logger.warning(
            "Missed-call text-back skipped: %s",
            exc,
            extra={"lead_id": str(processed.lead_id), "business_id": str(processed.business_id)},
        )
        _store_outbound_message(
            db,
            business_id=processed.business_id,
            lead_id=processed.lead_id,
            body=body,
            customer_phone=processed.from_phone,
            from_phone=from_phone,
            status="failed",
            provider_sid=None,
        )
    except Exception:
        logger.exception(
            "Missed-call text-back failed",
            extra={"lead_id": str(processed.lead_id), "business_id": str(processed.business_id)},
        )
        _store_outbound_message(
            db,
            business_id=processed.business_id,
            lead_id=processed.lead_id,
            body=body,
            customer_phone=processed.from_phone,
            from_phone=from_phone,
            status="failed",
            provider_sid=None,
        )


def send_inbound_auto_response(db: Session, processed: InboundSmsProcessed) -> None:
    """
    Analyze inbound SMS, update lead fields, and send one guided reply.

    Never raises to the webhook caller; failures are logged and stored as failed outbound.
    """
    business = get_business(db, processed.business_id)
    lead = get_lead(db, processed.lead_id)

    analysis = analyze_inbound_sms_for_lead(
        business_name=business.name,
        business_industry=business.industry,
        customer_message=processed.body,
        existing_lead_context=build_lead_context_for_ai(lead),
    )
    try:
        apply_ai_analysis(db, processed.lead_id, analysis)
    except Exception:
        logger.exception(
            "Failed to apply AI analysis to lead",
            extra={"lead_id": str(processed.lead_id)},
        )

    body = _ai_guided_response_body(business.name, analysis)

    from app.core.config import get_settings

    settings = get_settings()
    from_phone = (settings.twilio_phone_number or "").strip()

    try:
        result: SendSmsResult = send_sms(
            to_phone=processed.from_phone,
            body=body,
            from_phone=from_phone or None,
            business_id=processed.business_id,
            lead_id=processed.lead_id,
        )
        _store_outbound_message(
            db,
            business_id=processed.business_id,
            lead_id=processed.lead_id,
            body=body,
            customer_phone=processed.from_phone,
            from_phone=from_phone,
            status=_normalize_outbound_status(result.status),
            provider_sid=result.sid or None,
        )
    except TwilioConfigError as exc:
        logger.warning(
            "Outbound auto-response skipped: %s",
            exc,
            extra={"lead_id": str(processed.lead_id), "business_id": str(processed.business_id)},
        )
        _store_outbound_message(
            db,
            business_id=processed.business_id,
            lead_id=processed.lead_id,
            body=body,
            customer_phone=processed.from_phone,
            from_phone=from_phone,
            status="failed",
            provider_sid=None,
        )
    except Exception:
        logger.exception(
            "Outbound auto-response failed",
            extra={"lead_id": str(processed.lead_id), "business_id": str(processed.business_id)},
        )
        _store_outbound_message(
            db,
            business_id=processed.business_id,
            lead_id=processed.lead_id,
            body=body,
            customer_phone=processed.from_phone,
            from_phone=from_phone,
            status="failed",
            provider_sid=None,
        )
