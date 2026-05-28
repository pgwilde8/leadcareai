"""Phone number service tests (SQLite)."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from app.models.phone_number import PhoneNumber
from app.services.business_service import create_business
from app.services.phone_number_service import (
    create_or_update_phone_number,
    create_phone_number,
    get_phone_number_by_number,
    list_phone_numbers_for_business,
)


def test_create_phone_number_trims(db_session: Session) -> None:
    business = create_business(db_session, name="Phone Co")
    record = create_phone_number(db_session, business.id, "  +15551234567  ")
    assert record.phone_number == "+15551234567"


def test_create_phone_number_rejects_empty(db_session: Session) -> None:
    business = create_business(db_session, name="Empty Phone Co")
    with pytest.raises(ValueError, match="must not be empty"):
        create_phone_number(db_session, business.id, "   ")


def test_create_phone_number_rejects_missing_business(db_session: Session) -> None:
    with pytest.raises(ValueError, match="not found"):
        create_phone_number(db_session, uuid.uuid4(), "+15550001111")


def test_list_phone_numbers_for_business(db_session: Session) -> None:
    business = create_business(db_session, name="List Phone Co")
    create_phone_number(db_session, business.id, "+15551111111")
    create_phone_number(db_session, business.id, "+15552222222")
    db_session.commit()

    numbers = list_phone_numbers_for_business(db_session, business.id)
    assert len(numbers) == 2
    assert {n.phone_number for n in numbers} == {"+15551111111", "+15552222222"}


def test_get_phone_number_by_number_active_only(db_session: Session) -> None:
    business = create_business(db_session, name="Lookup Co")
    create_phone_number(
        db_session,
        business.id,
        "+18336691335",
        provider="twilio",
        status="inactive",
    )
    db_session.commit()

    assert get_phone_number_by_number(db_session, "+18336691335") is None
    assert get_phone_number_by_number(db_session, "+18336691335", active_only=False) is not None


def test_create_phone_number_rejects_duplicate(db_session: Session) -> None:
    business = create_business(db_session, name="Dup Phone Co")
    create_phone_number(db_session, business.id, "+15559998888", status="active")
    db_session.commit()

    with pytest.raises(ValueError, match="already assigned"):
        create_phone_number(db_session, business.id, "+15559998888")


def test_create_or_update_phone_number_is_idempotent(db_session: Session) -> None:
    business = create_business(db_session, name="Seed Co")
    first = create_or_update_phone_number(
        db_session,
        business.id,
        "+18336691335",
        label="Line A",
        provider="twilio",
        status="active",
    )
    db_session.commit()
    second = create_or_update_phone_number(
        db_session,
        business.id,
        "+18336691335",
        label="Line B",
        provider="twilio",
        status="active",
    )

    assert second.id == first.id
    assert second.label == "Line B"
    assert db_session.query(PhoneNumber).filter_by(phone_number="+18336691335").count() == 1
