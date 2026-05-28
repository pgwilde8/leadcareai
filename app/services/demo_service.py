"""Admin demo control panel helpers."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.lead import Lead
from app.models.message import Message
from app.models.notification_log import NotificationLog
from app.services import lead_service


@dataclass(frozen=True)
class DemoLeadRow:
    lead: Lead
    masked_phone: str
    latest_message_preview: str | None
    recommended_action: str


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
