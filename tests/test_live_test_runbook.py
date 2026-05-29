"""Admin end-to-end launch test runbook (Phase 3J)."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services.user_service import create_admin_user, create_user
from app.services.business_service import create_business


def _login_admin(client: TestClient, db_session: Session) -> None:
    create_admin_user(db_session, email="admin-runbook@example.com", password="admin-secret")
    db_session.commit()
    client.post(
        "/login",
        data={"email": "admin-runbook@example.com", "password": "admin-secret"},
    )


SECRET_PATTERNS = (
    r"sk_live_[a-zA-Z0-9]{8,}",
    r"sk_test_[a-zA-Z0-9]{8,}",
    r"change-me",
    r"BEGIN PRIVATE KEY",
)


def test_admin_can_view_live_test_runbook(client: TestClient, db_session: Session) -> None:
    _login_admin(client, db_session)
    response = client.get("/admin/live-test-runbook")
    assert response.status_code == 200
    assert "End-to-end launch test runbook" in response.text


def test_non_admin_blocked_from_live_test_runbook(client: TestClient, db_session: Session) -> None:
    create_user(
        db_session,
        email="biz-runbook@example.com",
        password="biz-secret",
        role="business_user",
    )
    db_session.commit()
    client.post("/login", data={"email": "biz-runbook@example.com", "password": "biz-secret"})

    response = client.get("/admin/live-test-runbook", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_runbook_links_system_check_and_a2p(client: TestClient, db_session: Session) -> None:
    _login_admin(client, db_session)
    text = client.get("/admin/live-test-runbook").text
    assert "/admin/system-check" in text
    assert "/admin/a2p-packet" in text


def test_runbook_includes_required_sections(client: TestClient, db_session: Session) -> None:
    _login_admin(client, db_session)
    text = client.get("/admin/live-test-runbook").text
    assert "System prerequisites" in text
    assert "Test business setup" in text
    assert "Twilio" in text and "Backup Mode" in text
    assert "Live call" in text
    assert "Stripe" in text
    assert "Partner" in text and "commission" in text.lower()
    assert "notification" in text.lower()
    assert "I need help with a leak" in text
    assert "4242" in text


def test_runbook_no_secrets_exposed(client: TestClient, db_session: Session) -> None:
    _login_admin(client, db_session)
    text = client.get("/admin/live-test-runbook").text
    for pattern in SECRET_PATTERNS:
        assert re.search(pattern, text, re.IGNORECASE) is None, pattern


def test_runbook_with_business_shows_checks(client: TestClient, db_session: Session) -> None:
    business = create_business(db_session, name="E2E Test Plumbing Co")
    business.status = "active"
    db_session.commit()
    _login_admin(client, db_session)

    response = client.get(f"/admin/live-test-runbook?business_id={business.id}")
    assert response.status_code == 200
    assert "E2E Test Plumbing Co" in response.text
    assert f"/admin/businesses/{business.id}" in response.text
