"""Lead service tests (SQLite)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from app.services.business_service import create_business
from app.services.lead_service import (
    create_lead,
    get_lead,
    list_leads_for_business,
    update_lead_status,
)


def test_create_lead_requires_business(db_session: Session) -> None:
    with pytest.raises(ValueError, match="not found"):
        create_lead(db_session, uuid.uuid4(), name="Ghost")


def test_create_lead_rejects_totally_empty(db_session: Session) -> None:
    business = create_business(db_session, name="Empty Lead Co")
    with pytest.raises(ValueError, match="at least one"):
        create_lead(db_session, business.id)


def test_create_lead_manual(db_session: Session) -> None:
    business = create_business(db_session, name="Lead Co")
    lead = create_lead(
        db_session,
        business.id,
        name="Jane Doe",
        phone="+15559998888",
        service_needed="Roof repair",
    )
    assert lead.source == "manual"
    assert lead.status == "new"
    assert lead.name == "Jane Doe"


def test_list_leads_for_business(db_session: Session) -> None:
    business = create_business(db_session, name="List Lead Co")
    create_lead(db_session, business.id, name="A")
    create_lead(db_session, business.id, phone="+15550000001")
    db_session.commit()

    leads = list_leads_for_business(db_session, business.id)
    assert len(leads) == 2


def test_update_lead_status_works(db_session: Session) -> None:
    business = create_business(db_session, name="Status Co")
    lead = create_lead(db_session, business.id, name="Status Lead")
    db_session.commit()

    updated = update_lead_status(db_session, lead.id, "qualified")
    assert updated.status == "qualified"
    assert get_lead(db_session, lead.id).status == "qualified"


def test_invalid_status_raises_value_error(db_session: Session) -> None:
    business = create_business(db_session, name="Bad Status Co")
    lead = create_lead(db_session, business.id, name="X")
    db_session.commit()

    with pytest.raises(ValueError, match="Invalid lead status"):
        update_lead_status(db_session, lead.id, "not-a-real-status")
