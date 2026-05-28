"""Public contact form."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.contact_message import ContactMessage
from app.services.email_service import EmailSendResult


def test_contact_page_renders_form(client: TestClient) -> None:
    response = client.get("/contact")
    assert response.status_code == 200
    assert 'name="message"' in response.text
    assert "Send message" in response.text


def test_contact_submit_persists_and_emails(client: TestClient, db_session: Session) -> None:
    settings = get_settings()
    with patch(
        "app.services.contact_service.send_email",
        return_value=EmailSendResult(status="sent"),
    ) as send_mock:
        response = client.post(
            "/contact",
            data={
                "name": "Jane Smith",
                "email": "jane@example.com",
                "phone": "+15551234567",
                "subject": "General inquiry",
                "message": "I would like to learn more about LeadCareAI for my HVAC business.",
            },
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"] == "/contact/success"

    row = db_session.query(ContactMessage).filter(ContactMessage.email == "jane@example.com").one()
    assert row.name == "Jane Smith"
    assert row.subject == "General inquiry"
    assert row.email_status == "sent"

    send_mock.assert_called_once()
    assert send_mock.call_args.kwargs["to_email"] == settings.default_support_email
    assert "Jane Smith" in send_mock.call_args.kwargs["body"]


def test_contact_submit_validation_error(client: TestClient, db_session: Session) -> None:
    response = client.post(
        "/contact",
        data={
            "name": "J",
            "email": "not-an-email",
            "subject": "General inquiry",
            "message": "short",
        },
    )
    assert response.status_code == 400
    assert "valid email" in response.text.lower() or "email" in response.text.lower()
    assert db_session.query(ContactMessage).count() == 0


def test_contact_honeypot_skips_persist(client: TestClient, db_session: Session) -> None:
    response = client.post(
        "/contact",
        data={
            "name": "Bot",
            "email": "bot@example.com",
            "subject": "General inquiry",
            "message": "This is spam content from a bot.",
            "website": "http://spam.example",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert db_session.query(ContactMessage).count() == 0


def test_contact_success_page(client: TestClient) -> None:
    response = client.get("/contact/success")
    assert response.status_code == 200
    assert "Thank you" in response.text
