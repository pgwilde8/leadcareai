"""Phase 1T: sales demo readiness checklist."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services import demo_service, lead_service
from app.services.business_service import create_business
from app.services.user_service import create_admin_user


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_readiness_checklist_all_false_when_demo_disabled(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEMO_ENABLED", "false")
    monkeypatch.setenv("DEMO_BUSINESS_ID", "")
    monkeypatch.setenv("DEMO_TWILIO_NUMBER", "")
    get_settings.cache_clear()

    items = demo_service.build_demo_readiness_checklist(db_session)
    by_key = {item.key: item for item in items}

    assert by_key["demo_enabled"].ok is False
    assert by_key["demo_business_id"].ok is False
    assert by_key["demo_twilio_number"].ok is False


def test_readiness_checklist_passes_when_fully_configured(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    business = create_business(db_session, name="Readiness Demo Co")
    business.notification_email = "staff@readiness.example"
    lead_service.create_lead(
        db_session,
        business.id,
        phone="+15550008888",
        source="missed_call",
        summary="Test lead",
    )
    db_session.commit()

    monkeypatch.setenv("DEMO_ENABLED", "true")
    monkeypatch.setenv("DEMO_BUSINESS_ID", str(business.id))
    monkeypatch.setenv("DEMO_TWILIO_NUMBER", "+18336691335")
    get_settings.cache_clear()

    items = demo_service.build_demo_readiness_checklist(db_session)
    assert all(item.ok for item in items)


def test_admin_demo_page_shows_readiness_and_sales_copy(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    business = create_business(db_session, name="Admin Readiness Co")
    business.notification_phone = "+15551112222"
    db_session.commit()
    monkeypatch.setenv("DEMO_ENABLED", "true")
    monkeypatch.setenv("DEMO_BUSINESS_ID", str(business.id))
    monkeypatch.setenv("DEMO_TWILIO_NUMBER", "+18336691335")
    get_settings.cache_clear()

    create_admin_user(db_session, email="readiness-admin@example.com", password="admin-secret")
    db_session.commit()
    client.post("/login", data={"email": "readiness-admin@example.com", "password": "admin-secret"})

    response = client.get("/admin/demo")
    assert response.status_code == 200
    assert "Sales demo readiness" in response.text
    assert "DEMO_ENABLED" in response.text
    assert "Staff notification configured" in response.text
    assert "Call this number and hang up" in response.text
    assert "Do I have to change my number?" in response.text
    assert "$100" in response.text
    assert "Call the demo number and hang up." in response.text


def test_partner_dashboard_includes_demo_script(
    client: TestClient,
    db_session: Session,
) -> None:
    from app.core.security import hash_password
    from app.models.partner_application import PartnerApplication
    from app.services.partner_document_service import seed_default_document_templates
    from app.services.partner_service import approve_application
    from tests.partner_fixtures import ensure_partner_application_docs_signed, partner_onboard_form_data

    seed_default_document_templates(db_session)
    db_session.commit()
    client.post(
        "/partner/onboard",
        data=partner_onboard_form_data(
            first_name="Demo",
            last_name="Partner",
            email="demo-script-partner@example.com",
            phone="+15550003333",
        ),
    )
    application = (
        db_session.query(PartnerApplication)
        .filter(PartnerApplication.email == "demo-script-partner@example.com")
        .one()
    )
    ensure_partner_application_docs_signed(db_session, application.id)
    db_session.commit()
    admin = create_admin_user(db_session, email="admin-for-script@example.com", password="admin-secret")
    db_session.commit()
    result = approve_application(db_session, application.id, reviewed_by_user_id=admin.id)
    result.user.hashed_password = hash_password("partner-demo-secret")
    db_session.commit()

    client.post("/login", data={"email": "demo-script-partner@example.com", "password": "partner-demo-secret"})
    response = client.get("/partner/dashboard")
    assert response.status_code == 200
    assert "Live demo script" in response.text
    assert "Call this number and hang up" in response.text
    assert "Do I have to change my number?" not in response.text
