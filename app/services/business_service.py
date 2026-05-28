"""Business CRUD and user linking (no product workflows)."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.business_user import BusinessUser
from app.models.user import User


def create_business(
    db: Session,
    name: str,
    industry: str | None = None,
    website_url: str | None = None,
    main_phone: str | None = None,
    timezone: str = "America/New_York",
) -> Business:
    trimmed_name = name.strip()
    if not trimmed_name:
        raise ValueError("Business name must not be empty")

    business = Business(
        name=trimmed_name,
        industry=industry.strip() if industry else None,
        website_url=website_url.strip() if website_url else None,
        main_phone=main_phone.strip() if main_phone else None,
        timezone=timezone,
    )
    db.add(business)
    db.flush()
    return business


def list_businesses(db: Session) -> list[Business]:
    return db.query(Business).order_by(Business.name).all()


def get_business(db: Session, business_id: uuid.UUID) -> Business:
    business = db.get(Business, business_id)
    if business is None:
        raise ValueError(f"Business {business_id} not found")
    return business


def get_primary_business_for_user(db: Session, user_id: uuid.UUID) -> Business | None:
    """First business linked to this user (earliest membership)."""
    link = (
        db.query(BusinessUser)
        .filter(BusinessUser.user_id == user_id)
        .order_by(BusinessUser.created_at.asc())
        .first()
    )
    if link is None:
        return None
    return get_business(db, link.business_id)


def link_user_to_business(
    db: Session,
    user_id: uuid.UUID,
    business_id: uuid.UUID,
    role: str = "owner",
) -> BusinessUser:
    if db.get(User, user_id) is None:
        raise ValueError(f"User {user_id} not found")
    if db.get(Business, business_id) is None:
        raise ValueError(f"Business {business_id} not found")

    existing = (
        db.query(BusinessUser)
        .filter(
            BusinessUser.business_id == business_id,
            BusinessUser.user_id == user_id,
        )
        .one_or_none()
    )
    if existing is not None:
        raise ValueError("User is already linked to this business")

    link = BusinessUser(
        business_id=business_id,
        user_id=user_id,
        role=role,
    )
    db.add(link)
    db.flush()
    return link
