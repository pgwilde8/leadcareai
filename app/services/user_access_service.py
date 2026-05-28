"""Admin user access overview and invite resend helpers."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session, joinedload

from app.models.business import Business
from app.models.business_user import BusinessUser
from app.models.partner import Partner
from app.models.user import User
from app.models.user_invite_token import UserInviteToken
from app.services import user_invite_service
from app.services.business_service import get_primary_business_for_user
from app.services.partner_service import get_partner_for_user
from app.services.user_service import get_user_by_id

INVITE_STATUSES = frozenset({"sent", "failed", "skipped", "accepted", "expired", "not needed"})


@dataclass(frozen=True)
class UserAccessRow:
    user_id: uuid.UUID
    email: str
    role: str
    is_active: bool
    linked_business_name: str | None
    linked_business_id: uuid.UUID | None
    linked_partner_name: str | None
    linked_partner_id: uuid.UUID | None
    linked_partner_application_id: uuid.UUID | None
    partner_referral_code: str | None
    invite_purpose: str | None
    invite_status: str
    invite_created_at: datetime | None
    invite_expires_at: datetime | None
    invite_used_at: datetime | None
    can_resend: bool


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def invite_token_status(token: UserInviteToken) -> str:
    if token.used_at is not None:
        return "accepted"
    if _as_utc(token.expires_at) <= datetime.now(timezone.utc):
        return "expired"
    if token.delivery_status in {"failed", "skipped"}:
        return token.delivery_status
    return "sent"


def _purpose_for_role(role: str) -> str | None:
    if role == "business_user":
        return user_invite_service.BUSINESS_INVITE
    if role == "partner":
        return user_invite_service.PARTNER_INVITE
    return None


def _latest_token_for_user(
    db: Session,
    *,
    user_id: uuid.UUID,
    purpose: str | None,
) -> UserInviteToken | None:
    query = db.query(UserInviteToken).filter(UserInviteToken.user_id == user_id)
    if purpose:
        query = query.filter(UserInviteToken.purpose == purpose)
    return query.order_by(UserInviteToken.created_at.desc()).first()


def _build_row(db: Session, user: User) -> UserAccessRow:
    business_name = None
    business_id = None
    partner_name = None
    partner_id = None
    partner_app_id = None
    referral_code = None

    if user.role == "business_user":
        link = (
            db.query(BusinessUser)
            .options(joinedload(BusinessUser.business))
            .filter(BusinessUser.user_id == user.id)
            .order_by(BusinessUser.created_at.asc())
            .first()
        )
        if link and link.business:
            business_name = link.business.name
            business_id = link.business_id

    if user.role == "partner":
        partner = (
            db.query(Partner)
            .filter(Partner.user_id == user.id)
            .one_or_none()
        )
        if partner:
            partner_name = partner.display_name
            partner_id = partner.id
            partner_app_id = partner.application_id
            referral_code = partner.referral_code

    purpose = _purpose_for_role(user.role)
    token = _latest_token_for_user(db, user_id=user.id, purpose=purpose) if purpose else None
    if token:
        invite_status = invite_token_status(token)
        invite_purpose = token.purpose
        invite_created = token.created_at
        invite_expires = token.expires_at
        invite_used = token.used_at
    else:
        invite_status = "not needed"
        invite_purpose = purpose
        invite_created = None
        invite_expires = None
        invite_used = None

    can_resend = user.role in {"business_user", "partner"} and user.is_active

    return UserAccessRow(
        user_id=user.id,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        linked_business_name=business_name,
        linked_business_id=business_id,
        linked_partner_name=partner_name,
        linked_partner_id=partner_id,
        linked_partner_application_id=partner_app_id,
        partner_referral_code=referral_code,
        invite_purpose=invite_purpose,
        invite_status=invite_status,
        invite_created_at=invite_created,
        invite_expires_at=invite_expires,
        invite_used_at=invite_used,
        can_resend=can_resend,
    )


def list_user_access_rows(
    db: Session,
    *,
    role: str | None = None,
    invite_status: str | None = None,
    q: str | None = None,
) -> list[UserAccessRow]:
    query = db.query(User).order_by(User.created_at.desc())
    role_v = (role or "").strip().lower()
    if role_v:
        query = query.filter(User.role == role_v)
    q_v = (q or "").strip().lower()
    if q_v:
        query = query.filter(User.email.ilike(f"%{q_v}%"))

    users = query.all()
    rows = [_build_row(db, user) for user in users]

    status_v = (invite_status or "").strip().lower()
    if status_v:
        rows = [row for row in rows if row.invite_status == status_v]
    return rows


def list_invite_history(db: Session, *, user_id: uuid.UUID) -> list[UserInviteToken]:
    return (
        db.query(UserInviteToken)
        .filter(UserInviteToken.user_id == user_id)
        .order_by(UserInviteToken.created_at.desc())
        .all()
    )


def get_user_access_row(db: Session, user_id: uuid.UUID) -> UserAccessRow:
    user = get_user_by_id(db, user_id)
    if user is None:
        raise ValueError("User not found")
    return _build_row(db, user)


def resend_invite_for_user(
    db: Session,
    *,
    user_id: uuid.UUID,
    created_by_user_id: uuid.UUID | None = None,
) -> str:
    """Resend role-appropriate invite. Returns delivery status string."""
    user = get_user_by_id(db, user_id)
    if user is None:
        raise ValueError("User not found")
    if user.role == "admin":
        raise ValueError("Cannot resend invite for admin users")
    if not user.is_active:
        raise ValueError("Cannot resend invite for inactive user")

    if user.role == "business_user":
        business = get_primary_business_for_user(db, user.id)
        if business is None:
            raise ValueError("No business linked to this user")
        result = user_invite_service.create_or_invite_business_user_for_business(
            db,
            business=business,
            email=user.email,
            full_name=user.full_name,
            created_by_user_id=created_by_user_id,
            resend=True,
        )
        return result.invite_delivery_status

    if user.role == "partner":
        partner = get_partner_for_user(db, user.id)
        if partner is None:
            raise ValueError("No partner record linked to this user")
        result = user_invite_service.create_or_invite_partner_user(
            db,
            partner=partner,
            email=user.email,
            full_name=user.full_name or partner.display_name,
            created_by_user_id=created_by_user_id,
            resend=True,
        )
        return result.invite_delivery_status

    raise ValueError(f"Cannot resend invite for role {user.role!r}")
