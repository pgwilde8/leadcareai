"""Admin business management routes (SQLite)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services.business_service import create_business
from app.services.user_service import create_admin_user, create_user


def _login_admin(client: TestClient, db_session: Session) -> None:
    create_admin_user(db_session, email="admin@example.com", password="admin-secret")
    db_session.commit()
    client.post(
        "/login",
        data={"email": "admin@example.com", "password": "admin-secret"},
    )


def test_businesses_list_requires_admin(client: TestClient) -> None:
    response = client.get("/admin/businesses", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_admin_can_view_business_list(
    client: TestClient,
    db_session: Session,
) -> None:
    _login_admin(client, db_session)
    create_business(db_session, name="Test Roofing")
    db_session.commit()

    response = client.get("/admin/businesses")
    assert response.status_code == 200
    assert "Test Roofing" in response.text


def test_admin_can_open_new_business_form(
    client: TestClient,
    db_session: Session,
) -> None:
    _login_admin(client, db_session)
    response = client.get("/admin/businesses/new")
    assert response.status_code == 200
    assert "New business" in response.text


def test_admin_can_create_business_and_view_detail(
    client: TestClient,
    db_session: Session,
) -> None:
    _login_admin(client, db_session)

    response = client.post(
        "/admin/businesses",
        data={
            "name": "New HVAC Co",
            "industry": "HVAC",
            "website_url": "",
            "main_phone": "",
            "timezone": "America/New_York",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "/admin/businesses/" in response.headers["location"]

    detail = client.get(response.headers["location"])
    assert detail.status_code == 200
    assert "New HVAC Co" in detail.text
    assert "Missed-call text-back" in detail.text


def test_business_detail_shows_business_name(
    client: TestClient,
    db_session: Session,
) -> None:
    _login_admin(client, db_session)
    business = create_business(db_session, name="Detail Plumbing")
    db_session.commit()

    response = client.get(f"/admin/businesses/{business.id}")
    assert response.status_code == 200
    assert "Detail Plumbing" in response.text


def test_admin_can_link_existing_user_to_business(
    client: TestClient,
    db_session: Session,
) -> None:
    _login_admin(client, db_session)
    business = create_business(db_session, name="Link Test Co")
    create_user(db_session, email="staff@example.com", password="secret")
    db_session.commit()

    response = client.post(
        f"/admin/businesses/{business.id}/users",
        data={"email": "staff@example.com", "role": "staff"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    detail = client.get(f"/admin/businesses/{business.id}")
    assert "staff@example.com" in detail.text
    assert "staff" in detail.text
