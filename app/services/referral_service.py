"""Partner referral code capture and session attribution."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.models.partner import PARTNER_STATUSES, Partner

REFERRAL_CODE_SESSION_KEY = "referral_code"
REFERRAL_PARTNER_ID_SESSION_KEY = "referral_partner_id"


def get_active_partner_by_referral_code(db: Session, referral_code: str) -> Partner | None:
    code = referral_code.strip()
    if not code:
        return None
    return (
        db.query(Partner)
        .filter(
            Partner.referral_code == code.upper(),
            Partner.status == "active",
        )
        .one_or_none()
    )


def get_referral_from_session(request) -> tuple[str | None, uuid.UUID | None]:
    code = request.session.get(REFERRAL_CODE_SESSION_KEY)
    raw_partner_id = request.session.get(REFERRAL_PARTNER_ID_SESSION_KEY)
    partner_id: uuid.UUID | None = None
    if raw_partner_id:
        try:
            partner_id = uuid.UUID(str(raw_partner_id))
        except (TypeError, ValueError):
            partner_id = None
    if code:
        code = str(code).strip() or None
    return code, partner_id


def clear_referral_session(request) -> None:
    request.session.pop(REFERRAL_CODE_SESSION_KEY, None)
    request.session.pop(REFERRAL_PARTNER_ID_SESSION_KEY, None)


def resolve_referral_partner(db: Session, request) -> Partner | None:
    """Return active partner from session if still valid; clear stale session keys."""
    code, partner_id = get_referral_from_session(request)
    if partner_id is not None:
        partner = db.get(Partner, partner_id)
        if partner is not None and partner.status == "active":
            request.session[REFERRAL_CODE_SESSION_KEY] = partner.referral_code
            return partner
        clear_referral_session(request)

    if code:
        partner = get_active_partner_by_referral_code(db, code)
        if partner is not None:
            request.session[REFERRAL_CODE_SESSION_KEY] = partner.referral_code
            request.session[REFERRAL_PARTNER_ID_SESSION_KEY] = str(partner.id)
            return partner
        clear_referral_session(request)
    return None
