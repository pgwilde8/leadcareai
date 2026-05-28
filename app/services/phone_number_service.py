"""Phone number records (admin + Twilio inbound routing)."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.phone_number import PhoneNumber
from app.services.business_service import get_business

PHONE_STATUSES = frozenset({"pending", "active", "inactive"})


def _strip(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def get_phone_number_by_number(
    db: Session,
    phone_number: str,
    *,
    active_only: bool = True,
) -> PhoneNumber | None:
    trimmed = phone_number.strip()
    if not trimmed:
        return None
    query = db.query(PhoneNumber).filter(PhoneNumber.phone_number == trimmed)
    if active_only:
        query = query.filter(PhoneNumber.status == "active")
    return query.one_or_none()


def create_phone_number(
    db: Session,
    business_id: uuid.UUID,
    phone_number: str,
    label: str | None = None,
    forward_to_number: str | None = None,
    provider: str = "manual",
    provider_sid: str | None = None,
    status: str = "pending",
) -> PhoneNumber:
    get_business(db, business_id)

    trimmed = phone_number.strip()
    if not trimmed:
        raise ValueError("Phone number must not be empty")

    if status not in PHONE_STATUSES:
        raise ValueError(f"Invalid phone number status: {status!r}")

    existing = get_phone_number_by_number(db, trimmed, active_only=False)
    if existing is not None:
        raise ValueError(f"Phone number {trimmed!r} is already assigned")

    record = PhoneNumber(
        business_id=business_id,
        phone_number=trimmed,
        label=_strip(label),
        forward_to_number=_strip(forward_to_number),
        provider=provider.strip() or "manual",
        provider_sid=_strip(provider_sid),
        status=status,
    )
    db.add(record)
    db.flush()
    return record


def create_or_update_phone_number(
    db: Session,
    business_id: uuid.UUID,
    phone_number: str,
    *,
    label: str | None = None,
    provider: str = "twilio",
    provider_sid: str | None = None,
    status: str = "active",
) -> PhoneNumber:
    """Idempotent upsert by E.164 phone_number (seed/scripts)."""
    get_business(db, business_id)

    trimmed = phone_number.strip()
    if not trimmed:
        raise ValueError("Phone number must not be empty")
    if status not in PHONE_STATUSES:
        raise ValueError(f"Invalid phone number status: {status!r}")

    existing = get_phone_number_by_number(db, trimmed, active_only=False)
    if existing is not None:
        if existing.business_id != business_id:
            raise ValueError(
                f"Phone number {trimmed!r} is already assigned to another business"
            )
        existing.label = _strip(label) or existing.label
        existing.provider = provider.strip() or existing.provider
        if provider_sid is not None:
            existing.provider_sid = _strip(provider_sid)
        existing.status = status
        db.flush()
        return existing

    return create_phone_number(
        db,
        business_id,
        trimmed,
        label=label,
        provider=provider,
        provider_sid=provider_sid,
        status=status,
    )


def update_phone_number_status(
    db: Session,
    phone_number_id: uuid.UUID,
    status: str,
) -> PhoneNumber:
    if status not in PHONE_STATUSES:
        raise ValueError(f"Invalid phone number status: {status!r}")

    record = get_phone_number(db, phone_number_id)
    record.status = status
    db.flush()
    return record


def list_phone_numbers_for_business(
    db: Session,
    business_id: uuid.UUID,
) -> list[PhoneNumber]:
    get_business(db, business_id)
    return (
        db.query(PhoneNumber)
        .filter(PhoneNumber.business_id == business_id)
        .order_by(PhoneNumber.created_at.desc())
        .all()
    )


def get_phone_number(db: Session, phone_number_id: uuid.UUID) -> PhoneNumber:
    record = db.get(PhoneNumber, phone_number_id)
    if record is None:
        raise ValueError(f"Phone number {phone_number_id} not found")
    return record
