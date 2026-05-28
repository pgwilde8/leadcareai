"""Inbound SMS routing by seeded/active phone number (SQLite)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.lead import Lead
from app.models.message import Message
from app.services.business_service import create_business
from app.services.phone_number_service import create_phone_number

TWILIO_SMS_URL = "/webhooks/twilio/sms"
LEADCARE_PHONE = "+18336691335"


@pytest.fixture(autouse=True)
def _twilio_webhook_auth_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TWILIO_WEBHOOK_AUTH_ENABLED", "false")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_inbound_sms_resolves_business_by_active_to_number(
    client: TestClient,
    db_session: Session,
) -> None:
    business = create_business(db_session, name="Routing Co")
    create_phone_number(
        db_session,
        business.id,
        LEADCARE_PHONE,
        provider="twilio",
        status="active",
    )
    db_session.commit()

    response = client.post(
        TWILIO_SMS_URL,
        data={
            "From": "+15551234567",
            "To": LEADCARE_PHONE,
            "Body": "Need help with a roof leak",
            "MessageSid": "SM_ROUTING_001",
        },
    )

    assert response.status_code == 200
    assert "<Response" in response.text
    assert db_session.query(Lead).count() == 1
    assert db_session.query(Message).filter(Message.direction == "inbound").count() == 1
    assert db_session.query(Message).filter(Message.direction == "outbound").count() == 1


def test_inbound_sms_ignores_inactive_to_number(
    client: TestClient,
    db_session: Session,
) -> None:
    business = create_business(db_session, name="Inactive Co")
    create_phone_number(
        db_session,
        business.id,
        LEADCARE_PHONE,
        provider="twilio",
        status="inactive",
    )
    db_session.commit()

    response = client.post(
        TWILIO_SMS_URL,
        data={
            "From": "+15551234567",
            "To": LEADCARE_PHONE,
            "Body": "Hello",
            "MessageSid": "SM_INACTIVE_001",
        },
    )

    assert response.status_code == 200
    assert db_session.query(Lead).count() == 0
    assert db_session.query(Message).count() == 0
