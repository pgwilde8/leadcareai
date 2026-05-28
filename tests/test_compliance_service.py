"""Compliance service tests (SQLite)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.business_compliance_profile import BusinessComplianceProfile
from app.services import compliance_service
from app.services.business_service import create_business


def test_create_or_get_creates_profile(db_session: Session) -> None:
    business = create_business(db_session, name="Compliance Co")
    db_session.commit()

    profile = compliance_service.create_or_get_compliance_profile(db_session, business.id)
    db_session.commit()

    assert profile.id is not None
    assert profile.business_id == business.id
    assert profile.status == "not_started"


def test_create_or_get_returns_existing_profile(db_session: Session) -> None:
    business = create_business(db_session, name="Existing Profile Co")
    db_session.commit()

    first = compliance_service.create_or_get_compliance_profile(db_session, business.id)
    db_session.commit()
    second = compliance_service.create_or_get_compliance_profile(db_session, business.id)

    assert second.id == first.id


def test_one_profile_per_business(db_session: Session) -> None:
    business = create_business(db_session, name="Unique Profile Co")
    db_session.commit()

    compliance_service.create_or_get_compliance_profile(db_session, business.id)
    db_session.commit()

    duplicate = BusinessComplianceProfile(business_id=business.id)
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_update_compliance_profile_updates_fields(db_session: Session) -> None:
    business = create_business(db_session, name="Update Fields Co")
    db_session.commit()

    profile = compliance_service.update_compliance_profile(
        db_session,
        business.id,
        legal_business_name="  Acme LLC  ",
        ein="12-3456789",
        sms_use_case="Missed call follow-up",
    )
    db_session.commit()

    assert profile.legal_business_name == "Acme LLC"
    assert profile.ein == "12-3456789"
    assert profile.sms_use_case == "Missed call follow-up"


def test_update_compliance_status_accepts_allowed_status(db_session: Session) -> None:
    business = create_business(db_session, name="Status Co")
    db_session.commit()

    profile = compliance_service.update_compliance_status(
        db_session,
        business.id,
        status="submitted",
    )
    db_session.commit()

    assert profile.status == "submitted"


def test_update_compliance_status_rejects_invalid_status(db_session: Session) -> None:
    business = create_business(db_session, name="Bad Status Co")
    db_session.commit()

    with pytest.raises(ValueError, match="Invalid compliance status"):
        compliance_service.update_compliance_status(
            db_session,
            business.id,
            status="bogus",
        )


def test_missing_business_raises_value_error(db_session: Session) -> None:
    missing_id = uuid.uuid4()

    with pytest.raises(ValueError, match="not found"):
        compliance_service.create_or_get_compliance_profile(db_session, missing_id)
