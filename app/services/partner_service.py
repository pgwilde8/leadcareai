"""Partner applications, approval workflow, and referral helpers."""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session, joinedload

from app.models.partner import Partner
from app.models.partner_application import APPLICATION_STATUSES, PartnerApplication
from app.models.partner_signed_document import PartnerSignedDocument
from app.models.user import User
from app.services import user_invite_service
from app.services.user_service import (
    get_user_by_email,
    get_user_by_id,
)

APPLICATION_STATUS_ADMIN_REVIEW = "admin_review"
APPLICATION_STATUS_APPROVED = "approved"
APPLICATION_STATUS_REJECTED = "rejected"
PARTNER_STATUS_ACTIVE = "active"
PARTNER_STATUS_REJECTED = "rejected"

PARTNER_ACTIVATION_SESSION_KEY = "partner_activation_notice"


@dataclass
class PartnerApprovalResult:
    partner: Partner
    user: User
    user_was_created: bool = False
    invite_status: str = "not needed"
    invite_error: str | None = None


def _normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not normalized:
        raise ValueError("Email must not be empty")
    return normalized


def _generate_referral_code(db: Session) -> str:
    for _ in range(20):
        code = f"LC{secrets.token_hex(4).upper()}"
        exists = db.query(Partner).filter(Partner.referral_code == code).one_or_none()
        if exists is None:
            return code
    raise RuntimeError("Could not generate unique referral code")


def activate_partner_login(
    db: Session,
    *,
    partner: Partner,
    application: PartnerApplication,
    created_by_user_id: uuid.UUID | None = None,
    resend_invite: bool = False,
) -> PartnerApprovalResult:
    """Create or link a User for partner login and issue invite when needed."""
    if partner.user_id is not None:
        user = get_user_by_id(db, partner.user_id)
        if user is None:
            partner.user_id = None
        else:
            result = user_invite_service.create_or_invite_partner_user(
                db,
                partner=partner,
                email=user.email,
                full_name=partner.display_name,
                created_by_user_id=created_by_user_id,
                resend=resend_invite,
            )
            return PartnerApprovalResult(
                partner=partner,
                user=result.user,
                user_was_created=result.user_created,
                invite_status=result.invite_delivery_status,
                invite_error=result.invite_delivery_error,
            )

    user = get_user_by_email(db, application.email)
    if user is not None:
        existing_partner_for_user = (
            db.query(Partner)
            .filter(Partner.user_id == user.id, Partner.id != partner.id)
            .one_or_none()
        )
        if existing_partner_for_user is not None:
            raise ValueError("Cannot link partner login: user is already linked to another partner")

    result = user_invite_service.create_or_invite_partner_user(
        db,
        partner=partner,
        email=application.email,
        full_name=partner.display_name,
        created_by_user_id=created_by_user_id,
        resend=resend_invite,
    )
    return PartnerApprovalResult(
        partner=partner,
        user=result.user,
        user_was_created=result.user_created,
        invite_status=result.invite_delivery_status,
        invite_error=result.invite_delivery_error,
    )


def list_applications(
    db: Session,
    *,
    status: str | None = None,
) -> list[PartnerApplication]:
    query = db.query(PartnerApplication).order_by(PartnerApplication.created_at.desc())
    if status:
        if status not in APPLICATION_STATUSES:
            raise ValueError(f"Invalid application status: {status!r}")
        query = query.filter(PartnerApplication.status == status)
    return query.all()


def list_partners(db: Session) -> list[Partner]:
    return db.query(Partner).order_by(Partner.created_at.desc()).all()


def get_application(db: Session, application_id: uuid.UUID) -> PartnerApplication:
    application = (
        db.query(PartnerApplication)
        .options(
            joinedload(PartnerApplication.signed_documents),
            joinedload(PartnerApplication.partner).joinedload(Partner.user),
        )
        .filter(PartnerApplication.id == application_id)
        .one_or_none()
    )
    if application is None:
        raise ValueError("Partner application not found")
    return application


def get_partner_for_user(db: Session, user_id: uuid.UUID) -> Partner | None:
    return db.query(Partner).filter(Partner.user_id == user_id).one_or_none()


def get_partner_by_application(db: Session, application_id: uuid.UUID) -> Partner | None:
    return (
        db.query(Partner)
        .options(joinedload(Partner.user))
        .filter(Partner.application_id == application_id)
        .one_or_none()
    )


def create_application(
    db: Session,
    *,
    first_name: str,
    last_name: str,
    email: str,
    phone: str,
    city: str,
    state: str,
    company_name: str | None = None,
    experience_summary: str | None = None,
    why_interested: str | None = None,
) -> PartnerApplication:
    if not first_name.strip():
        raise ValueError("First name is required")
    if not last_name.strip():
        raise ValueError("Last name is required")
    if not phone.strip():
        raise ValueError("Phone is required")
    if not city.strip():
        raise ValueError("City is required")
    if not state.strip():
        raise ValueError("State is required")

    application = PartnerApplication(
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        email=_normalize_email(email),
        phone=phone.strip(),
        city=city.strip(),
        state=state.strip(),
        company_name=company_name.strip() if company_name and company_name.strip() else None,
        experience_summary=experience_summary.strip() if experience_summary else None,
        why_interested=why_interested.strip() if why_interested else None,
        status="applied",
    )
    db.add(application)
    db.flush()
    return application


def mark_application_admin_review(db: Session, application_id: uuid.UUID) -> PartnerApplication:
    application = get_application(db, application_id)
    application.status = APPLICATION_STATUS_ADMIN_REVIEW
    db.flush()
    return application


def list_signed_documents_for_application(
    db: Session,
    application_id: uuid.UUID,
) -> list[PartnerSignedDocument]:
    return (
        db.query(PartnerSignedDocument)
        .filter(PartnerSignedDocument.application_id == application_id)
        .order_by(PartnerSignedDocument.document_code)
        .all()
    )


def approve_application(
    db: Session,
    application_id: uuid.UUID,
    *,
    reviewed_by_user_id: uuid.UUID,
) -> PartnerApprovalResult:
    application = get_application(db, application_id)
    if application.status == APPLICATION_STATUS_REJECTED:
        raise ValueError("Cannot approve a rejected application")

    existing = get_partner_by_application(db, application_id)
    if existing is not None:
        partner = existing
        if partner.status != PARTNER_STATUS_ACTIVE:
            partner.status = PARTNER_STATUS_ACTIVE
            partner.approved_at = partner.approved_at or datetime.now(timezone.utc)
        application.status = APPLICATION_STATUS_APPROVED
        application.reviewed_at = datetime.now(timezone.utc)
        application.reviewed_by_user_id = reviewed_by_user_id
        application.rejection_reason = None
        db.flush()
        return activate_partner_login(
            db,
            partner=partner,
            application=application,
            created_by_user_id=reviewed_by_user_id,
        )

    display_name = f"{application.first_name} {application.last_name}".strip()
    partner = Partner(
        application_id=application.id,
        user_id=None,
        display_name=display_name,
        email=application.email,
        phone=application.phone,
        referral_code=_generate_referral_code(db),
        status=PARTNER_STATUS_ACTIVE,
        approved_at=datetime.now(timezone.utc),
    )
    db.add(partner)
    application.status = APPLICATION_STATUS_APPROVED
    application.reviewed_at = datetime.now(timezone.utc)
    application.reviewed_by_user_id = reviewed_by_user_id
    application.rejection_reason = None
    db.flush()
    return activate_partner_login(
        db,
        partner=partner,
        application=application,
        created_by_user_id=reviewed_by_user_id,
    )


def reject_application(
    db: Session,
    application_id: uuid.UUID,
    *,
    reviewed_by_user_id: uuid.UUID,
    rejection_reason: str,
) -> PartnerApplication:
    application = get_application(db, application_id)
    if application.status == APPLICATION_STATUS_APPROVED:
        raise ValueError("Cannot reject an approved application")

    reason = rejection_reason.strip()
    if not reason:
        raise ValueError("Rejection reason is required")

    application.status = APPLICATION_STATUS_REJECTED
    application.reviewed_at = datetime.now(timezone.utc)
    application.reviewed_by_user_id = reviewed_by_user_id
    application.rejection_reason = reason

    partner = get_partner_by_application(db, application_id)
    if partner is not None and partner.status != PARTNER_STATUS_REJECTED:
        partner.status = PARTNER_STATUS_REJECTED

    db.flush()
    return application


def pop_activation_notice(request, application_id: uuid.UUID) -> dict | None:
    """Return one-time activation notice from session, then clear it."""
    raw = request.session.pop(PARTNER_ACTIVATION_SESSION_KEY, None)
    if not raw or raw.get("application_id") != str(application_id):
        return None
    return raw


def store_activation_notice(
    request,
    *,
    application_id: uuid.UUID,
    login_email: str,
    invite_status: str,
    invite_error: str | None,
    user_was_created: bool,
) -> None:
    if invite_status == "not needed":
        return
    request.session[PARTNER_ACTIVATION_SESSION_KEY] = {
        "application_id": str(application_id),
        "login_email": login_email,
        "invite_status": invite_status,
        "invite_error": invite_error,
        "user_was_created": user_was_created,
    }
