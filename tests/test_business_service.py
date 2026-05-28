"""Business service tests (SQLite)."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.services.business_service import (
    create_business,
    get_business,
    link_user_to_business,
    list_businesses,
)
from app.services.user_service import create_user


def test_create_business_trims_name(db_session: Session) -> None:
    business = create_business(db_session, name="  Mike's Roofing  ")
    assert business.name == "Mike's Roofing"


def test_create_business_rejects_empty_name(db_session: Session) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        create_business(db_session, name="   ")


def test_list_businesses_returns_created_businesses(db_session: Session) -> None:
    create_business(db_session, name="Alpha Co")
    create_business(db_session, name="Beta Co")
    db_session.commit()

    names = [b.name for b in list_businesses(db_session)]
    assert names == ["Alpha Co", "Beta Co"]


def test_link_user_to_business_creates_relationship(db_session: Session) -> None:
    business = create_business(db_session, name="Linked Co")
    user = create_user(db_session, email="owner@example.com", password="secret")
    db_session.commit()

    link = link_user_to_business(db_session, user.id, business.id, role="owner")
    assert link.business_id == business.id
    assert link.user_id == user.id
    assert link.role == "owner"


def test_duplicate_link_raises_value_error(db_session: Session) -> None:
    business = create_business(db_session, name="Dup Co")
    user = create_user(db_session, email="dup@example.com", password="secret")
    link_user_to_business(db_session, user.id, business.id)
    db_session.commit()

    with pytest.raises(ValueError, match="already linked"):
        link_user_to_business(db_session, user.id, business.id)


def test_get_business_raises_when_missing(db_session: Session) -> None:
    import uuid

    with pytest.raises(ValueError, match="not found"):
        get_business(db_session, uuid.uuid4())
