"""Business profile and lead-handling settings (V1)."""

from __future__ import annotations

import re
import uuid

from sqlalchemy.orm import Session

from app.models.business import Business
from app.services.business_service import get_business

STOP_SUFFIX = " Reply STOP to opt out."
MISSED_CALL_MESSAGE_MAX_LEN = 240
_URL_PATTERN = re.compile(r"https?://|www\.", re.IGNORECASE)


def _strip(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def resolve_outbound_sms_label(
    business: Business | None = None,
    *,
    business_name: str | None = None,
    sms_signature: str | None = None,
) -> str:
    """
    Label/signature for outbound SMS openers.

    Precedence: sms_signature -> business.name -> "LeadCare AI".
    """
    signature = (
        (sms_signature or (business.sms_signature if business is not None else None) or "")
        .strip()
    )
    if signature:
        return signature

    name = (business_name or (business.name if business is not None else None) or "").strip()
    if name:
        return name

    return "LeadCare AI"


def build_missed_call_textback_body(business: Business) -> str:
    """Resolved SMS body for missed-call text-back (custom or platform default)."""
    custom = (business.missed_call_textback_message or "").strip()
    if custom:
        return custom

    label = resolve_outbound_sms_label(business)
    return (
        f"{label}: Sorry we missed your call. "
        "What can we help you with today?"
        f"{STOP_SUFFIX}"
    )


def preview_default_missed_call_message(business: Business) -> str:
    """Default message shown in settings when no custom message is saved."""
    label = resolve_outbound_sms_label(business)
    return (
        f"{label}: Sorry we missed your call. "
        "What can we help you with today?"
        f"{STOP_SUFFIX}"
    )


def normalize_missed_call_textback_message(raw: str | None) -> str | None:
    """
  Normalize custom missed-call SMS.

  Empty input clears custom message (platform default).
  Whitespace-only is rejected. STOP language is enforced. Links are rejected.
  """
    if raw is None:
        return None
    if raw != "" and not raw.strip():
        raise ValueError("Missed-call message cannot be blank")
    text = raw.strip()
    if not text:
        return None
    if _URL_PATTERN.search(text):
        raise ValueError("Links are not allowed in missed-call messages")
    if "STOP" not in text.upper():
        text = text.rstrip() + STOP_SUFFIX
    if len(text) > MISSED_CALL_MESSAGE_MAX_LEN:
        raise ValueError(
            f"Missed-call message must be {MISSED_CALL_MESSAGE_MAX_LEN} characters or fewer"
        )
    return text


def update_business_settings(
    db: Session,
    business_id: uuid.UUID,
    *,
    name: str,
    industry: str | None = None,
    website_url: str | None = None,
    contact_email: str | None = None,
    contact_phone: str | None = None,
    notification_email: str | None = None,
    notification_phone: str | None = None,
    missed_call_textback_message: str | None = None,
    sms_signature: str | None = None,
    lead_intake_prompt: str | None = None,
) -> Business:
    business = get_business(db, business_id)

    trimmed_name = name.strip()
    if not trimmed_name:
        raise ValueError("Business name must not be empty")

    business.name = trimmed_name
    business.industry = _strip(industry)
    business.website_url = _strip(website_url)
    business.contact_email = _strip(contact_email)
    business.main_phone = _strip(contact_phone)
    business.notification_email = _strip(notification_email)
    business.notification_phone = _strip(notification_phone)
    business.sms_signature = _strip(sms_signature)
    business.lead_intake_prompt = _strip(lead_intake_prompt)
    business.missed_call_textback_message = normalize_missed_call_textback_message(
        missed_call_textback_message
    )

    db.flush()
    return business
