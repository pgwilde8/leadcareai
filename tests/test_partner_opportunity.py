"""Public partner opportunity page and polished application flow."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.partner_application import PartnerApplication
from app.models.partner_signed_document import PartnerSignedDocument
from app.models.partner_tax_info import PartnerTaxInfo
from app.services.user_service import create_admin_user
from tests.partner_fixtures import partner_onboard_form_data


def _login_admin(client: TestClient, db_session: Session) -> None:
    create_admin_user(db_session, email="admin@example.com", password="admin-secret")
    db_session.commit()
    client.post(
        "/login",
        data={"email": "admin@example.com", "password": "admin-secret"},
    )


def test_partners_opportunity_page_returns_200(client: TestClient) -> None:
    response = client.get("/partners")
    assert response.status_code == 200
    text = response.text
    assert "Build recurring commissions" in text
    assert "$100" in text
    assert "$25/month" in text
    assert "6 paid months" in text or "6 months" in text
    assert "recruiting alone" in text
    assert "fake accounts" in text
    assert "guaranteed income" in text.lower()
    assert 'href="/partner/onboard"' in text
    assert "Apply to become a Sales Partner" in text
    assert "Good fit" in text
    assert "Not a good fit" in text


def test_partner_onboard_has_no_tax_or_signature_fields(client: TestClient) -> None:
    response = client.get("/partner/onboard")
    assert response.status_code == 200
    text = response.text.lower()
    assert 'name="tax_' not in text
    assert 'name="signature_text"' not in text
    assert 'name="electronic_consent"' not in text
    assert 'type="file"' not in text
    assert 'name="ic_understanding"' in text
    assert "commission-based" in text
    assert 'name="full_name"' in text
    assert "collected later" in text


def test_partner_onboard_requires_ic_understanding_checkbox(
    client: TestClient,
    db_session: Session,
) -> None:
    data = partner_onboard_form_data(email="no-check@example.com")
    data.pop("ic_understanding")
    response = client.post("/partner/onboard", data=data)
    assert response.status_code == 400
    assert "commission-based" in response.text.lower()
    assert (
        db_session.query(PartnerApplication)
        .filter(PartnerApplication.email == "no-check@example.com")
        .count()
        == 0
    )


def test_post_partner_onboard_creates_admin_review_application(
    client: TestClient,
    db_session: Session,
) -> None:
    response = client.post(
        "/partner/onboard",
        data=partner_onboard_form_data(email="apply@example.com"),
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/partner/onboard/success"

    application = (
        db_session.query(PartnerApplication)
        .filter(PartnerApplication.email == "apply@example.com")
        .one()
    )
    assert application.status == "admin_review"
    assert application.first_name == "Pat"
    assert application.city == "Austin"
    assert application.state == "TX"
    assert "HVAC" in (application.company_name or "")

    assert (
        db_session.query(PartnerSignedDocument)
        .filter(PartnerSignedDocument.application_id == application.id)
        .count()
        == 0
    )
    assert (
        db_session.query(PartnerTaxInfo)
        .filter(PartnerTaxInfo.application_id == application.id)
        .count()
        == 0
    )


def test_admin_application_detail_labels_target_industries_not_company(
    client: TestClient,
    db_session: Session,
) -> None:
    client.post(
        "/partner/onboard",
        data=partner_onboard_form_data(email="admin-label@example.com"),
        follow_redirects=False,
    )
    application = (
        db_session.query(PartnerApplication)
        .filter(PartnerApplication.email == "admin-label@example.com")
        .one()
    )
    _login_admin(client, db_session)

    detail = client.get(f"/admin/partners/{application.id}")
    assert detail.status_code == 200
    assert "Target industries / businesses to contact" in detail.text
    assert "HVAC" in detail.text
    assert "<th>Company</th>" not in detail.text


def test_partner_onboard_success_does_not_imply_docs_signed(client: TestClient) -> None:
    response = client.get("/partner/onboard/success")
    assert response.status_code == 200
    assert "screening call" in response.text
    assert "document-signing link" in response.text
    assert "have not signed" in response.text.lower() or "not signed" in response.text.lower()
