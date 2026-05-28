"""Partner referral code capture and session/cookie attribution."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session
from starlette.responses import Response

from app.core.config import get_settings
from app.models.partner import Partner

REFERRAL_CODE_SESSION_KEY = "referral_code"
REFERRAL_PARTNER_ID_SESSION_KEY = "referral_partner_id"
REFERRAL_COOKIE_NAME = "leadcare_ref"
REFERRAL_COOKIE_MAX_AGE_SECONDS = 30 * 24 * 60 * 60


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


def get_referral_code_from_cookie(request) -> str | None:
    raw = request.cookies.get(REFERRAL_COOKIE_NAME)
    if not raw or not str(raw).strip():
        return None
    return str(raw).strip().upper()


def clear_referral_session(request) -> None:
    request.session.pop(REFERRAL_CODE_SESSION_KEY, None)
    request.session.pop(REFERRAL_PARTNER_ID_SESSION_KEY, None)


def _cookie_secure() -> bool:
    return get_settings().app_env.lower() in {"production", "prod"}


def set_referral_cookie(response: Response, referral_code: str) -> None:
    """Persist referral code for 30 days; last click overwrites prior cookie."""
    code = referral_code.strip().upper()
    if not code:
        return
    response.set_cookie(
        key=REFERRAL_COOKIE_NAME,
        value=code,
        max_age=REFERRAL_COOKIE_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=_cookie_secure(),
        path="/",
    )


def capture_referral_for_partner(
    request,
    response: Response | None,
    partner: Partner,
) -> None:
    """Store validated partner attribution in session and optional cookie (last-click wins)."""
    request.session[REFERRAL_CODE_SESSION_KEY] = partner.referral_code
    request.session[REFERRAL_PARTNER_ID_SESSION_KEY] = str(partner.id)
    if response is not None:
        set_referral_cookie(response, partner.referral_code)


def capture_referral_code(
    db: Session,
    request,
    response: Response | None,
    referral_code: str,
) -> Partner | None:
    """Validate code, capture attribution if active partner; return partner or None."""
    partner = get_active_partner_by_referral_code(db, referral_code)
    if partner is None:
        return None
    capture_referral_for_partner(request, response, partner)
    return partner


def resolve_referral_partner(db: Session, request) -> Partner | None:
    """Return active partner from session, else 30-day cookie; clear stale keys."""
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

    cookie_code = get_referral_code_from_cookie(request)
    if cookie_code:
        partner = get_active_partner_by_referral_code(db, cookie_code)
        if partner is not None:
            request.session[REFERRAL_CODE_SESSION_KEY] = partner.referral_code
            request.session[REFERRAL_PARTNER_ID_SESSION_KEY] = str(partner.id)
            return partner

    return None
