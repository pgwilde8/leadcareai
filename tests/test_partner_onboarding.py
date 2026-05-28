"""Partner onboarding, admin review, login activation, and dashboard (V1/V2B)."""

from __future__ import annotations

import re
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.partner import Partner
from app.models.partner_application import PartnerApplication
from app.models.partner_signed_document import PartnerSignedDocument
from app.models.user import User
from app.models.user_invite_token import UserInviteToken
from app.models.partner_tax_info import PartnerTaxInfo
from app.services.partner_document_service import load_document_body, seed_default_document_templates
from app.core.field_encryption import decrypt_field
from app.services.partner_service import approve_application, get_partner_by_application
from app.services.user_service import create_admin_user, create_user, get_user_by_email
from tests.partner_fixtures import (
    ensure_partner_application_docs_signed,
    ensure_partner_application_tax_info,
    partner_onboard_form_data,
    partner_sign_documents_form_data,
    partner_tax_info_form_data,
)


def _login_admin(client: TestClient, db_session: Session) -> User:
    admin = create_admin_user(db_session, email="admin@example.com", password="admin-secret")
    db_session.commit()
    client.post(
        "/login",
        data={"email": "admin@example.com", "password": "admin-secret"},
    )
    return admin


def _submit_and_get_application(client: TestClient, db_session: Session, email: str) -> PartnerApplication:
    client.post("/partner/onboard", data=partner_onboard_form_data(email=email))
    return (
        db_session.query(PartnerApplication)
        .filter(PartnerApplication.email == email)
        .one()
    )


def _submit_sign_and_get_application(
    client: TestClient, db_session: Session, email: str
) -> PartnerApplication:
    application = _submit_and_get_application(client, db_session, email)
    ensure_partner_application_docs_signed(db_session, application.id)
    ensure_partner_application_tax_info(db_session, application.id)
    db_session.commit()
    db_session.refresh(application)
    return application


def test_seed_loads_markdown_document_content(db_session: Session) -> None:
    body = load_document_body("independent_contractor_agreement")
    assert "DRAFT PLACEHOLDER" in body
    assert "Independent Contractor Sales Partner Agreement" in body

    seed_default_document_templates(db_session)
    db_session.commit()
    from app.services.partner_document_service import get_document_template_by_code

    template = get_document_template_by_code(db_session, "independent_contractor_agreement")
    assert template is not None
    assert "Independent Contractor Sales Partner Agreement" in template.body


def test_get_partner_onboard_returns_200(client: TestClient) -> None:
    response = client.get("/partner/onboard")
    assert response.status_code == 200
    assert "Partner application" in response.text
    assert "separate link" in response.text.lower()
    assert "Independent Contractor Agreement" not in response.text


def test_partner_onboard_page_has_no_tax_form_fields(client: TestClient) -> None:
    response = client.get("/partner/onboard")
    assert response.status_code == 200
    text = response.text.lower()
    assert 'name="tax_legal_name"' not in text
    assert 'name="tax_tin"' not in text
    assert 'name="tax_certification"' not in text
    assert "federal tax classification" not in text
    assert "taxpayer id" not in text


def test_post_partner_onboard_creates_application_without_signed_docs(
    client: TestClient,
    db_session: Session,
) -> None:
    _submit_and_get_application(client, db_session, "pat.ner@example.com")

    application = (
        db_session.query(PartnerApplication)
        .filter(PartnerApplication.email == "pat.ner@example.com")
        .one()
    )
    assert application.status == "admin_review"
    assert application.first_name == "Pat"

    signed = (
        db_session.query(PartnerSignedDocument)
        .filter(PartnerSignedDocument.application_id == application.id)
        .all()
    )
    assert signed == []

    tax_count = (
        db_session.query(PartnerTaxInfo)
        .filter(PartnerTaxInfo.application_id == application.id)
        .count()
    )
    assert tax_count == 0


def test_admin_invite_shows_signing_link_once(
    client: TestClient,
    db_session: Session,
) -> None:
    application = _submit_and_get_application(client, db_session, "signlink@example.com")
    _login_admin(client, db_session)

    invite = client.post(
        f"/admin/partners/{application.id}/invite-sign-documents",
        follow_redirects=False,
    )
    assert invite.status_code == 303

    first = client.get(f"/admin/partners/{application.id}")
    assert first.status_code == 200
    assert "IC document signing link" in first.text
    match = re.search(r"/partner/sign-documents\?token=([A-Za-z0-9_-]+)", first.text)
    assert match is not None

    second = client.get(f"/admin/partners/{application.id}")
    assert "IC document signing link" not in second.text

    db_session.refresh(application)
    assert application.status == "docs_pending"


def test_partner_sign_documents_via_invite_token(
    client: TestClient,
    db_session: Session,
) -> None:
    application = _submit_and_get_application(client, db_session, "signflow@example.com")
    from app.services import partner_service

    raw, _ = partner_service.issue_docs_signing_invite(db_session, application.id)
    db_session.commit()

    sign_get = client.get(f"/partner/sign-documents?token={raw}")
    assert sign_get.status_code == 200
    assert "Independent Contractor" in sign_get.text or "Documents to sign" in sign_get.text

    sign_post = client.post(
        f"/partner/sign-documents?token={raw}",
        data=partner_sign_documents_form_data(signature_text="Sign Flow"),
        follow_redirects=False,
    )
    assert sign_post.status_code == 303
    assert sign_post.headers["location"].startswith("/partner/tax-info?token=")

    tax_token = sign_post.headers["location"].split("token=", 1)[1]
    tax_post = client.post(
        f"/partner/tax-info?token={tax_token}",
        data=partner_tax_info_form_data(
            tax_legal_name="Sign Flow",
            tax_tin="987654321",
        ),
        follow_redirects=False,
    )
    assert tax_post.status_code == 303
    assert tax_post.headers["location"] == "/partner/tax-info/success"

    db_session.expire_all()
    db_session.refresh(application)
    assert application.status == "docs_signed"

    signed = (
        db_session.query(PartnerSignedDocument)
        .filter(PartnerSignedDocument.application_id == application.id)
        .all()
    )
    assert len(signed) == 5
    for doc in signed:
        assert doc.document_snapshot
        assert doc.signature_text == "Sign Flow"

    tax = (
        db_session.query(PartnerTaxInfo)
        .filter(PartnerTaxInfo.application_id == application.id)
        .one()
    )
    assert tax.legal_name == "Sign Flow"
    assert decrypt_field(tax.tin_encrypted) == "987654321"


def test_admin_cannot_approve_before_docs_signed(
    client: TestClient,
    db_session: Session,
) -> None:
    application = _submit_and_get_application(client, db_session, "nosign@example.com")
    _login_admin(client, db_session)

    response = client.post(f"/admin/partners/{application.id}/approve")
    assert response.status_code == 400
    assert "document signing" in response.text.lower()


def test_admin_partners_list_shows_application(
    client: TestClient,
    db_session: Session,
) -> None:
    _submit_and_get_application(client, db_session, "list@example.com")
    _login_admin(client, db_session)

    response = client.get("/admin/partners")
    assert response.status_code == 200
    assert "list@example.com" in response.text
    assert "admin_review" in response.text


def test_admin_approve_creates_active_partner_with_referral_code(
    client: TestClient,
    db_session: Session,
) -> None:
    application = _submit_sign_and_get_application(client, db_session, "approve@example.com")
    _login_admin(client, db_session)

    response = client.post(
        f"/admin/partners/{application.id}/approve",
        follow_redirects=False,
    )
    assert response.status_code == 303

    db_session.expire_all()
    partner = get_partner_by_application(db_session, application.id)
    assert partner is not None
    assert partner.status == "active"
    assert partner.referral_code.startswith("LC")
    assert len(partner.referral_code) >= 6

    db_session.refresh(application)
    assert application.status == "approved"


def test_approve_creates_partner_user_with_role_partner(
    client: TestClient,
    db_session: Session,
) -> None:
    application = _submit_and_get_application(client, db_session, "login@example.com")
    ensure_partner_application_docs_signed(db_session, application.id)
    db_session.commit()
    admin = _login_admin(client, db_session)

    result = approve_application(
        db_session,
        application.id,
        reviewed_by_user_id=admin.id,
    )
    db_session.commit()

    assert result.user.role == "partner"
    assert result.user.is_active is True
    assert result.partner.user_id == result.user.id
    assert result.invite_status in {"sent", "skipped", "failed"}
    assert result.user_was_created is True

    user = get_user_by_email(db_session, "login@example.com")
    assert user is not None
    assert user.role == "partner"
    invite = (
        db_session.query(UserInviteToken)
        .filter(UserInviteToken.user_id == user.id, UserInviteToken.purpose == "partner_invite")
        .one_or_none()
    )
    assert invite is not None
    assert invite.token_hash


def test_approve_shows_invite_status_notice(
    client: TestClient,
    db_session: Session,
) -> None:
    application = _submit_sign_and_get_application(client, db_session, "temppw@example.com")
    _login_admin(client, db_session)

    client.post(f"/admin/partners/{application.id}/approve", follow_redirects=False)
    first = client.get(f"/admin/partners/{application.id}")
    assert first.status_code == 200
    assert "Partner login invite" in first.text
    assert "temppw@example.com" in first.text

    second = client.get(f"/admin/partners/{application.id}")
    assert second.status_code == 200
    assert "Partner login invite" not in second.text
    assert "Linked login email" in second.text


def test_admin_detail_shows_linked_user_and_referral_code(
    client: TestClient,
    db_session: Session,
) -> None:
    application = _submit_sign_and_get_application(client, db_session, "detail@example.com")
    _login_admin(client, db_session)
    client.post(f"/admin/partners/{application.id}/approve")

    response = client.get(f"/admin/partners/{application.id}")
    assert response.status_code == 200
    assert "detail@example.com" in response.text
    assert "Referral code" in response.text
    assert "ref=" in response.text
    assert "Invite status" in response.text


def test_admin_reject_marks_application_rejected(
    client: TestClient,
    db_session: Session,
) -> None:
    application = _submit_and_get_application(client, db_session, "reject@example.com")
    _login_admin(client, db_session)

    response = client.post(
        f"/admin/partners/{application.id}/reject",
        data={"rejection_reason": "Not a fit at this time."},
        follow_redirects=False,
    )
    assert response.status_code == 303

    db_session.expire_all()
    db_session.refresh(application)
    assert application.status == "rejected"
    assert application.rejection_reason == "Not a fit at this time."


def test_rejected_application_cannot_be_approved(
    client: TestClient,
    db_session: Session,
) -> None:
    application = _submit_and_get_application(client, db_session, "noreapprove@example.com")
    admin = _login_admin(client, db_session)
    client.post(
        f"/admin/partners/{application.id}/reject",
        data={"rejection_reason": "No"},
    )

    response = client.post(f"/admin/partners/{application.id}/approve")
    assert response.status_code == 400
    assert "Cannot approve a rejected application" in response.text

    partner = get_partner_by_application(db_session, application.id)
    assert partner is None


def test_partner_dashboard_requires_auth(client: TestClient) -> None:
    response = client.get("/partner/dashboard", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_non_partner_user_cannot_access_partner_dashboard(
    client: TestClient,
    db_session: Session,
) -> None:
    create_user(
        db_session,
        email="business@example.com",
        password="biz-secret",
        role="business_user",
    )
    db_session.commit()
    client.post(
        "/login",
        data={"email": "business@example.com", "password": "biz-secret"},
    )
    response = client.get("/partner/dashboard", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_partner_dashboard_after_approval_with_invite_acceptance(
    client: TestClient,
    db_session: Session,
) -> None:
    application = _submit_and_get_application(client, db_session, "dash@example.com")
    ensure_partner_application_docs_signed(db_session, application.id)
    db_session.commit()
    admin = _login_admin(client, db_session)

    result = approve_application(
        db_session,
        application.id,
        reviewed_by_user_id=admin.id,
    )
    db_session.commit()
    invite = (
        db_session.query(UserInviteToken)
        .filter(UserInviteToken.user_id == result.user.id, UserInviteToken.purpose == "partner_invite")
        .order_by(UserInviteToken.created_at.desc())
        .first()
    )
    assert invite is not None
    # Route-level invite acceptance behavior is validated in dedicated invite tests.
    from app.core.security import hash_password

    result.user.hashed_password = hash_password("dash-new-secret")
    db_session.commit()
    client.post("/login", data={"email": "dash@example.com", "password": "dash-new-secret"})
    response = client.get("/partner/dashboard")
    assert response.status_code == 200
    assert result.partner.referral_code in response.text
    assert "Partner dashboard" in response.text
    assert "Referred businesses" in response.text


def test_duplicate_approve_does_not_create_duplicate_partner_or_user(
    client: TestClient,
    db_session: Session,
) -> None:
    application = _submit_sign_and_get_application(client, db_session, "dup@example.com")
    _login_admin(client, db_session)

    client.post(f"/admin/partners/{application.id}/approve")
    client.post(f"/admin/partners/{application.id}/approve")

    partners = (
        db_session.query(Partner)
        .filter(Partner.application_id == application.id)
        .all()
    )
    assert len(partners) == 1

    users = db_session.query(User).filter(User.email == "dup@example.com").all()
    assert len(users) == 1

    first_code = partners[0].referral_code
    db_session.refresh(partners[0])
    assert partners[0].referral_code == first_code
    assert partners[0].user_id == users[0].id
