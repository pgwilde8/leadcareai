"""Partner marketing links and public referral landing (/r/{code})."""

from __future__ import annotations

from unittest.mock import MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.business_lead import BusinessLead
from app.models.partner_customer import PartnerCustomer
from app.services.referral_service import (
    REFERRAL_COOKIE_NAME,
    REFERRAL_CODE_SESSION_KEY,
    REFERRAL_PARTNER_ID_SESSION_KEY,
    resolve_referral_partner,
)
from app.services.user_service import create_user
from tests.test_referral_capture import _active_partner, _demo_form_data


def test_active_partner_can_view_marketing_page(
    client: TestClient,
    db_session: Session,
) -> None:
    code, email, password = _active_partner(client, db_session, "marketing@example.com")
    assert password
    client.post("/login", data={"email": email, "password": password})

    response = client.get("/partner/marketing")
    assert response.status_code == 200
    assert "Marketing links" in response.text
    assert code in response.text
    assert f"/demo?ref={code}" in response.text
    assert f"/r/{code}" in response.text
    assert f"/demo/book?ref={code}" in response.text
    assert "Compliance reminders" in response.text
    assert "guaranteed income" in response.text.lower()


def test_non_partner_cannot_access_marketing(
    client: TestClient,
    db_session: Session,
) -> None:
    create_user(
        db_session,
        email="biz-only@example.com",
        password="biz-secret",
        role="business_user",
    )
    db_session.commit()
    client.post("/login", data={"email": "biz-only@example.com", "password": "biz-secret"})

    response = client.get("/partner/marketing", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_referral_landing_stores_session_and_links_to_demo(
    client: TestClient,
    db_session: Session,
) -> None:
    code, _, _ = _active_partner(client, db_session, "rlanding@example.com")

    response = client.get(f"/r/{code}", follow_redirects=False)
    assert response.status_code == 200
    assert "Stop losing customers when you miss calls" in response.text
    assert f"/demo?ref={code}" in response.text
    assert f"/demo/book?ref={code}" in response.text

    assert client.cookies.get(REFERRAL_COOKIE_NAME) == code

    book = client.get("/demo/book")
    assert book.status_code == 200
    assert "Referred by partner" in book.text


def test_invalid_referral_landing_redirects_without_attribution(
    client: TestClient,
) -> None:
    response = client.get("/r/INVALIDCODE99", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/"

    book = client.get("/demo/book")
    assert book.status_code == 200
    assert "Referred by partner" not in book.text


def test_demo_submission_after_referral_landing_attributes_partner(
    client: TestClient,
    db_session: Session,
) -> None:
    code, _, _ = _active_partner(client, db_session, "rattrib@example.com")
    client.get(f"/r/{code}")

    post = client.post(
        "/demo/book",
        data=_demo_form_data(email="rlanding-lead@example.com"),
        follow_redirects=False,
    )
    assert post.status_code == 303

    lead = (
        db_session.query(BusinessLead)
        .filter(BusinessLead.email == "rlanding-lead@example.com")
        .one()
    )
    assert lead.partner_id is not None
    assert lead.referral_code == code

    attribution = (
        db_session.query(PartnerCustomer)
        .filter(PartnerCustomer.business_lead_id == lead.id)
        .one()
    )
    assert attribution.referral_code == code


def test_resolve_referral_partner_from_cookie_when_session_empty(
    client: TestClient,
    db_session: Session,
) -> None:
    code, _, _ = _active_partner(client, db_session, "cookie@example.com")
    from app.services.referral_service import get_active_partner_by_referral_code

    partner = get_active_partner_by_referral_code(db_session, code)
    assert partner is not None

    request = MagicMock()
    request.session = {}
    request.cookies = {REFERRAL_COOKIE_NAME: code}

    resolved = resolve_referral_partner(db_session, request)
    assert resolved is not None
    assert resolved.id == partner.id
    assert request.session[REFERRAL_CODE_SESSION_KEY] == code
    assert request.session[REFERRAL_PARTNER_ID_SESSION_KEY] == str(partner.id)


def test_referral_cookie_used_when_session_absent(
    client: TestClient,
    db_session: Session,
) -> None:
    from app.main import app

    code, _, _ = _active_partner(client, db_session, "cookieflow@example.com")

    cookie_client = TestClient(app)
    cookie_client.cookies.set(REFERRAL_COOKIE_NAME, code)

    book = cookie_client.get("/demo/book")
    assert book.status_code == 200
    assert "Referred by partner" in book.text

    post = cookie_client.post(
        "/demo/book",
        data=_demo_form_data(email="cookie-only@example.com"),
        follow_redirects=False,
    )
    assert post.status_code == 303

    lead = (
        db_session.query(BusinessLead)
        .filter(BusinessLead.email == "cookie-only@example.com")
        .one()
    )
    assert lead.referral_code == code
    assert lead.partner_id is not None
