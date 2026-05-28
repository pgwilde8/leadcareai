"""Business SMS compliance / A2P 10DLC profile (manual; no Twilio API)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.business_compliance_profile import BusinessComplianceProfile
from app.services.business_service import get_business

COMPLIANCE_STATUSES = frozenset(
    {"not_started", "needs_review", "submitted", "approved", "rejected"}
)

_UPDATABLE_FIELDS = frozenset(
    {
        "legal_business_name",
        "dba_name",
        "business_type",
        "ein",
        "website_url",
        "business_phone",
        "business_email",
        "address_line1",
        "address_line2",
        "city",
        "state",
        "postal_code",
        "country",
        "authorized_rep_name",
        "authorized_rep_title",
        "authorized_rep_email",
        "sms_use_case",
        "opt_in_description",
        "sample_message_1",
        "sample_message_2",
        "privacy_policy_url",
        "terms_url",
        "twilio_brand_sid",
        "twilio_campaign_sid",
        "status",
        "rejection_reason",
    }
)


def _strip(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def get_compliance_profile_for_business(
    db: Session,
    business_id: uuid.UUID,
) -> BusinessComplianceProfile | None:
    get_business(db, business_id)
    return (
        db.query(BusinessComplianceProfile)
        .filter(BusinessComplianceProfile.business_id == business_id)
        .one_or_none()
    )


def create_or_get_compliance_profile(
    db: Session,
    business_id: uuid.UUID,
) -> BusinessComplianceProfile:
    get_business(db, business_id)
    existing = get_compliance_profile_for_business(db, business_id)
    if existing is not None:
        return existing

    profile = BusinessComplianceProfile(business_id=business_id)
    db.add(profile)
    db.flush()
    return profile


def update_compliance_profile(
    db: Session,
    business_id: uuid.UUID,
    **fields: Any,
) -> BusinessComplianceProfile:
    profile = create_or_get_compliance_profile(db, business_id)

    for key, value in fields.items():
        if key not in _UPDATABLE_FIELDS:
            raise ValueError(f"Unknown compliance field: {key!r}")

    if "status" in fields:
        status = fields["status"]
        if status not in COMPLIANCE_STATUSES:
            raise ValueError(f"Invalid compliance status: {status!r}")

    for key in _UPDATABLE_FIELDS:
        if key not in fields:
            continue
        value = fields[key]
        if key in {"opt_in_description", "sample_message_1", "sample_message_2", "rejection_reason"}:
            setattr(profile, key, _strip(value) if isinstance(value, str) else value)
        elif key == "country":
            setattr(profile, key, _strip(value) or "US")
        elif isinstance(value, str):
            setattr(profile, key, _strip(value))
        else:
            setattr(profile, key, value)

    db.flush()
    return profile


def update_compliance_status(
    db: Session,
    business_id: uuid.UUID,
    status: str,
    rejection_reason: str | None = None,
) -> BusinessComplianceProfile:
    if status not in COMPLIANCE_STATUSES:
        raise ValueError(f"Invalid compliance status: {status!r}")

    profile = create_or_get_compliance_profile(db, business_id)
    profile.status = status
    if status == "rejected":
        profile.rejection_reason = _strip(rejection_reason)
    elif rejection_reason is not None:
        profile.rejection_reason = _strip(rejection_reason)
    else:
        profile.rejection_reason = None

    db.flush()
    return profile
