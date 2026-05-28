"""Public live missed-call demo (Joe's Plumbing Demo)."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models.business import Business
from app.models.lead import Lead
from app.services import lead_service
from app.services.business_service import get_business
from app.services.demo_service import mask_phone
from app.services.phone_number_service import get_phone_number_by_number

DEMO_BUSINESS_DISPLAY_NAME = "Joe's Plumbing Demo"
DEMO_PHONE_E164 = "+18336691335"
DEMO_PHONE_DISPLAY = "1-833-669-1335"

DEMO_MISSED_CALL_SMS = (
    "Hi, this is Joe's Plumbing Demo. Sorry we missed your call. "
    "What plumbing issue can we help with? Reply STOP to opt out."
)

DEMO_TWIML = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say>Sorry we missed your call. We just sent you a text message so we can help faster.</Say>
  <Hangup/>
</Response>"""

@dataclass(frozen=True)
class PublicDemoLeadRow:
    lead: Lead
    masked_phone: str
    issue: str
    urgency: str
    location: str
    status: str
    created_at: object
    summary: str


def normalize_phone(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\D", "", value.strip())


def is_demo_enabled(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return bool(settings.demo_enabled and (settings.demo_business_id or "").strip())


def get_demo_business_id(settings: Settings | None = None) -> uuid.UUID | None:
    settings = settings or get_settings()
    if not is_demo_enabled(settings):
        return None
    try:
        return uuid.UUID(str(settings.demo_business_id).strip())
    except ValueError:
        return None


def is_demo_business_id(db: Session, business_id: uuid.UUID) -> bool:
    demo_id = get_demo_business_id()
    return demo_id is not None and demo_id == business_id


def is_demo_phone_number(db: Session, to_phone: str, settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    to_norm = normalize_phone(to_phone)
    if not to_norm:
        return False
    configured = normalize_phone(settings.demo_twilio_number or DEMO_PHONE_E164)
    if configured and to_norm == configured:
        return True
    demo_id = get_demo_business_id()
    if demo_id is None:
        return False
    record = get_phone_number_by_number(db, to_phone.strip())
    return record is not None and record.business_id == demo_id


def get_demo_business(db: Session) -> Business | None:
    demo_id = get_demo_business_id()
    if demo_id is None:
        return None
    try:
        return get_business(db, demo_id)
    except ValueError:
        return None


def _display_issue(lead: Lead) -> str:
    return (lead.service_needed or lead.summary or "—").strip() or "—"


def _display_urgency(lead: Lead) -> str:
    return (lead.urgency or "—").strip() or "—"


def _display_location(lead: Lead) -> str:
    return (lead.location or "—").strip() or "—"


def _display_summary(lead: Lead) -> str:
    parts: list[str] = []
    if lead.service_needed:
        parts.append(f"Issue: {lead.service_needed}")
    if lead.urgency:
        parts.append(f"Urgency: {lead.urgency}")
    if lead.location:
        parts.append(f"Town: {lead.location}")
    if lead.name:
        parts.append(f"Name: {lead.name}")
    if lead.email:
        parts.append(f"Email: {lead.email}")
    if lead.preferred_contact_time:
        parts.append(f"Callback: {lead.preferred_contact_time}")
    if parts:
        return " | ".join(parts)
    return (lead.summary or "Demo intake in progress").strip()


def list_public_demo_leads(db: Session, *, limit: int = 50) -> list[PublicDemoLeadRow]:
    business = get_demo_business(db)
    if business is None:
        return []
    leads = lead_service.list_leads_for_business(db, business.id)
    rows: list[PublicDemoLeadRow] = []
    for lead in leads[: max(1, limit)]:
        rows.append(
            PublicDemoLeadRow(
                lead=lead,
                masked_phone=mask_phone(lead.phone),
                issue=_display_issue(lead),
                urgency=_display_urgency(lead),
                location=_display_location(lead),
                status=lead.status,
                created_at=lead.created_at,
                summary=_display_summary(lead),
            )
        )
    return rows

