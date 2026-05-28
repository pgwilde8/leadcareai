"""Database model smoke tests (SQLite, no Postgres required)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.user import User


def test_user_defaults_and_round_trip(db_session: Session) -> None:
    user = User(
        email="owner@example.com",
        hashed_password="hashed-secret",
        full_name="Test Owner",
    )
    db_session.add(user)
    db_session.commit()

    loaded = db_session.query(User).filter_by(email="owner@example.com").one()

    assert loaded.id is not None
    assert loaded.is_active is True
    assert loaded.role == "business_user"
    assert loaded.full_name == "Test Owner"
    assert loaded.created_at is not None
    assert loaded.updated_at is not None


def test_business_defaults_and_round_trip(db_session: Session) -> None:
    business = Business(name="Mike's Roofing")
    db_session.add(business)
    db_session.commit()

    loaded = db_session.query(Business).filter_by(name="Mike's Roofing").one()

    assert loaded.id is not None
    assert loaded.status == "pending"
    assert loaded.timezone == "America/New_York"
    assert loaded.industry is None
    assert loaded.stripe_customer_id is None
    assert loaded.created_at is not None
