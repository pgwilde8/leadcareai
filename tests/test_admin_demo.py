"""Admin demo control panel tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services import lead_service, message_service
from app.services.business_service import create_business
from app.services.user_service import create_admin_user


def _login_admin(client: TestClient, db_session: Session) -> None:
    create_admin_user(db_session, email="admin@example.com", password="admin-secret")
    db_session.commit()
    client.post("/login", data={"email": "admin@example.com", "password": "admin-secret"})


@pytest.fixture
def _demo_env(monkeypatch: pytest.MonkeyPatch, db_session: Session):
    demo = create_business(db_session, name="LeadCare AI Demo")
    db_session.commit()
    monkeypatch.setenv("DEMO_ENABLED", "true")
    monkeypatch.setenv("DEMO_BUSINESS_ID", str(demo.id))
    monkeypatch.setenv("DEMO_TWILIO_NUMBER", "+18336691335")
    get_settings.cache_clear()
    yield demo
    get_settings.cache_clear()


def test_admin_demo_requires_admin(client: TestClient, _demo_env) -> None:
    response = client.get("/admin/demo", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_admin_demo_shows_instructions_and_recent_lead(
    client: TestClient,
    db_session: Session,
    _demo_env,
) -> None:
    lead = lead_service.create_lead(
        db_session,
        _demo_env.id,
        phone="+15550001111",
        source="missed_call",
        summary="Water pump failed",
        service_needed="water pump repair",
        location="Brick, NJ",
        urgency="urgent",
    )
    lead.ai_temperature = "hot"
    lead.ai_confidence = 0.9
    message_service.create_message(
        db_session,
        _demo_env.id,
        lead.id,
        body="Water pump broke, no water",
        direction="inbound",
        channel="sms",
        status="received",
    )
    db_session.commit()

    _login_admin(client, db_session)
    response = client.get("/admin/demo")
    assert response.status_code == 200
    assert "Call the demo number and hang up." in response.text
    assert "Reply to the text like a customer." in response.text
    assert "Watch the lead appear below." in response.text
    assert "HOT" in response.text
    assert "URGENT" in response.text
    assert "Call immediately" in response.text
    assert "****" in response.text
    assert "+15550001111" not in response.text


def test_admin_demo_clear_only_affects_demo_business(
    client: TestClient,
    db_session: Session,
    _demo_env,
) -> None:
    other = create_business(db_session, name="Real Customer Co")
    demo_lead = lead_service.create_lead(
        db_session,
        _demo_env.id,
        phone="+15550002222",
        source="missed_call",
        summary="Demo lead",
    )
    other_lead = lead_service.create_lead(
        db_session,
        other.id,
        phone="+15559990000",
        source="sms",
        summary="Real lead",
    )
    message_service.create_message(
        db_session,
        _demo_env.id,
        demo_lead.id,
        body="demo msg",
        direction="inbound",
        channel="sms",
        status="received",
    )
    message_service.create_message(
        db_session,
        other.id,
        other_lead.id,
        body="real msg",
        direction="inbound",
        channel="sms",
        status="received",
    )
    db_session.commit()

    _login_admin(client, db_session)
    response = client.post("/admin/demo/clear", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/admin/demo?cleared=")

    db_session.expire_all()
    demo_remaining = lead_service.list_leads_for_business(db_session, _demo_env.id)
    other_remaining = lead_service.list_leads_for_business(db_session, other.id)
    assert demo_remaining == []
    assert len(other_remaining) == 1
    assert other_remaining[0].id == other_lead.id
