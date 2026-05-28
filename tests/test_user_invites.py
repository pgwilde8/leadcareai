"""Invite-token flows for business and partner access."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.models.business_user import BusinessUser
from app.models.user import User
from app.models.user_invite_token import UserInviteToken
from app.services.business_service import create_business
from app.services.partner_service import approve_application
from app.services.partner_document_service import seed_default_document_templates
from app.services.user_invite_service import (
    BUSINESS_INVITE,
    PARTNER_INVITE,
    create_invite_token,
    create_or_invite_business_user_for_business,
)
from app.services.user_service import create_admin_user


def test_invite_token_stores_hash_not_raw(db_session: Session) -> None:
    user = User(email="hash@test.example", hashed_password="hashed", role="business_user", is_active=True)
    db_session.add(user)
    db_session.flush()
    token, raw = create_invite_token(db_session, user_id=user.id, purpose=BUSINESS_INVITE)
    assert token.token_hash != raw
    assert len(token.token_hash) >= 64


def test_accept_invite_sets_password_and_single_use(client: TestClient, db_session: Session) -> None:
    user = User(email="invite@test.example", hashed_password="hashed", role="business_user", is_active=True)
    db_session.add(user)
    db_session.flush()
    _token, raw = create_invite_token(db_session, user_id=user.id, purpose=BUSINESS_INVITE)
    db_session.commit()

    page = client.get(f"/auth/accept-invite?token={raw}")
    assert page.status_code == 200
    assert "Set your password" in page.text

    post = client.post(
        "/auth/accept-invite",
        data={"token": raw, "password": "new-secret-123", "password_confirm": "new-secret-123"},
        follow_redirects=False,
    )
    assert post.status_code == 303
    assert post.headers["location"] == "/login"

    db_session.expire_all()
    refreshed = db_session.get(User, user.id)
    assert refreshed is not None
    assert verify_password("new-secret-123", refreshed.hashed_password)
    used = db_session.query(UserInviteToken).filter(UserInviteToken.user_id == user.id).one()
    assert used.used_at is not None

    reuse = client.post(
        "/auth/accept-invite",
        data={"token": raw, "password": "again-secret", "password_confirm": "again-secret"},
    )
    assert reuse.status_code == 400
    assert "invalid or expired" in reuse.text.lower()


def test_expired_invite_rejected(client: TestClient, db_session: Session) -> None:
    user = User(email="expired@test.example", hashed_password="hashed", role="business_user", is_active=True)
    db_session.add(user)
    db_session.flush()
    token, raw = create_invite_token(db_session, user_id=user.id, purpose=BUSINESS_INVITE)
    token.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()

    page = client.get(f"/auth/accept-invite?token={raw}")
    assert page.status_code == 200
    assert "invalid or expired" in page.text.lower()


def test_business_invite_creates_or_reuses_user_and_link(db_session: Session) -> None:
    biz = create_business(db_session, name="Invite Biz")
    result = create_or_invite_business_user_for_business(
        db_session,
        business=biz,
        email="owner@invitebiz.example",
        full_name="Owner",
    )
    db_session.commit()
    assert result.user_created is True
    assert result.user.role == "business_user"
    link = (
        db_session.query(BusinessUser)
        .filter(BusinessUser.business_id == biz.id, BusinessUser.user_id == result.user.id)
        .one_or_none()
    )
    assert link is not None
    token = (
        db_session.query(UserInviteToken)
        .filter(UserInviteToken.user_id == result.user.id, UserInviteToken.purpose == BUSINESS_INVITE)
        .one_or_none()
    )
    assert token is not None
    assert result.invite_delivery_status in {"sent", "failed", "skipped"}

    reused = create_or_invite_business_user_for_business(
        db_session,
        business=biz,
        email="owner@invitebiz.example",
        full_name="Owner",
    )
    assert reused.user_created is False
    assert reused.invite_token_created is False
    assert reused.invite_delivery_status == "not needed"


def test_partner_approval_creates_invite_token_and_no_duplicate_on_repeat(
    client: TestClient,
    db_session: Session,
) -> None:
    seed_default_document_templates(db_session)
    db_session.commit()
    client.post(
        "/partner/onboard",
        data={
            "first_name": "Inv",
            "last_name": "Partner",
            "email": "inv.partner@example.com",
            "phone": "+15550000111",
            "city": "Austin",
            "state": "TX",
            "company_name": "",
            "experience_summary": "",
            "why_interested": "",
            "signature_text": "Inv Partner",
            "electronic_consent": "on",
        },
    )
    from app.models.partner_application import PartnerApplication

    application = (
        db_session.query(PartnerApplication)
        .filter(PartnerApplication.email == "inv.partner@example.com")
        .one()
    )
    admin = create_admin_user(db_session, email="admin-invite@example.com", password="admin-secret")
    db_session.commit()

    first = approve_application(db_session, application.id, reviewed_by_user_id=admin.id)
    db_session.commit()
    assert first.invite_status in {"sent", "failed", "skipped"}

    second = approve_application(db_session, application.id, reviewed_by_user_id=admin.id)
    db_session.commit()
    assert second.user.id == first.user.id

    tokens = (
        db_session.query(UserInviteToken)
        .filter(UserInviteToken.user_id == first.user.id, UserInviteToken.purpose == PARTNER_INVITE)
        .all()
    )
    assert len(tokens) == 1


def test_admin_email_not_convertible_to_partner_or_business(db_session: Session) -> None:
    admin = create_admin_user(db_session, email="shared-admin@example.com", password="admin-secret")
    biz = create_business(db_session, name="Admin Block Co")
    db_session.commit()

    try:
        create_or_invite_business_user_for_business(
            db_session,
            business=biz,
            email=admin.email,
            full_name="Admin User",
        )
    except ValueError as exc:
        assert "admin" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError when inviting admin as business user")

    seed_default_document_templates(db_session)
    db_session.commit()
    from app.models.partner_application import PartnerApplication

    app = PartnerApplication(
        first_name="Admin",
        last_name="Partner",
        email=admin.email,
        phone="+15550001111",
        city="Austin",
        state="TX",
        status="admin_review",
    )
    db_session.add(app)
    db_session.flush()
    try:
        approve_application(db_session, app.id, reviewed_by_user_id=admin.id)
    except ValueError as exc:
        assert "admin" in str(exc).lower()
    else:
        raise AssertionError("Expected ValueError when approving admin as partner")
