"""Admin message routes (SQLite)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services.business_service import create_business
from app.services.lead_service import create_lead
from app.services.user_service import create_admin_user


def _login_admin(client: TestClient, db_session: Session) -> None:
    create_admin_user(db_session, email="admin@example.com", password="admin-secret")
    db_session.commit()
    client.post(
        "/login",
        data={"email": "admin@example.com", "password": "admin-secret"},
    )


def test_lead_detail_shows_message_history_section(
    client: TestClient,
    db_session: Session,
) -> None:
    _login_admin(client, db_session)
    business = create_business(db_session, name="Msg UI Co")
    lead = create_lead(db_session, business.id, name="UI Lead", phone="+15551112222")
    db_session.commit()

    response = client.get(f"/admin/leads/{lead.id}")
    assert response.status_code == 200
    assert "Message history" in response.text
    assert "Twilio SMS sync coming later" in response.text


def test_admin_can_add_internal_message(
    client: TestClient,
    db_session: Session,
) -> None:
    _login_admin(client, db_session)
    business = create_business(db_session, name="Add Msg Co")
    lead = create_lead(db_session, business.id, name="Lead", phone="+15553334444")
    db_session.commit()

    post = client.post(
        f"/admin/leads/{lead.id}/messages",
        data={
            "body": "Called customer back — left voicemail.",
            "direction": "internal",
            "channel": "note",
        },
        follow_redirects=False,
    )
    assert post.status_code == 303
    assert post.headers["location"] == f"/admin/leads/{lead.id}"

    detail = client.get(f"/admin/leads/{lead.id}")
    assert "Called customer back" in detail.text
    assert "internal" in detail.text


def test_messages_redirect_to_lead_detail(
    client: TestClient,
    db_session: Session,
) -> None:
    _login_admin(client, db_session)
    business = create_business(db_session, name="Redirect Co")
    lead = create_lead(db_session, business.id, name="L")
    db_session.commit()

    response = client.get(f"/admin/leads/{lead.id}/messages", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == f"/admin/leads/{lead.id}"


def test_unauthenticated_cannot_post_message(
    client: TestClient,
    db_session: Session,
) -> None:
    business = create_business(db_session, name="No Auth Co")
    lead = create_lead(db_session, business.id, name="L", phone="+1")
    db_session.commit()

    response = client.post(
        f"/admin/leads/{lead.id}/messages",
        data={"body": "Should not work", "direction": "internal", "channel": "manual"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/login"
