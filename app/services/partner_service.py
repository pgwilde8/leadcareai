"""Partner applications, approval workflow, and referral helpers."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

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
APPLICATION_STATUS_DOCS_PENDING = "docs_pending"
APPLICATION_STATUS_DOCS_SIGNED = "docs_signed"
APPLICATION_STATUS_APPROVED = "approved"
APPLICATION_STATUS_REJECTED = "rejected"
DOCS_SIGNING_TOKEN_DAYS = 14
TAX_INFO_TOKEN_DAYS = 14
DOCS_SIGNING_SESSION_KEY = "partner_docs_signing_notice"
TAX_INFO_SESSION_KEY = "partner_tax_info_notice"
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


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _hash_docs_signing_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()


def _generate_docs_signing_token() -> str:
    return secrets.token_urlsafe(32)


def issue_docs_signing_invite(
    db: Session,
    application_id: uuid.UUID,
) -> tuple[str, PartnerApplication]:
    """Create a signing link token; application must be in admin_review."""
    application = get_application(db, application_id)
    if application.status == APPLICATION_STATUS_REJECTED:
        raise ValueError("Cannot invite a rejected application to sign documents.")
    if application.status == APPLICATION_STATUS_APPROVED:
        raise ValueError("Application is already approved.")
    if application.status == APPLICATION_STATUS_DOCS_SIGNED:
        raise ValueError("Documents are already signed.")

    raw = _generate_docs_signing_token()
    application.docs_signing_token_hash = _hash_docs_signing_token(raw)
    application.docs_signing_token_expires_at = datetime.now(timezone.utc) + timedelta(
        days=DOCS_SIGNING_TOKEN_DAYS
    )
    application.status = APPLICATION_STATUS_DOCS_PENDING
    db.flush()
    return raw, application


def get_application_by_docs_signing_token(
    db: Session,
    raw_token: str,
) -> PartnerApplication | None:
    token = (raw_token or "").strip()
    if not token:
        return None
    token_hash = _hash_docs_signing_token(token)
    application = (
        db.query(PartnerApplication)
        .options(joinedload(PartnerApplication.signed_documents))
        .filter(PartnerApplication.docs_signing_token_hash == token_hash)
        .one_or_none()
    )
    if application is None:
        return None
    if application.status not in {APPLICATION_STATUS_DOCS_PENDING, APPLICATION_STATUS_DOCS_SIGNED}:
        return None
    expires = application.docs_signing_token_expires_at
    if expires is not None and _as_utc(expires) < datetime.now(timezone.utc):
        return None
    return application


def _hash_tax_info_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()


def issue_tax_info_token(
    db: Session,
    application_id: uuid.UUID,
) -> tuple[str, PartnerApplication]:
    """Create a W-9 collection link for an applicant who has signed IC documents."""
    from app.services import partner_tax_service

    application = get_application(db, application_id)
    if application.status == APPLICATION_STATUS_REJECTED:
        raise ValueError("Cannot collect tax information for a rejected application.")
    if application.status not in {
        APPLICATION_STATUS_DOCS_SIGNED,
        APPLICATION_STATUS_APPROVED,
    }:
        raise ValueError("IC documents must be signed before collecting W-9 / tax information.")
    if partner_tax_service.get_partner_tax_info_for_application(db, application_id) is not None:
        raise ValueError("W-9 / tax information is already on file.")

    raw = _generate_docs_signing_token()
    application.tax_info_token_hash = _hash_tax_info_token(raw)
    application.tax_info_token_expires_at = datetime.now(timezone.utc) + timedelta(
        days=TAX_INFO_TOKEN_DAYS
    )
    db.flush()
    return raw, application


def get_application_by_tax_info_token(
    db: Session,
    raw_token: str,
) -> PartnerApplication | None:
    token = (raw_token or "").strip()
    if not token:
        return None
    token_hash = _hash_tax_info_token(token)
    application = (
        db.query(PartnerApplication)
        .filter(PartnerApplication.tax_info_token_hash == token_hash)
        .one_or_none()
    )
    if application is None:
        return None
    if application.status not in {
        APPLICATION_STATUS_DOCS_SIGNED,
        APPLICATION_STATUS_APPROVED,
    }:
        return None
    expires = application.tax_info_token_expires_at
    if expires is not None and _as_utc(expires) < datetime.now(timezone.utc):
        return None
    return application


def clear_tax_info_token(db: Session, application_id: uuid.UUID) -> None:
    application = get_application(db, application_id)
    application.tax_info_token_hash = None
    application.tax_info_token_expires_at = None
    db.flush()


def mark_application_docs_signed(
    db: Session,
    application_id: uuid.UUID,
) -> tuple[PartnerApplication, str | None]:
    """Mark docs signed; issue a tax-info token when W-9 is not yet on file."""
    from app.services import partner_tax_service

    application = get_application(db, application_id)
    application.status = APPLICATION_STATUS_DOCS_SIGNED
    application.docs_signing_token_hash = None
    application.docs_signing_token_expires_at = None
    tax_token: str | None = None
    if partner_tax_service.get_partner_tax_info_for_application(db, application_id) is None:
        raw, application = issue_tax_info_token(db, application_id)
        tax_token = raw
    db.flush()
    return application, tax_token


def application_has_tax_info(db: Session, application_id: uuid.UUID) -> bool:
    from app.services import partner_tax_service

    return (
        partner_tax_service.get_partner_tax_info_for_application(db, application_id) is not None
    )


def partner_onboarding_checklist(
    db: Session,
    application: PartnerApplication,
    *,
    signed_doc_count: int,
    active_doc_count: int,
) -> dict[str, str]:
    """Human-readable onboarding step statuses for admin UI."""
    from app.services import partner_tax_service

    has_tax = partner_tax_service.get_partner_tax_info_for_application(db, application.id) is not None
    docs_complete = application.status in {
        APPLICATION_STATUS_DOCS_SIGNED,
        APPLICATION_STATUS_APPROVED,
    } or (signed_doc_count >= active_doc_count and active_doc_count > 0)

    if application.status == APPLICATION_STATUS_REJECTED:
        application_status = "rejected"
    elif application.status == APPLICATION_STATUS_APPROVED:
        application_status = "approved"
    else:
        application_status = "received"

    if application.status == APPLICATION_STATUS_DOCS_PENDING:
        ic_docs_status = "pending"
    elif docs_complete:
        ic_docs_status = "complete"
    elif application.status == APPLICATION_STATUS_ADMIN_REVIEW:
        ic_docs_status = "not started"
    else:
        ic_docs_status = "not started"

    tax_status = "complete" if has_tax else "pending"
    payout_status = "eligible" if has_tax and application.status == APPLICATION_STATUS_APPROVED else "blocked"

    return {
        "application": application_status,
        "ic_documents": ic_docs_status,
        "tax_info": tax_status,
        "payouts": payout_status,
    }


def store_tax_info_notice(
    request,
    *,
    application_id: uuid.UUID,
    tax_info_url: str,
) -> None:
    request.session[TAX_INFO_SESSION_KEY] = {
        "application_id": str(application_id),
        "tax_info_url": tax_info_url,
    }


def pop_tax_info_notice(request, application_id: uuid.UUID) -> dict | None:
    raw = request.session.pop(TAX_INFO_SESSION_KEY, None)
    if not raw or raw.get("application_id") != str(application_id):
        return None
    return raw


def application_ready_for_approval(application: PartnerApplication) -> bool:
    return application.status == APPLICATION_STATUS_DOCS_SIGNED


def store_docs_signing_notice(
    request,
    *,
    application_id: uuid.UUID,
    signing_url: str,
) -> None:
    request.session[DOCS_SIGNING_SESSION_KEY] = {
        "application_id": str(application_id),
        "signing_url": signing_url,
    }


def pop_docs_signing_notice(request, application_id: uuid.UUID) -> dict | None:
    raw = request.session.pop(DOCS_SIGNING_SESSION_KEY, None)
    if not raw or raw.get("application_id") != str(application_id):
        return None
    return raw


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
    if application.status == APPLICATION_STATUS_APPROVED and existing is not None:
        return activate_partner_login(
            db,
            partner=existing,
            application=application,
            created_by_user_id=reviewed_by_user_id,
        )

    if not application_ready_for_approval(application):
        raise ValueError(
            "Applicant must complete independent contractor document signing before approval. "
            "Send the signing link from the application detail page first."
        )

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
