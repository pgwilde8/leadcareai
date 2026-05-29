"""Referral capture and business lead intake (Phase 2C)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.business_lead import BusinessLead
from app.models.partner_application import PartnerApplication
from app.models.partner_customer import PartnerCustomer
from app.core.security import hash_password
from app.services.partner_document_service import seed_default_document_templates
from app.services.partner_service import approve_application
from app.services.user_service import create_admin_user
from tests.partner_fixtures import ensure_partner_application_docs_signed, partner_onboard_form_data


def _login_admin(client: TestClient, db_session: Session) -> None:
    create_admin_user(db_session, email="admin@example.com", password="admin-secret")
    db_session.commit()
    client.post(
        "/login",
        data={"email": "admin@example.com", "password": "admin-secret"},
    )


def _active_partner(
    client: TestClient,
    db_session: Session,
    partner_email: str,
) -> tuple[str, str, str | None]:
    """Return (referral_code, partner_email, login_password)."""
    seed_default_document_templates(db_session)
    db_session.commit()
    client.post(
        "/partner/onboard",
        data=partner_onboard_form_data(
            first_name="Ref",
            last_name="Partner",
            email=partner_email,
            phone="+15559990001",
            city="Dallas",
            state="TX",
        ),
    )
    application = (
        db_session.query(PartnerApplication)
        .filter(PartnerApplication.email == partner_email)
        .one()
    )
    ensure_partner_application_docs_signed(db_session, application.id)
    db_session.commit()
    admin = create_admin_user(
        db_session,
        email=f"admin-for-{partner_email}",
        password="admin-secret",
    )
    db_session.commit()
    result = approve_application(db_session, application.id, reviewed_by_user_id=admin.id)
    result.user.hashed_password = hash_password("partner-ref-secret")
    db_session.commit()
    return result.partner.referral_code, partner_email, "partner-ref-secret"


def _demo_form_data(**overrides: str) -> dict[str, str]:
    data = {
        "business_name": "Acme HVAC",
        "contact_name": "Jane Owner",
        "email": "jane@acmehvac.example",
        "phone": "+15551234000",
        "industry": "HVAC",
        "city": "Austin",
        "state": "TX",
        "notes": "We miss a lot of after-hours calls.",
        "call_forwarding_terms_acknowledged": "on",
    }
    data.update(overrides)
    return data


def test_valid_ref_stores_referral_in_session(client: TestClient, db_session: Session) -> None:
    code, _, _ = _active_partner(client, db_session, "partner-ref@example.com")
    client.get(f"/?ref={code}")
    response = client.get("/demo/book")
    assert response.status_code == 200
    assert "Referred by partner" in response.text
    assert "Ref Partner" in response.text


def test_invalid_ref_does_not_crash_or_store_partner(client: TestClient) -> None:
    response = client.get("/?ref=INVALIDCODE99")
    assert response.status_code == 200
    follow = client.get("/demo")
    assert follow.status_code == 200
    assert "Referred by partner" not in follow.text


def test_get_demo_returns_200(client: TestClient) -> None:
    response = client.get("/demo")
    assert response.status_code == 200
    assert "missed-call demo" in response.text


def test_post_demo_creates_business_lead(client: TestClient, db_session: Session) -> None:
    response = client.post("/demo/book", data=_demo_form_data(), follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/demo/book/success"

    lead = (
        db_session.query(BusinessLead)
        .filter(BusinessLead.email == "jane@acmehvac.example")
        .one()
    )
    assert lead.business_name == "Acme HVAC"
    assert lead.status == "new"
    assert lead.partner_id is None


def test_post_demo_with_referral_creates_partner_customer(
    client: TestClient,
    db_session: Session,
) -> None:
    code, _, _ = _active_partner(client, db_session, "partner-attrib@example.com")
    client.get(f"/?ref={code}")
    response = client.post(
        "/demo/book",
        data=_demo_form_data(email="referred@biz.example"),
        follow_redirects=False,
    )
    assert response.status_code == 303

    lead = (
        db_session.query(BusinessLead)
        .filter(BusinessLead.email == "referred@biz.example")
        .one()
    )
    assert lead.referral_code == code
    assert lead.partner_id is not None

    attribution = (
        db_session.query(PartnerCustomer)
        .filter(PartnerCustomer.business_lead_id == lead.id)
        .one()
    )
    assert attribution.referral_code == code
    assert attribution.status == "referred"


def test_admin_can_see_referred_business_lead(
    client: TestClient,
    db_session: Session,
) -> None:
    code, _, _ = _active_partner(client, db_session, "partner-admin@example.com")
    client.get(f"/?ref={code}")
    client.post("/demo/book", data=_demo_form_data(email="adminview@biz.example"))
    _login_admin(client, db_session)

    response = client.get("/admin/business-leads")
    assert response.status_code == 200
    assert "adminview@biz.example" in response.text
    assert code in response.text


def test_partner_dashboard_shows_referred_business_lead(
    client: TestClient,
    db_session: Session,
) -> None:
    partner_email = "partner-dash-ref@example.com"
    code, email, password = _active_partner(client, db_session, partner_email)
    assert password

    client.get(f"/?ref={code}")
    client.post(
        "/demo/book",
        data=_demo_form_data(
            email="dashref@biz.example",
            business_name="Dash Ref Plumbing",
        ),
    )

    client.post("/login", data={"email": email, "password": password})
    response = client.get("/partner/dashboard")
    assert response.status_code == 200
    assert "Dash Ref Plumbing" in response.text
    assert code in response.text
    assert "Referred businesses" in response.text


def test_duplicate_demo_submission_does_not_duplicate_partner_customer(
    client: TestClient,
    db_session: Session,
) -> None:
    code, _, _ = _active_partner(client, db_session, "partner-dup@example.com")
    client.get(f"/?ref={code}")
    data = _demo_form_data(email="dup@biz.example")
    client.post("/demo/book", data=data)
    client.get(f"/?ref={code}")
    client.post("/demo/book", data=data)

    leads = (
        db_session.query(BusinessLead)
        .filter(BusinessLead.email == "dup@biz.example")
        .all()
    )
    assert len(leads) == 1

    attributions = (
        db_session.query(PartnerCustomer)
        .filter(PartnerCustomer.business_lead_id == leads[0].id)
        .all()
    )
    assert len(attributions) == 1
