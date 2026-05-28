"""Business lead notifications (email + staff SMS)."""

from __future__ import annotations

import logging
import re
import smtplib
import uuid
from email.message import EmailMessage

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.business import Business
from app.models.lead import Lead
from app.models.message import Message
from app.models.notification_log import NotificationLog
from app.services.business_service import get_business
from app.services.lead_service import get_lead
from app.services.lead_service import recommended_action_for_lead
from app.services.twilio_service import SendSmsResult, TwilioConfigError, TwilioSendError, send_sms

logger = logging.getLogger(__name__)

STAFF_SMS_MAX_LEN = 320
SUMMARY_SNIPPET_LEN = 100
INBOUND_QUOTE_MAX_LEN = 80
_NON_DIGIT = re.compile(r"\D+")
_URGENT_LEVELS = frozenset({"urgent", "emergency"})


def _normalize_phone_digits(phone: str | None) -> str:
    if not phone:
        return ""
    return _NON_DIGIT.sub("", phone.strip())


def _phones_match(a: str | None, b: str | None) -> bool:
    da = _normalize_phone_digits(a)
    db = _normalize_phone_digits(b)
    if not da or not db:
        return False
    return da == db or da.endswith(db) or db.endswith(da)


def is_urgent_lead(lead: Lead) -> bool:
    """True when urgency or AI temperature indicates an emergency-style lead."""
    urgency = (lead.urgency or "").strip().lower()
    if urgency in _URGENT_LEVELS:
        return True
    temperature = (lead.ai_temperature or "").strip().lower()
    return temperature == "hot"


def _urgent_email_prefix(lead: Lead) -> str:
    return "[URGENT] " if is_urgent_lead(lead) else ""


def _staff_sms_brand(lead: Lead) -> str:
    return "URGENT LeadCare AI" if is_urgent_lead(lead) else "LeadCare AI"


def _short_summary(lead: Lead, message: Message | str | None) -> str:
    if isinstance(message, Message):
        text = (message.body or "").strip()
    elif isinstance(message, str):
        text = message.strip()
    else:
        text = ""
    if not text:
        text = (lead.summary or "New activity").strip()
    if len(text) > SUMMARY_SNIPPET_LEN:
        return text[:SUMMARY_SNIPPET_LEN] + "…"
    return text


def _quote_snippet(text: str, *, max_len: int = INBOUND_QUOTE_MAX_LEN) -> str:
    cleaned = re.sub(r"\s+", " ", text.strip())
    if not cleaned:
        return "''"
    if len(cleaned) > max_len:
        cleaned = cleaned[: max_len - 1].rstrip() + "…"
    return f"'{cleaned}'"


def _lead_detail_url(lead_id: uuid.UUID) -> str | None:
    base = get_settings().effective_public_base_url
    if not base:
        return None
    return f"{base}/business/leads/{lead_id}"


def build_lead_notification_summary(
    business: Business,
    lead: Lead,
    message: Message | str | None,
) -> dict[str, str]:
    """Structured summary for email / staff SMS."""
    if isinstance(message, Message):
        latest = message.body.strip()
    elif isinstance(message, str):
        latest = message.strip()
    else:
        latest = ""

    detail_url = _lead_detail_url(lead.id)
    source_label = {
        "sms": "SMS",
        "missed_call": "Missed call",
    }.get(lead.source, lead.source)

    temperature = (lead.ai_temperature or "").strip()
    return {
        "business_name": business.name,
        "customer_phone": lead.phone or "—",
        "lead_status": lead.status,
        "source": source_label,
        "summary": lead.summary or _short_summary(lead, message),
        "service_needed": (lead.service_needed or "—").strip() or "—",
        "urgency": lead.urgency or "—",
        "ai_temperature": temperature or "—",
        "latest_message": latest or lead.summary or "—",
        "dashboard_url": detail_url or "",
    }


def _build_email_body(
    *,
    event_label: str,
    summary: dict[str, str],
) -> str:
    lines = [
        event_label,
        "",
        f"Business: {summary['business_name']}",
        f"Customer phone: {summary['customer_phone']}",
        f"Status: {summary['lead_status']}",
        f"Source: {summary['source']}",
        f"Service needed: {summary['service_needed']}",
        f"Summary: {summary['summary']}",
        f"Urgency: {summary['urgency']}",
        f"AI temperature: {summary['ai_temperature']}",
        "",
        "Latest message:",
        summary["latest_message"],
    ]
    if summary["dashboard_url"]:
        lines.extend(["", f"View lead: {summary['dashboard_url']}"])
    return "\n".join(lines)


def _build_inbound_reply_staff_sms(
    business: Business,
    lead: Lead,
    message: Message | str | None,
) -> str:
    """Compact staff SMS for live customer SMS replies."""
    brand = _staff_sms_brand(lead)
    phone = lead.phone or "unknown"
    quoted = _quote_snippet(_short_summary(lead, message))
    parts = [f"{brand}: New reply for {business.name} from {phone}: {quoted}"]
    urgency = (lead.urgency or "").strip()
    if urgency and urgency.lower() not in {"normal", "low", "unknown", "—", "-"}:
        parts.append(f" Urgency: {urgency}.")
    detail_url = _lead_detail_url(lead.id)
    if detail_url:
        parts.append(f" View: {detail_url}")
    body = "".join(parts)
    if len(body) > STAFF_SMS_MAX_LEN:
        body = body[: STAFF_SMS_MAX_LEN - 1] + "…"
    return body


def _build_missed_call_staff_sms(
    business: Business,
    lead: Lead,
    message: Message | str | None,
) -> str:
    """Staff SMS for new missed-call leads (multi-line detail)."""
    brand = _staff_sms_brand(lead)
    urgency = (lead.urgency or "normal").strip().upper() or "NORMAL"
    service = (lead.service_needed or "Unknown service").strip()
    town = (lead.location or "Unknown town").strip()
    name = (lead.name or "Unknown").strip()
    callback = (lead.preferred_contact_time or "Not provided").strip()
    last_message = _short_summary(lead, message)
    parts = [
        f"{brand}: {urgency} | {service} | {town}\n"
        f"Name: {name}\n"
        f"Callback: {callback}\n"
        f"Last message: {last_message}"
    ]
    if lead.ai_temperature or lead.ai_confidence is not None or lead.ai_last_analyzed_at:
        parts.append(f"\nRecommended: {recommended_action_for_lead(lead)}")
    detail_url = _lead_detail_url(lead.id)
    if detail_url:
        parts.append(f"\nView: {detail_url}")
    body = "".join(parts)
    if len(body) > STAFF_SMS_MAX_LEN:
        body = body[: STAFF_SMS_MAX_LEN - 1] + "…"
    return body


def _build_staff_sms_body(
    *,
    event_type: str,
    business: Business,
    lead: Lead,
    message: Message | str | None,
) -> str:
    if event_type == "inbound_sms":
        return _build_inbound_reply_staff_sms(business, lead, message)
    return _build_missed_call_staff_sms(business, lead, message)


def list_recent_notifications_for_lead(
    db: Session,
    *,
    business_id: uuid.UUID,
    lead_id: uuid.UUID,
    limit: int = 5,
) -> list[NotificationLog]:
    return (
        db.query(NotificationLog)
        .filter(
            NotificationLog.business_id == business_id,
            NotificationLog.lead_id == lead_id,
        )
        .order_by(NotificationLog.created_at.desc())
        .limit(max(1, limit))
        .all()
    )


def _smtp_configured() -> bool:
    settings = get_settings()
    return bool(settings.smtp_host and settings.smtp_from_email)


def _send_notification_email(*, to_email: str, subject: str, body: str) -> tuple[str, str | None, str | None]:
    """
    Send notification email. Returns (status, error_message, provider_sid).

    status is sent | failed | skipped
    """
    settings = get_settings()
    if not _smtp_configured():
        logger.info(
            "Notification email skipped (SMTP not configured): to=%s subject=%s",
            to_email,
            subject,
        )
        return "skipped", "SMTP not configured", None

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
        logger.info("Notification email sent to=%s subject=%s", to_email, subject)
        return "sent", None, None
    except Exception as exc:
        logger.exception("Notification email failed to=%s", to_email)
        return "failed", str(exc)[:500], None


def _send_staff_notification_sms(
    db: Session,
    *,
    business: Business,
    lead: Lead,
    to_phone: str,
    body: str,
) -> tuple[str, str | None, str | None]:
    """Staff alert SMS (not customer-facing). Returns (status, error, provider_sid)."""
    if _phones_match(to_phone, lead.phone):
        return "skipped", "Staff phone matches customer phone", None

    settings = get_settings()
    from_phone = (settings.twilio_phone_number or "").strip()

    try:
        result: SendSmsResult = send_sms(
            to_phone=to_phone,
            body=body,
            from_phone=from_phone or None,
            business_id=business.id,
            lead_id=lead.id,
        )
        return "sent", None, result.sid or None
    except (TwilioConfigError, TwilioSendError) as exc:
        logger.warning(
            "Staff notification SMS failed: %s",
            exc,
            extra={"business_id": str(business.id), "lead_id": str(lead.id)},
        )
        return "failed", str(exc)[:500], None
    except Exception as exc:
        logger.exception(
            "Staff notification SMS unexpected error",
            extra={"business_id": str(business.id), "lead_id": str(lead.id)},
        )
        return "failed", str(exc)[:500], None


def _record_notification(
    db: Session,
    *,
    business_id: uuid.UUID,
    lead_id: uuid.UUID,
    channel: str,
    recipient: str,
    event_type: str,
    status: str,
    error_message: str | None = None,
    provider_sid: str | None = None,
) -> NotificationLog:
    entry = NotificationLog(
        business_id=business_id,
        lead_id=lead_id,
        channel=channel,
        recipient=recipient,
        event_type=event_type,
        status=status,
        error_message=error_message,
        provider_sid=provider_sid,
    )
    db.add(entry)
    db.flush()
    return entry


def _dispatch_notifications(
    db: Session,
    *,
    business: Business,
    lead: Lead,
    message: Message | str | None,
    event_type: str,
    email_subject: str,
) -> None:
    summary = build_lead_notification_summary(business, lead, message)
    email_body = _build_email_body(event_label=email_subject, summary=summary)
    staff_body = _build_staff_sms_body(
        event_type=event_type,
        business=business,
        lead=lead,
        message=message,
    )

    notification_email = (business.notification_email or "").strip()
    if notification_email:
        status, error, sid = _send_notification_email(
            to_email=notification_email,
            subject=email_subject,
            body=email_body,
        )
        _record_notification(
            db,
            business_id=business.id,
            lead_id=lead.id,
            channel="email",
            recipient=notification_email,
            event_type=event_type,
            status=status,
            error_message=error,
            provider_sid=sid,
        )
    else:
        logger.debug(
            "Notification email not configured business_id=%s event=%s",
            business.id,
            event_type,
        )

    notification_phone = (business.notification_phone or "").strip()
    if notification_phone:
        status, error, sid = _send_staff_notification_sms(
            db,
            business=business,
            lead=lead,
            to_phone=notification_phone,
            body=staff_body,
        )
        _record_notification(
            db,
            business_id=business.id,
            lead_id=lead.id,
            channel="sms",
            recipient=notification_phone,
            event_type=event_type,
            status=status,
            error_message=error,
            provider_sid=sid,
        )
    else:
        logger.debug(
            "Notification phone not configured business_id=%s event=%s",
            business.id,
            event_type,
        )


def notify_new_missed_call_lead(
    db: Session,
    business: Business,
    lead: Lead,
    voice_message: Message | str,
) -> None:
    """Alert business staff after a new missed-call lead event. Never raises."""
    try:
        db.refresh(lead)
        _dispatch_notifications(
            db,
            business=business,
            lead=lead,
            message=voice_message,
            event_type="missed_call",
            email_subject=f"{_urgent_email_prefix(lead)}New missed-call lead: {business.name}",
        )
    except Exception:
        logger.exception(
            "Missed-call lead notification failed",
            extra={"business_id": str(business.id), "lead_id": str(lead.id)},
        )


def notify_inbound_sms_reply(
    db: Session,
    business: Business,
    lead: Lead,
    inbound_message: Message | str,
) -> None:
    """Alert business staff after a new inbound SMS (post AI analysis). Never raises."""
    try:
        db.refresh(lead)
        _dispatch_notifications(
            db,
            business=business,
            lead=lead,
            message=inbound_message,
            event_type="inbound_sms",
            email_subject=f"{_urgent_email_prefix(lead)}New customer reply: {business.name}",
        )
    except Exception:
        logger.exception(
            "Inbound SMS notification failed",
            extra={"business_id": str(business.id), "lead_id": str(lead.id)},
        )


def notify_new_missed_call_lead_by_id(
    db: Session,
    business_id: uuid.UUID,
    lead_id: uuid.UUID,
    voice_message: Message | str,
) -> None:
    business = get_business(db, business_id)
    lead = get_lead(db, lead_id)
    notify_new_missed_call_lead(db, business, lead, voice_message)


def notify_inbound_sms_reply_by_id(
    db: Session,
    business_id: uuid.UUID,
    lead_id: uuid.UUID,
    inbound_message: Message | str,
) -> None:
    business = get_business(db, business_id)
    lead = get_lead(db, lead_id)
    notify_inbound_sms_reply(db, business, lead, inbound_message)
