"""Admin A2P 10DLC registration packet (Phase 3H)."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services import a2p_packet_service
from app.services.user_service import create_admin_user, create_user
from app.services.business_service import create_business, link_user_to_business


def _login_admin(client: TestClient, db_session: Session) -> None:
    create_admin_user(db_session, email="admin-a2p@example.com", password="admin-secret")
    db_session.commit()
    client.post(
        "/login",
        data={"email": "admin-a2p@example.com", "password": "admin-secret"},
    )


SECRET_PATTERNS = (
    r"TWILIO_AUTH_TOKEN",
    r"sk_live_",
    r"sk_test_",
    r"SECRET_KEY",
    r"SMTP_PASSWORD",
    r"BEGIN PRIVATE KEY",
)


def test_admin_can_view_a2p_packet_page(client: TestClient, db_session: Session) -> None:
    _login_admin(client, db_session)
    response = client.get("/admin/a2p-packet")
    assert response.status_code == 200
    assert "A2P 10DLC registration packet" in response.text
    assert "LeadCareAI missed-call recovery" in response.text
    assert "third-party marketing" in response.text


def test_non_admin_blocked_from_a2p_packet(client: TestClient, db_session: Session) -> None:
    business = create_business(db_session, name="A2P Block Co")
    user = create_user(
        db_session,
        email="biz-a2p@example.com",
        password="biz-secret",
        role="business_user",
    )
    link_user_to_business(db_session, user.id, business.id)
    db_session.commit()
    client.post("/login", data={"email": "biz-a2p@example.com", "password": "biz-secret"})

    response = client.get("/admin/a2p-packet", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_a2p_packet_includes_required_compliance_content(client: TestClient, db_session: Session) -> None:
    _login_admin(client, db_session)
    text = client.get("/admin/a2p-packet").text

    assert "STOP" in text
    assert "HELP" in text
    assert "https://leadcareai.com/privacy" in text or "/privacy" in text
    assert "https://leadcareai.com/terms" in text or "/terms" in text
    assert "sms-terms" in text
    assert "not sold" in text.lower()
    assert "third parties" in text.lower()
    assert "marketing" in text.lower() or "promotional" in text.lower()
    assert "missed-call" in text.lower() or "missed call" in text.lower()


def test_a2p_packet_contains_no_secrets(client: TestClient, db_session: Session) -> None:
    _login_admin(client, db_session)
    text = client.get("/admin/a2p-packet").text
    for pattern in SECRET_PATTERNS:
        assert re.search(pattern, text, re.IGNORECASE) is None, pattern


def test_a2p_packet_service_builds_production_urls() -> None:
    packet = a2p_packet_service.build_a2p_packet()
    assert packet.privacy_url == "https://leadcareai.com/privacy"
    assert packet.terms_url == "https://leadcareai.com/terms"
    assert packet.sms_terms_url == "https://leadcareai.com/sms-terms"
    assert len(packet.sample_messages) == 5
