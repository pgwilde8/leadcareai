"""Admin notification logs and system-check pages."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.notification_log import NotificationLog
from app.services.lead_service import create_lead
from app.services.business_service import create_business
from app.services.user_service import create_admin_user


def _login_admin(client: TestClient, db_session: Session) -> None:
    create_admin_user(db_session, email="admin@example.com", password="admin-secret")
    db_session.commit()
    client.post("/login", data={"email": "admin@example.com", "password": "admin-secret"})


def test_admin_can_view_notification_logs(client: TestClient, db_session: Session) -> None:
    business = create_business(db_session, name="Notify Log Co")
    lead = create_lead(
        db_session,
        business.id,
        phone="+15550009999",
        source="missed_call",
        summary="Lead for logs",
    )
    log = NotificationLog(
        business_id=business.id,
        lead_id=lead.id,
        channel="sms",
        recipient="+15556667777",
        event_type="missed_call",
        status="failed",
        error_message="Twilio send failed due to test",
        provider_sid="SM_TEST_LOG_1",
    )
    db_session.add(log)
    db_session.commit()

    _login_admin(client, db_session)
    response = client.get("/admin/notification-logs")
    assert response.status_code == 200
    assert "Notification Logs" in response.text
    assert "Notify Log Co" in response.text
    assert "missed_call" in response.text
    assert "SM_TEST_LOG_1" in response.text


def test_non_admin_cannot_view_notification_logs(client: TestClient) -> None:
    response = client.get("/admin/notification-logs", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_notification_log_recipient_is_masked(client: TestClient, db_session: Session) -> None:
    business = create_business(db_session, name="Mask Co")
    lead = create_lead(
        db_session,
        business.id,
        phone="+15551234567",
        source="sms",
        summary="Mask test",
    )
    db_session.add(
        NotificationLog(
            business_id=business.id,
            lead_id=lead.id,
            channel="email",
            recipient="alerts@example.com",
            event_type="inbound_sms",
            status="sent",
        )
    )
    db_session.commit()

    _login_admin(client, db_session)
    response = client.get("/admin/notification-logs")
    assert response.status_code == 200
    assert "a***@example.com" in response.text
    assert "alerts@example.com" not in response.text


def test_system_check_page_loads_and_hides_secrets(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret-never-show")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "twilio-secret-never-show")
    get_settings.cache_clear()

    _login_admin(client, db_session)
    response = client.get("/admin/system-check")
    assert response.status_code == 200
    assert "System Check" in response.text
    assert "OPENAI_API_KEY configured" in response.text
    assert "TWILIO_AUTH_TOKEN configured" in response.text
    assert "sk-secret-never-show" not in response.text
    assert "twilio-secret-never-show" not in response.text
    get_settings.cache_clear()


def test_system_check_configured_and_missing_values(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PUBLIC_BASE_URL", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("OPENAI_ENABLED", "false")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_present")
    get_settings.cache_clear()

    _login_admin(client, db_session)
    response = client.get("/admin/system-check")
    assert response.status_code == 200
    assert "PUBLIC_BASE_URL configured" in response.text
    assert "OPENAI_API_KEY configured" in response.text
    assert "STRIPE_SECRET_KEY configured" in response.text
    assert "OPENAI_ENABLED" in response.text
    assert "<td>no</td>" in response.text
    assert "<td>false</td>" in response.text
    assert "<td>yes</td>" in response.text
    get_settings.cache_clear()
