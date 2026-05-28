"""Session auth and admin access tests (SQLite, no Postgres)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services.user_service import create_admin_user


def test_login_page_returns_200(client: TestClient) -> None:
    response = client.get("/login")
    assert response.status_code == 200
    assert "Log in" in response.text
    assert "Business login" in response.text


def test_login_wrong_credentials_shows_generic_error(
    client: TestClient,
    db_session: Session,
) -> None:
    create_admin_user(db_session, email="admin@example.com", password="correct-password")
    db_session.commit()

    response = client.post(
        "/login",
        data={"email": "admin@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert "Invalid email or password" in response.text


def test_login_valid_admin_redirects_to_admin(
    client: TestClient,
    db_session: Session,
) -> None:
    create_admin_user(db_session, email="admin@example.com", password="admin-secret")
    db_session.commit()

    response = client.post(
        "/login",
        data={"email": "admin@example.com", "password": "admin-secret"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/admin"


def test_admin_requires_login(client: TestClient) -> None:
    response = client.get("/admin", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_admin_after_login_returns_dashboard(
    client: TestClient,
    db_session: Session,
) -> None:
    create_admin_user(db_session, email="admin@example.com", password="admin-secret")
    db_session.commit()

    client.post(
        "/login",
        data={"email": "admin@example.com", "password": "admin-secret"},
    )

    response = client.get("/admin")
    assert response.status_code == 200
    assert "LeadCare AI Admin" in response.text
    assert "admin@example.com" in response.text


def test_logout_clears_session_and_protects_admin(
    client: TestClient,
    db_session: Session,
) -> None:
    create_admin_user(db_session, email="admin@example.com", password="admin-secret")
    db_session.commit()

    client.post(
        "/login",
        data={"email": "admin@example.com", "password": "admin-secret"},
    )
    logout = client.post("/logout", follow_redirects=False)
    assert logout.status_code == 303
    assert logout.headers["location"] == "/login"

    protected = client.get("/admin", follow_redirects=False)
    assert protected.status_code == 303
    assert protected.headers["location"] == "/login"
