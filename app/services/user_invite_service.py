"""User invite token lifecycle and invite email delivery."""

from __future__ import annotations

import hashlib
import logging
import secrets
import smtplib
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.business import Business
from app.models.business_user import BusinessUser
from app.models.partner import Partner
from app.models.user import User
from app.models.user_invite_token import UserInviteToken
from app.services.business_service import link_user_to_business
from app.services.user_service import create_user, get_user_by_email

logger = logging.getLogger(__name__)

BUSINESS_INVITE = "business_invite"
PARTNER_INVITE = "partner_invite"
PASSWORD_RESET = "password_reset"


@dataclass
class InviteStatus:
    status: str
    token: UserInviteToken | None


@dataclass
class InviteSendResult:
    status: str
    error: str | None


@dataclass
class BusinessInviteResult:
    user: User
    link: BusinessUser
    user_created: bool
    invite_token_created: bool
    invite_delivery_status: str
    invite_delivery_error: str | None = None


@dataclass
class PartnerInviteResult:
    user: User
    user_created: bool
    invite_token_created: bool
    invite_delivery_status: str
    invite_delivery_error: str | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _generate_raw_token() -> str:
    return secrets.token_urlsafe(32)


def _smtp_configured() -> bool:
    settings = get_settings()
    return bool(settings.smtp_host and settings.smtp_from_email)


def _send_email(to_email: str, subject: str, body: str) -> InviteSendResult:
    settings = get_settings()
    if not _smtp_configured():
        return InviteSendResult(status="skipped", error="SMTP not configured")

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from_email
    msg["To"] = to_email
    msg.set_content(body)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
            if settings.smtp_username and settings.smtp_password:
                smtp.starttls()
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(msg)
        return InviteSendResult(status="sent", error=None)
    except Exception as exc:
        logger.exception("Invite email send failed to=%s", to_email)
        return InviteSendResult(status="failed", error=str(exc)[:500])


def _build_accept_invite_url(raw_token: str) -> str:
    base = get_settings().effective_public_base_url or get_settings().app_base_url.rstrip("/")
    return f"{base}/auth/accept-invite?token={raw_token}"


def create_invite_token(
    db: Session,
    *,
    user_id: uuid.UUID,
    purpose: str,
    created_by_user_id: uuid.UUID | None = None,
    expires_in_days: int = 7,
) -> tuple[UserInviteToken, str]:
    raw = _generate_raw_token()
    token = UserInviteToken(
        user_id=user_id,
        token_hash=_hash_token(raw),
        purpose=purpose,
        expires_at=_now() + timedelta(days=max(1, expires_in_days)),
        used_at=None,
        created_by_user_id=created_by_user_id,
    )
    db.add(token)
    db.flush()
    return token, raw


def record_invite_delivery(
    db: Session,
    *,
    token: UserInviteToken,
    status: str,
    error: str | None,
) -> UserInviteToken:
    token.delivery_status = status
    token.delivery_error = error
    db.flush()
    return token


def get_valid_token_by_raw(db: Session, *, raw_token: str) -> UserInviteToken | None:
    token_hash = _hash_token(raw_token.strip())
    token = db.query(UserInviteToken).filter(UserInviteToken.token_hash == token_hash).one_or_none()
    if token is None:
        return None
    if token.used_at is not None:
        return None
    if _as_utc(token.expires_at) <= _now():
        return None
    return token


def consume_invite_and_set_password(
    db: Session,
    *,
    raw_token: str,
    new_password: str,
) -> User | None:
    token = get_valid_token_by_raw(db, raw_token=raw_token)
    if token is None:
        return None
    user = db.get(User, token.user_id)
    if user is None or not user.is_active:
        return None
    user.hashed_password = hash_password(new_password)
    token.used_at = _now()
    db.flush()
    return user


def latest_invite_status(db: Session, *, user_id: uuid.UUID, purpose: str) -> InviteStatus:
    token = (
        db.query(UserInviteToken)
        .filter(UserInviteToken.user_id == user_id, UserInviteToken.purpose == purpose)
        .order_by(UserInviteToken.created_at.desc())
        .first()
    )
    if token is None:
        return InviteStatus(status="not needed", token=None)
    if token.used_at is not None:
        return InviteStatus(status="accepted", token=token)
    if _as_utc(token.expires_at) <= _now():
        return InviteStatus(status="expired", token=token)
    if token.delivery_status in {"failed", "skipped"}:
        return InviteStatus(status=token.delivery_status, token=token)
    return InviteStatus(status="sent", token=token)


def _ensure_business_link(db: Session, *, user: User, business: Business) -> BusinessUser:
    existing = (
        db.query(BusinessUser)
        .filter(BusinessUser.user_id == user.id, BusinessUser.business_id == business.id)
        .one_or_none()
    )
    if existing is not None:
        return existing
    return link_user_to_business(db, user.id, business.id, role="owner")


def _send_business_invite_email(*, email: str, business_name: str, invite_url: str) -> InviteSendResult:
    subject = "Your LeadCare AI account is ready"
    body = (
        f"Welcome to LeadCare AI.\n\n"
        f"Your business account for {business_name} is ready.\n"
        f"Set your password and sign in here:\n{invite_url}\n\n"
        "If you did not expect this email, contact support."
    )
    return _send_email(email, subject, body)


def _send_partner_invite_email(*, email: str, invite_url: str) -> InviteSendResult:
    subject = "Your LeadCare AI partner account is ready"
    body = (
        "Welcome to LeadCare AI Partner.\n\n"
        "Your partner back-office access is ready.\n"
        f"Set your password and sign in here:\n{invite_url}\n\n"
        "After sign-in, you can access your referral dashboard."
    )
    return _send_email(email, subject, body)


def create_or_invite_business_user_for_business(
    db: Session,
    *,
    business: Business,
    email: str,
    full_name: str | None = None,
    created_by_user_id: uuid.UUID | None = None,
    resend: bool = False,
) -> BusinessInviteResult:
    normalized = email.strip().lower()
    if not normalized:
        raise ValueError("Business contact email is required for invite")

    existing = get_user_by_email(db, normalized)
    user_created = False
    if existing is None:
        # Internal bootstrap secret; user must still set their own password via invite.
        existing = create_user(
            db,
            email=normalized,
            password=secrets.token_urlsafe(24),
            full_name=full_name,
            role="business_user",
        )
        user_created = True
    elif existing.role == "admin":
        raise ValueError("Cannot invite admin user as business user")
    elif existing.role != "business_user":
        raise ValueError(f"Cannot invite user with role {existing.role!r} as business user")

    link = _ensure_business_link(db, user=existing, business=business)
    should_invite = user_created or resend
    if not should_invite:
        return BusinessInviteResult(
            user=existing,
            link=link,
            user_created=user_created,
            invite_token_created=False,
            invite_delivery_status="not needed",
        )

    token, raw = create_invite_token(
        db,
        user_id=existing.id,
        purpose=BUSINESS_INVITE,
        created_by_user_id=created_by_user_id,
    )
    invite_url = _build_accept_invite_url(raw)
    delivery = _send_business_invite_email(
        email=existing.email,
        business_name=business.name,
        invite_url=invite_url,
    )
    record_invite_delivery(db, token=token, status=delivery.status, error=delivery.error)
    return BusinessInviteResult(
        user=existing,
        link=link,
        user_created=user_created,
        invite_token_created=True,
        invite_delivery_status=delivery.status,
        invite_delivery_error=delivery.error,
    )


def create_or_invite_partner_user(
    db: Session,
    *,
    partner: Partner,
    email: str,
    full_name: str | None = None,
    created_by_user_id: uuid.UUID | None = None,
    resend: bool = False,
) -> PartnerInviteResult:
    normalized = email.strip().lower()
    existing = get_user_by_email(db, normalized)
    user_created = False
    if existing is None:
        existing = create_user(
            db,
            email=normalized,
            password=secrets.token_urlsafe(24),
            full_name=full_name,
            role="partner",
        )
        user_created = True
    elif existing.role == "admin":
        raise ValueError("Cannot link partner login: email belongs to an admin account")
    elif existing.role not in {"partner", "business_user"}:
        raise ValueError(f"Cannot link partner login: unsupported role {existing.role!r}")
    elif existing.role == "business_user":
        existing.role = "partner"
        existing.is_active = True

    partner.user_id = existing.id
    db.flush()

    should_invite = user_created or resend
    if not should_invite:
        return PartnerInviteResult(
            user=existing,
            user_created=user_created,
            invite_token_created=False,
            invite_delivery_status="not needed",
        )

    token, raw = create_invite_token(
        db,
        user_id=existing.id,
        purpose=PARTNER_INVITE,
        created_by_user_id=created_by_user_id,
    )
    invite_url = _build_accept_invite_url(raw)
    delivery = _send_partner_invite_email(email=existing.email, invite_url=invite_url)
    record_invite_delivery(db, token=token, status=delivery.status, error=delivery.error)
    return PartnerInviteResult(
        user=existing,
        user_created=user_created,
        invite_token_created=True,
        invite_delivery_status=delivery.status,
        invite_delivery_error=delivery.error,
    )
