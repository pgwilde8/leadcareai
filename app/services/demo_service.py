"""Admin demo control panel helpers."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.models.business import Business
from app.models.lead import Lead
from app.models.message import Message
from app.models.notification_log import NotificationLog
from app.services import lead_service
from app.services.business_service import get_business


@dataclass(frozen=True)
class DemoLeadRow:
    lead: Lead
    masked_phone: str
    latest_message_preview: str | None
    recommended_action: str


@dataclass(frozen=True)
class DemoReadinessItem:
    key: str
    label: str
    ok: bool
    detail: str


def build_demo_readiness_checklist(
    db: Session,
    *,
    settings: Settings | None = None,
) -> list[DemoReadinessItem]:
    """Admin sales-demo readiness checks (no secrets exposed)."""
    settings = settings or get_settings()
    items: list[DemoReadinessItem] = []

    demo_enabled = bool(settings.demo_enabled)
    items.append(
        DemoReadinessItem(
            key="demo_enabled",
            label="Demo mode enabled (DEMO_ENABLED)",
            ok=demo_enabled,
            detail="true" if demo_enabled else "Set DEMO_ENABLED=true",
        )
    )

    raw_business_id = (settings.demo_business_id or "").strip()
    items.append(
        DemoReadinessItem(
            key="demo_business_id",
            label="Demo business ID configured (DEMO_BUSINESS_ID)",
            ok=bool(raw_business_id),
            detail=raw_business_id or "Not set",
        )
    )

    business: Business | None = None
    business_exists = False
    if raw_business_id:
        try:
            business = get_business(db, uuid.UUID(raw_business_id))
            business_exists = True
        except (ValueError, TypeError):
            business_exists = False

    items.append(
        DemoReadinessItem(
            key="demo_business_exists",
            label="Demo business exists",
            ok=business_exists,
            detail=business.name if business else "Business record not found",
        )
    )

    demo_number = (settings.demo_twilio_number or "").strip()
    items.append(
        DemoReadinessItem(
            key="demo_twilio_number",
            label="Demo number configured (DEMO_TWILIO_NUMBER)",
            ok=bool(demo_number),
            detail=demo_number or "Not set",
        )
    )

    staff_configured = bool(
        business and (business.notification_email or business.notification_phone)
    )
    staff_detail = "—"
    if business:
        parts = []
        if business.notification_email:
            parts.append(f"email: {business.notification_email}")
        if business.notification_phone:
            parts.append(f"phone: {business.notification_phone}")
        staff_detail = ", ".join(parts) if parts else "Add notification email or phone on business record"
    elif business_exists:
        staff_detail = "Add notification email or phone on business record"
    else:
        staff_detail = "Configure demo business first"

    items.append(
        DemoReadinessItem(
            key="staff_notifications",
            label="Staff notification configured",
            ok=staff_configured,
            detail=staff_detail,
        )
    )

    recent_lead_ok = False
    recent_detail = "Run the live demo once (call, hang up, reply to SMS)"
    if business_exists and business is not None:
        leads = lead_service.list_leads_for_business(db, business.id)
        if leads:
            recent_lead_ok = True
            latest = leads[0]
            recent_detail = f"Latest lead {latest.created_at} · status {latest.status}"
        else:
            recent_detail = "No demo leads yet — run through the call + SMS flow"

    items.append(
        DemoReadinessItem(
            key="recent_demo_lead",
            label="Recent demo lead exists",
            ok=recent_lead_ok,
            detail=recent_detail,
        )
    )

    return items


def mask_phone(phone: str | None) -> str:
    if not phone:
        return "—"
    raw = phone.strip()
    if len(raw) <= 4:
        return "*" * len(raw)
    return f"{'*' * max(0, len(raw) - 4)}{raw[-4:]}"


def list_recent_demo_leads(
    db: Session,
    *,
    business_id: uuid.UUID,
    limit: int = 25,
) -> list[DemoLeadRow]:
    inbox_rows = lead_service.list_lead_inbox_for_business(db, business_id)
    return [
        DemoLeadRow(
            lead=row.lead,
            masked_phone=mask_phone(row.lead.phone),
            latest_message_preview=row.last_message_preview,
            recommended_action=lead_service.recommended_action_for_lead(row.lead),
        )
        for row in inbox_rows[: max(1, limit)]
    ]


def clear_demo_business_data(db: Session, *, business_id: uuid.UUID) -> dict[str, int]:
    leads = db.query(Lead).filter(Lead.business_id == business_id).all()
    lead_ids = [lead.id for lead in leads]
    deleted_messages = 0
    deleted_notifications = 0

    if lead_ids:
        deleted_messages = (
            db.query(Message)
            .filter(Message.lead_id.in_(lead_ids))
            .delete(synchronize_session=False)
        )
        deleted_notifications = (
            db.query(NotificationLog)
            .filter(NotificationLog.lead_id.in_(lead_ids))
            .delete(synchronize_session=False)
        )

    deleted_leads = (
        db.query(Lead)
        .filter(Lead.business_id == business_id)
        .delete(synchronize_session=False)
    )
    return {
        "leads": int(deleted_leads or 0),
        "messages": int(deleted_messages or 0),
        "notifications": int(deleted_notifications or 0),
    }
