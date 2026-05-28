"""Admin lead and phone number routes (SQLite)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services.business_service import create_business
from app.services.user_service import create_admin_user


def _login_admin(client: TestClient, db_session: Session) -> None:
    create_admin_user(db_session, email="admin@example.com", password="admin-secret")
    db_session.commit()
    client.post(
        "/login",
        data={"email": "admin@example.com", "password": "admin-secret"},
    )


def test_business_detail_shows_phone_and_lead_sections(
    client: TestClient,
    db_session: Session,
) -> None:
    _login_admin(client, db_session)
    business = create_business(db_session, name="Sections Co")
    db_session.commit()

    response = client.get(f"/admin/businesses/{business.id}")
    assert response.status_code == 200
    assert "Phone numbers" in response.text
    assert "Leads" in response.text
    assert "Active numbers receive inbound SMS" in response.text


def test_admin_can_open_new_phone_number_form(
    client: TestClient,
    db_session: Session,
) -> None:
    _login_admin(client, db_session)
    business = create_business(db_session, name="Phone Form Co")
    db_session.commit()

    response = client.get(f"/admin/businesses/{business.id}/phone-numbers/new")
    assert response.status_code == 200
    assert "Add phone number" in response.text


def test_admin_can_create_phone_number_on_business_detail(
    client: TestClient,
    db_session: Session,
) -> None:
    _login_admin(client, db_session)
    business = create_business(db_session, name="Phone Create Co")
    db_session.commit()

    post = client.post(
        f"/admin/businesses/{business.id}/phone-numbers",
        data={
            "phone_number": "+15551230000",
            "label": "Main line",
            "forward_to_number": "+15559876543",
            "provider": "twilio",
            "provider_sid": "",
            "status": "active",
        },
        follow_redirects=False,
    )
    assert post.status_code == 303

    detail = client.get(f"/admin/businesses/{business.id}")
    assert "+15551230000" in detail.text
    assert "Main line" in detail.text
    assert "twilio" in detail.text


def test_admin_can_update_phone_number_status(
    client: TestClient,
    db_session: Session,
) -> None:
    _login_admin(client, db_session)
    business = create_business(db_session, name="Phone Status Co")
    from app.services.phone_number_service import create_phone_number

    record = create_phone_number(
        db_session,
        business.id,
        "+15551239999",
        status="pending",
    )
    db_session.commit()

    response = client.post(
        f"/admin/phone-numbers/{record.id}/status",
        data={"status": "active"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    detail = client.get(f"/admin/businesses/{business.id}")
    assert "active" in detail.text


def test_admin_can_open_leads_list(
    client: TestClient,
    db_session: Session,
) -> None:
    _login_admin(client, db_session)
    business = create_business(db_session, name="Leads List Co")
    db_session.commit()

    response = client.get(f"/admin/businesses/{business.id}/leads")
    assert response.status_code == 200
    assert "Leads" in response.text


def test_admin_can_create_lead_and_view_detail(
    client: TestClient,
    db_session: Session,
) -> None:
    _login_admin(client, db_session)
    business = create_business(db_session, name="Lead Create Co")
    db_session.commit()

    post = client.post(
        f"/admin/businesses/{business.id}/leads",
        data={
            "name": "John Smith",
            "phone": "+15554443333",
            "email": "john@example.com",
            "service_needed": "Emergency roof leak",
            "location": "Toms River",
            "urgency": "Today",
            "summary": "Active leak in kitchen",
        },
        follow_redirects=False,
    )
    assert post.status_code == 303
    assert post.headers["location"].startswith("/admin/leads/")

    detail = client.get(post.headers["location"])
    assert detail.status_code == 200
    assert "John Smith" in detail.text
    assert "+15554443333" in detail.text
    assert "Emergency roof leak" in detail.text


def test_admin_can_update_lead_status(
    client: TestClient,
    db_session: Session,
) -> None:
    _login_admin(client, db_session)
    business = create_business(db_session, name="Status Update Co")
    db_session.commit()

    create = client.post(
        f"/admin/businesses/{business.id}/leads",
        data={"name": "Status Lead", "phone": "+15550000099"},
        follow_redirects=False,
    )
    lead_url = create.headers["location"]

    update = client.post(
        f"{lead_url}/status",
        data={"status": "contacted"},
        follow_redirects=False,
    )
    assert update.status_code == 303

    detail = client.get(lead_url)
    assert "contacted" in detail.text
