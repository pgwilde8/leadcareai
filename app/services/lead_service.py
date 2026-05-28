"""Lead CRUD and AI qualification field updates."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.lead import Lead
from app.models.message import Message
from app.schemas.lead_ai import LeadAIAnalysis
from app.services.business_service import get_business

LEAD_STATUSES = frozenset(
    {
        "new",
        "qualifying",
        "qualified",
        "contacted",
        "booked",
        "won",
        "lost",
        "spam",
        "archived",
    }
)

BUSINESS_SELECTABLE_STATUSES: tuple[str, ...] = (
    "new",
    "qualifying",
    "contacted",
    "won",
    "lost",
    "archived",
)

LEAD_SOURCES = frozenset({"manual", "missed_call", "sms", "web_form", "demo"})


def _strip(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _lead_has_content(
    *,
    name: str | None,
    phone: str | None,
    email: str | None,
    service_needed: str | None,
    location: str | None,
    urgency: str | None,
    summary: str | None,
) -> bool:
    return any(
        (
            name,
            phone,
            email,
            service_needed,
            location,
            urgency,
            summary,
        )
    )


def create_lead(
    db: Session,
    business_id: uuid.UUID,
    name: str | None = None,
    phone: str | None = None,
    email: str | None = None,
    service_needed: str | None = None,
    location: str | None = None,
    urgency: str | None = None,
    summary: str | None = None,
    source: str = "manual",
) -> Lead:
    get_business(db, business_id)

    if source not in LEAD_SOURCES:
        raise ValueError(f"Invalid lead source: {source!r}")

    fields = {
        "name": _strip(name),
        "phone": _strip(phone),
        "email": _strip(email),
        "service_needed": _strip(service_needed),
        "location": _strip(location),
        "urgency": _strip(urgency),
        "summary": _strip(summary),
    }
    if not _lead_has_content(**fields):
        raise ValueError("Lead must include at least one contact or detail field")

    lead = Lead(business_id=business_id, source=source, status="new", **fields)
    db.add(lead)
    db.flush()
    return lead


def list_leads_for_business(db: Session, business_id: uuid.UUID) -> list[Lead]:
    get_business(db, business_id)
    return (
        db.query(Lead)
        .filter(Lead.business_id == business_id)
        .order_by(Lead.created_at.desc())
        .all()
    )


def get_lead(db: Session, lead_id: uuid.UUID) -> Lead:
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise ValueError(f"Lead {lead_id} not found")
    return lead


def get_lead_for_business(db: Session, business_id: uuid.UUID, lead_id: uuid.UUID) -> Lead:
    lead = get_lead(db, lead_id)
    if lead.business_id != business_id:
        raise ValueError(f"Lead {lead_id} not found")
    return lead


@dataclass(frozen=True)
class LeadInboxRow:
    lead: Lead
    last_message_preview: str | None


def _last_message_preview(db: Session, lead_id: uuid.UUID) -> str | None:
    message = (
        db.query(Message)
        .filter(Message.lead_id == lead_id)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .first()
    )
    if message is None:
        return None
    body = message.body.strip()
    if not body:
        return None
    return body[:160] + ("…" if len(body) > 160 else "")


def list_lead_inbox_for_business(db: Session, business_id: uuid.UUID) -> list[LeadInboxRow]:
    leads = list_leads_for_business(db, business_id)
    return [
        LeadInboxRow(lead=lead, last_message_preview=_last_message_preview(db, lead.id))
        for lead in leads
    ]


def dashboard_lead_counts(db: Session, business_id: uuid.UUID) -> dict[str, int]:
    leads = list_leads_for_business(db, business_id)
    counts = {
        "new": 0,
        "qualifying": 0,
        "urgent_hot": 0,
        "total": len(leads),
    }
    for lead in leads:
        if lead.status == "new":
            counts["new"] += 1
        elif lead.status == "qualifying":
            counts["qualifying"] += 1

        is_hot = lead.ai_temperature == "hot"
        urgency = (lead.urgency or "").strip().lower()
        is_urgent = urgency in {"urgent", "today", "asap", "emergency"}
        if is_hot or is_urgent:
            counts["urgent_hot"] += 1
    return counts


def get_lead_by_business_and_phone(
    db: Session,
    business_id: uuid.UUID,
    phone: str,
) -> Lead | None:
    trimmed = phone.strip()
    if not trimmed:
        return None
    return (
        db.query(Lead)
        .filter(Lead.business_id == business_id, Lead.phone == trimmed)
        .one_or_none()
    )


def update_lead_status(db: Session, lead_id: uuid.UUID, status: str) -> Lead:
    if status not in LEAD_STATUSES:
        raise ValueError(f"Invalid lead status: {status!r}")

    lead = get_lead(db, lead_id)
    lead.status = status
    db.flush()
    return lead


def build_lead_context_for_ai(lead: Lead) -> dict[str, Any]:
    return {
        "name": lead.name,
        "service_needed": lead.service_needed,
        "location": lead.location,
        "urgency": lead.urgency,
        "summary": lead.summary,
        "status": lead.status,
        "ai_temperature": lead.ai_temperature,
    }


def apply_ai_analysis(db: Session, lead_id: uuid.UUID, analysis: LeadAIAnalysis) -> Lead:
    """Persist AI classification onto the lead (existing columns + ai_* fields)."""
    lead = get_lead(db, lead_id)

    if analysis.service_needed and analysis.service_needed.strip():
        lead.service_needed = analysis.service_needed.strip()[:255]
    if analysis.location and analysis.location.strip():
        lead.location = analysis.location.strip()[:255]
    if analysis.urgency and analysis.urgency != "unknown":
        lead.urgency = analysis.urgency[:100]
    if analysis.customer_name and analysis.customer_name.strip() and not lead.name:
        lead.name = analysis.customer_name.strip()[:255]
    if analysis.summary and analysis.summary.strip():
        lead.summary = analysis.summary.strip()[:5000]

    lead.ai_temperature = analysis.lead_temperature
    lead.ai_next_question = analysis.capped_next_question()
    lead.ai_confidence = analysis.confidence
    lead.ai_last_analyzed_at = datetime.now(timezone.utc)

    if lead.status == "new" and analysis.lead_temperature in {"warm", "hot"}:
        lead.status = "qualifying"

    db.flush()
    return lead
