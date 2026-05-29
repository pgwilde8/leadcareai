"""Mobile-first call forwarding onboarding (V1)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services import call_forwarding_service
from app.services.business_service import create_business, link_user_to_business
from app.services.phone_number_service import create_phone_number
from app.services.user_service import create_admin_user, create_user

SETTINGS_URL = "/business/settings"
CALL_FORWARDING_URL = "/business/call-forwarding"
DASHBOARD_URL = "/business/dashboard"
BANNER_SNIPPET = call_forwarding_service.INCOMPLETE_BANNER_MESSAGE


def _create_business_user(
    db_session: Session,
    *,
    email: str,
    password: str,
    business_name: str,
):
    business = create_business(db_session, name=business_name)
    user = create_user(
        db_session,
        email=email,
        password=password,
        role="business_user",
    )
    link_user_to_business(db_session, user.id, business.id)
    db_session.commit()
    return user, business


def _login(client: TestClient, email: str, password: str) -> None:
    client.post("/login", data={"email": email, "password": password})


def _login_admin(client: TestClient, db_session: Session) -> None:
    create_admin_user(db_session, email="admin@example.com", password="admin-secret")
    db_session.commit()
    client.post(
        "/login",
        data={"email": "admin@example.com", "password": "admin-secret"},
    )


def test_business_settings_saves_carrier_and_mobile(
    client: TestClient,
    db_session: Session,
) -> None:
    _user, _business = _create_business_user(
        db_session,
        email="cf-settings@example.com",
        password="cf-secret",
        business_name="CF Settings Co",
    )
    _login(client, "cf-settings@example.com", "cf-secret")

    response = client.post(
        SETTINGS_URL,
        data={
            "name": "CF Settings Co",
            "industry": "HVAC",
            "website_url": "",
            "contact_email": "owner@example.com",
            "contact_phone": "+15551112222",
            "notification_email": "",
            "notification_phone": "",
            "missed_call_textback_message": "",
            "sms_signature": "",
            "lead_intake_prompt": "",
            "customer_phone_is_mobile": "yes",
            "customer_phone_carrier": "verizon",
            "can_access_phone_during_onboarding": "yes",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    page = client.get(f"{SETTINGS_URL}?saved=1")
    assert page.status_code == 200
    assert "Verizon" in page.text or "verizon" in page.text.lower()

    db_session.expire_all()
    from app.models.business import Business

    business = db_session.query(Business).filter_by(name="CF Settings Co").one()
    assert business.customer_phone_is_mobile is True
    assert business.customer_phone_carrier == "verizon"


def test_call_forwarding_page_shows_assigned_leadcare_number(
    client: TestClient,
    db_session: Session,
) -> None:
    _user, business = _create_business_user(
        db_session,
        email="cf-page@example.com",
        password="cf-page-secret",
        business_name="CF Page Co",
    )
    create_phone_number(
        db_session,
        business.id,
        "+15559876543",
        provider="twilio",
        status="active",
    )
    business.customer_phone_carrier = "t_mobile"
    business.customer_phone_is_mobile = True
    db_session.commit()

    _login(client, "cf-page@example.com", "cf-page-secret")
    response = client.get(CALL_FORWARDING_URL)
    assert response.status_code == 200
    assert "+15559876543" in response.text
    assert "Backup Mode" in response.text


def test_dashboard_banner_mentions_call_forwarding_test(
    client: TestClient,
    db_session: Session,
) -> None:
    _user, business = _create_business_user(
        db_session,
        email="cf-banner2@example.com",
        password="cf-banner2-secret",
        business_name="CF Banner 2 Co",
    )
    business.customer_phone_forwarding_status = "instructions_sent"
    db_session.commit()

    _login(client, "cf-banner2@example.com", "cf-banner2-secret")
    response = client.get(DASHBOARD_URL)
    assert "call-forwarding test" in response.text


def test_dashboard_shows_incomplete_banner_when_not_test_passed(
    client: TestClient,
    db_session: Session,
) -> None:
    _user, business = _create_business_user(
        db_session,
        email="cf-banner@example.com",
        password="cf-banner-secret",
        business_name="CF Banner Co",
    )
    business.customer_phone_forwarding_status = "instructions_sent"
    db_session.commit()

    _login(client, "cf-banner@example.com", "cf-banner-secret")
    response = client.get(DASHBOARD_URL)
    assert response.status_code == 200
    assert BANNER_SNIPPET in response.text


def test_dashboard_hides_banner_when_test_passed(
    client: TestClient,
    db_session: Session,
) -> None:
    _user, business = _create_business_user(
        db_session,
        email="cf-done@example.com",
        password="cf-done-secret",
        business_name="CF Done Co",
    )
    business.customer_phone_forwarding_status = "test_passed"
    db_session.commit()

    _login(client, "cf-done@example.com", "cf-done-secret")
    response = client.get(DASHBOARD_URL)
    assert response.status_code == 200
    assert BANNER_SNIPPET not in response.text


def test_admin_can_update_forwarding_status(
    client: TestClient,
    db_session: Session,
) -> None:
    business = create_business(db_session, name="Admin CF Co")
    business.customer_phone_carrier = "att"
    business.customer_phone_is_mobile = True
    db_session.commit()

    _login_admin(client, db_session)
    detail = client.get(f"/admin/businesses/{business.id}")
    assert detail.status_code == 200
    assert "Call forwarding (mobile V1)" in detail.text

    response = client.post(
        f"/admin/businesses/{business.id}/call-forwarding",
        data={"status": "test_passed", "notes": "Live test OK"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    db_session.expire_all()
    db_session.refresh(business)
    assert business.customer_phone_forwarding_status == "test_passed"
    assert business.customer_phone_forwarding_notes == "Live test OK"
    assert business.call_forwarding_tested_at is not None


def test_non_business_user_cannot_access_call_forwarding_page(
    client: TestClient,
    db_session: Session,
) -> None:
    _login_admin(client, db_session)
    response = client.get(CALL_FORWARDING_URL, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_business_only_sees_own_assigned_number(
    client: TestClient,
    db_session: Session,
) -> None:
    _user_a, business_a = _create_business_user(
        db_session,
        email="cf-a@example.com",
        password="cf-a-secret",
        business_name="Business A CF",
    )
    _user_b, business_b = _create_business_user(
        db_session,
        email="cf-b@example.com",
        password="cf-b-secret",
        business_name="Business B CF",
    )
    create_phone_number(
        db_session,
        business_a.id,
        "+15551111111",
        provider="twilio",
        status="active",
    )
    create_phone_number(
        db_session,
        business_b.id,
        "+15552222222",
        provider="twilio",
        status="active",
    )
    db_session.commit()

    _login(client, "cf-a@example.com", "cf-a-secret")
    response = client.get(CALL_FORWARDING_URL)
    assert response.status_code == 200
    assert "+15551111111" in response.text
    assert "+15552222222" not in response.text


def test_demo_book_requires_call_forwarding_terms_checkbox(
    client: TestClient,
    db_session: Session,
) -> None:
    from tests.test_referral_capture import _demo_form_data

    data = _demo_form_data()
    del data["call_forwarding_terms_acknowledged"]

    response = client.post("/demo/book", data=data, follow_redirects=False)
    assert response.status_code == 400
    assert "mobile call-forwarding" in response.text.lower()
