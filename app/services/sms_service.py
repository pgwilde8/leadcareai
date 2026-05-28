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
from app.models.business import Business
from app.services.business_settings_service import (
    build_missed_call_textback_body,
    resolve_outbound_sms_label,
)
from app.services.lead_service import apply_ai_analysis, build_lead_context_for_ai, get_lead
from app.services.message_service import MESSAGE_STATUSES
from app.services.twilio_inbound_sms_service import InboundSmsProcessed, TWILIO_PROVIDER
from app.services.twilio_inbound_voice_service import VoiceCallProcessed
from app.services.twilio_service import SendSmsResult, TwilioConfigError, send_sms

logger = logging.getLogger(__name__)

STOP_SUFFIX = " Reply STOP to opt out."
SMS_SOFT_MAX_LEN = 160
LOW_CONFIDENCE_THRESHOLD = 0.45

_FORBIDDEN_REPLY_PATTERNS = re.compile(
    r"(\$\s?\d|€\s?\d|\bprice\b|\bcost\b|\bfree estimate\b|available now|call you (right )?back in \d)",
    re.IGNORECASE,
)
_URGENT_KEYWORDS = re.compile(
    r"\b(leak now|emergency|flood(?:ing)?|no ac|broken pipe|no heat|locked out|burst pipe|gas leak|fire)\b",
    re.IGNORECASE,
)

SMS_TEMPLATE_LIBRARY = {
    "missed_call": "{label} Sorry we missed your call. What can we help with today? Reply STOP to opt out.",
    "inbound_sms": "{label} Thanks for your message. {question} Reply STOP to opt out.",
    "urgent": "{label} Thanks for reaching out. This sounds urgent. {question} If this is dangerous or life-threatening, call 911. Reply STOP to opt out.",
    "fallback": "{label} Thanks for your message. What service is needed and what town are you in? Reply STOP to opt out.",
    "handoff": "{label} Thanks. We shared this with the team. Would you prefer a callback today or tomorrow? Reply STOP to opt out.",
}


def _normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _label_prefix(business: Business) -> str:
    return f"{resolve_outbound_sms_label(business)}:"


def _enforce_one_question(text: str) -> str:
    if text.count("?") <= 1:
        return text
    first = text.find("?")
    if first == -1:
        return text
    before = text[: first + 1]
    after = text[first + 1 :].replace("?", ".")
    return f"{before}{after}"


def _safe_short_sms(text: str) -> str:
    """Keep SMS concise and preserve STOP compliance wording."""
    body = _normalize_spaces(text)
    body = _enforce_one_question(body)
    if len(body) <= SMS_SOFT_MAX_LEN:
        return body

    stop = "Reply STOP to opt out."
    if stop in body:
        base = body.replace(stop, "").rstrip(" .")
        max_base_len = max(40, SMS_SOFT_MAX_LEN - len(stop) - 2)
        if len(base) > max_base_len:
            base = base[: max_base_len - 1].rstrip(" .,") + "…"
        return f"{base} {stop}"

    return body[: SMS_SOFT_MAX_LEN - 1].rstrip(" .,") + "…"


def _is_urgent(customer_message: str, analysis: LeadAIAnalysis) -> bool:
    if analysis.urgency in {"urgent", "emergency"} or analysis.lead_temperature == "hot":
        return True
    return bool(_URGENT_KEYWORDS.search(customer_message))


def _simple_auto_response_body(business: Business) -> str:
    label = _label_prefix(business)
    body = SMS_TEMPLATE_LIBRARY["handoff"].format(label=label)
    return _safe_short_sms(body)


def _ai_guided_response_body(
    business: Business,
    analysis: LeadAIAnalysis,
    customer_message: str,
) -> str:
    next_q = analysis.capped_next_question()
    if next_q and _FORBIDDEN_REPLY_PATTERNS.search(next_q):
        next_q = None

    if analysis.confidence < LOW_CONFIDENCE_THRESHOLD:
        next_q = None

    if next_q and len(next_q) > 120:
        next_q = None

    label = _label_prefix(business)
    if not next_q:
        body = SMS_TEMPLATE_LIBRARY["fallback"].format(label=label)
        return _safe_short_sms(body)

    if _is_urgent(customer_message, analysis):
        body = SMS_TEMPLATE_LIBRARY["urgent"].format(label=label, question=next_q)
        return _safe_short_sms(body)

    body = SMS_TEMPLATE_LIBRARY["inbound_sms"].format(label=label, question=next_q)
    return _safe_short_sms(body)


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

    body = _ai_guided_response_body(business, analysis, processed.body)

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
