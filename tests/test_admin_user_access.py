"""Admin user access dashboard and per-user invite resend."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.business_user import BusinessUser
from app.models.user import User
from app.models.user_invite_token import UserInviteToken
from app.services.business_service import create_business, link_user_to_business
from app.services.partner_document_service import seed_default_document_templates
from app.services.partner_service import approve_application
from app.services.user_invite_service import BUSINESS_INVITE, PARTNER_INVITE, create_invite_token
from app.services.user_service import create_admin_user, create_user


def _login_admin(client: TestClient, db_session: Session, email: str = "admin@example.com") -> User:
    admin = create_admin_user(db_session, email=email, password="admin-secret")
    db_session.commit()
    client.post("/login", data={"email": email, "password": "admin-secret"})
    return admin


def test_admin_can_view_user_access(client: TestClient, db_session: Session) -> None:
    _login_admin(client, db_session)
    response = client.get("/admin/user-access")
    assert response.status_code == 200
    assert "User Access" in response.text


def test_non_admin_cannot_view_user_access(client: TestClient) -> None:
    response = client.get("/admin/user-access", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_table_shows_business_user_with_linked_business(
    client: TestClient,
    db_session: Session,
) -> None:
    business = create_business(db_session, name="Access Biz Co")
    user = create_user(
        db_session,
        email="biz-access@example.com",
        password="secret",
        role="business_user",
    )
    link_user_to_business(db_session, user.id, business.id)
    create_invite_token(db_session, user_id=user.id, purpose=BUSINESS_INVITE)
    db_session.commit()

    _login_admin(client, db_session)
    response = client.get("/admin/user-access")
    assert response.status_code == 200
    assert "biz-access@example.com" in response.text
    assert "business_user" in response.text
    assert "Access Biz Co" in response.text
    assert "business_invite" in response.text


def test_table_shows_partner_with_referral_code(
    client: TestClient,
    db_session: Session,
) -> None:
    seed_default_document_templates(db_session)
    db_session.commit()
    client.post(
        "/partner/onboard",
        data={
            "first_name": "Access",
            "last_name": "Partner",
            "email": "partner-access@example.com",
            "phone": "+15550000222",
            "city": "Austin",
            "state": "TX",
            "company_name": "",
            "experience_summary": "",
            "why_interested": "",
            "signature_text": "Access Partner",
            "electronic_consent": "on",
        },
    )
    from app.models.partner_application import PartnerApplication

    application = (
        db_session.query(PartnerApplication)
        .filter(PartnerApplication.email == "partner-access@example.com")
        .one()
    )
    admin = _login_admin(client, db_session, email="admin-partner-access@example.com")
    approve_application(db_session, application.id, reviewed_by_user_id=admin.id)
    db_session.commit()

    response = client.get("/admin/user-access")
    assert response.status_code == 200
    assert "partner-access@example.com" in response.text
    assert "partner" in response.text
    assert "partner_invite" in response.text

    from app.models.partner import Partner

    partner = db_session.query(Partner).filter(Partner.application_id == application.id).one()
    assert partner.referral_code in response.text


def test_invite_status_accepted_displayed(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session, email="accepted@example.com", password="secret", role="business_user")
    token, _raw = create_invite_token(db_session, user_id=user.id, purpose=BUSINESS_INVITE)
    token.used_at = datetime.now(timezone.utc)
    db_session.commit()

    _login_admin(client, db_session)
    response = client.get("/admin/user-access?invite_status=accepted")
    assert response.status_code == 200
    assert "accepted@example.com" in response.text
    assert "accepted" in response.text


def test_admin_user_cannot_resend_invite(client: TestClient, db_session: Session) -> None:
    admin = _login_admin(client, db_session)
    response = client.get("/admin/user-access")
    assert response.status_code == 200
    assert f'/admin/users/{admin.id}/resend-invite' not in response.text

    post = client.post(f"/admin/users/{admin.id}/resend-invite", follow_redirects=False)
    assert post.status_code == 303
    assert post.headers["location"] == f"/admin/user-access/{admin.id}"
    db_session.expire_all()
    assert (
        db_session.query(UserInviteToken)
        .filter(UserInviteToken.user_id == admin.id)
        .count()
        == 0
    )


def test_resend_invite_for_business_user_creates_token(
    client: TestClient,
    db_session: Session,
) -> None:
    _login_admin(client, db_session)
    business = create_business(db_session, name="Resend User Co")
    user = create_user(
        db_session,
        email="resend-biz@example.com",
        password="owner-secret",
        role="business_user",
    )
    link_user_to_business(db_session, user.id, business.id)
    db_session.commit()

    response = client.post(f"/admin/users/{user.id}/resend-invite", follow_redirects=False)
    assert response.status_code == 303
    db_session.expire_all()
    token = (
        db_session.query(UserInviteToken)
        .filter(UserInviteToken.user_id == user.id, UserInviteToken.purpose == BUSINESS_INVITE)
        .one_or_none()
    )
    assert token is not None


def test_resend_invite_for_partner_creates_token(
    client: TestClient,
    db_session: Session,
) -> None:
    seed_default_document_templates(db_session)
    db_session.commit()
    client.post(
        "/partner/onboard",
        data={
            "first_name": "Resend",
            "last_name": "Partner",
            "email": "resend-partner@example.com",
            "phone": "+15550000333",
            "city": "Austin",
            "state": "TX",
            "company_name": "",
            "experience_summary": "",
            "why_interested": "",
            "signature_text": "Resend Partner",
            "electronic_consent": "on",
        },
    )
    from app.models.partner_application import PartnerApplication

    application = (
        db_session.query(PartnerApplication)
        .filter(PartnerApplication.email == "resend-partner@example.com")
        .one()
    )
    admin = _login_admin(client, db_session, email="admin-resend-partner@example.com")
    approved = approve_application(db_session, application.id, reviewed_by_user_id=admin.id)
    db_session.commit()
    initial_count = (
        db_session.query(UserInviteToken)
        .filter(UserInviteToken.user_id == approved.user.id, UserInviteToken.purpose == PARTNER_INVITE)
        .count()
    )

    response = client.post(f"/admin/users/{approved.user.id}/resend-invite", follow_redirects=False)
    assert response.status_code == 303
    db_session.expire_all()
    final_count = (
        db_session.query(UserInviteToken)
        .filter(UserInviteToken.user_id == approved.user.id, UserInviteToken.purpose == PARTNER_INVITE)
        .count()
    )
    assert final_count == initial_count + 1


def test_no_token_hash_in_user_access_html(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session, email="hash-check@example.com", password="secret", role="business_user")
    token, raw = create_invite_token(db_session, user_id=user.id, purpose=BUSINESS_INVITE)
    db_session.commit()

    _login_admin(client, db_session)
    list_page = client.get("/admin/user-access")
    detail_page = client.get(f"/admin/user-access/{user.id}")
    assert list_page.status_code == 200
    assert detail_page.status_code == 200
    assert token.token_hash not in list_page.text
    assert token.token_hash not in detail_page.text
    assert raw not in list_page.text
    assert raw not in detail_page.text


def test_email_search_filter(client: TestClient, db_session: Session) -> None:
    create_user(db_session, email="findme@example.com", password="secret", role="business_user")
    create_user(db_session, email="other@example.com", password="secret", role="business_user")
    db_session.commit()

    _login_admin(client, db_session)
    response = client.get("/admin/user-access?q=findme")
    assert response.status_code == 200
    assert "findme@example.com" in response.text
    assert "other@example.com" not in response.text


def test_expired_invite_status_filter(client: TestClient, db_session: Session) -> None:
    user = create_user(db_session, email="expired-row@example.com", password="secret", role="business_user")
    token, _raw = create_invite_token(db_session, user_id=user.id, purpose=BUSINESS_INVITE)
    token.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db_session.commit()

    _login_admin(client, db_session)
    response = client.get("/admin/user-access?invite_status=expired")
    assert response.status_code == 200
    assert "expired-row@example.com" in response.text
