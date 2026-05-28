"""Twilio inbound SMS webhook tests (SQLite; no real Twilio credentials)."""

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
BUSINESS_PHONE = "+15559876543"
SENDER_PHONE = "+15551234567"


@pytest.fixture(autouse=True)
def _twilio_webhook_auth_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TWILIO_WEBHOOK_AUTH_ENABLED", "false")
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _post_sms(client: TestClient, **fields: str) -> object:
    data = {
        "From": SENDER_PHONE,
        "To": BUSINESS_PHONE,
        "Body": "Need help with a roof leak",
        "MessageSid": "SM_TEST_001",
    }
    data.update(fields)
    return client.post(TWILIO_SMS_URL, data=data)


def _setup_business_phone(db_session: Session) -> None:
    business = create_business(db_session, name="Twilio SMS Co")
    create_phone_number(
        db_session,
        business.id,
        phone_number=BUSINESS_PHONE,
        provider="twilio",
        status="active",
    )
    db_session.commit()


def test_unknown_to_returns_twiml_without_lead_or_message(
    client: TestClient,
    db_session: Session,
) -> None:
    create_business(db_session, name="No Phone Co")
    db_session.commit()

    response = _post_sms(client, To="+15550001111")

    assert response.status_code == 200
    assert "<Response" in response.text
    assert db_session.query(Lead).count() == 0
    assert db_session.query(Message).count() == 0


def test_known_to_creates_lead_and_inbound_message(
    client: TestClient,
    db_session: Session,
) -> None:
    _setup_business_phone(db_session)

    response = _post_sms(client, MessageSid="SM_TEST_NEW_001")

    assert response.status_code == 200
    assert "<Response" in response.text

    leads = db_session.query(Lead).all()
    assert len(leads) == 1
    assert leads[0].phone == SENDER_PHONE
    assert leads[0].source == "sms"
    assert leads[0].status in {"new", "qualifying"}
    assert "roof leak" in (leads[0].summary or "")
    assert leads[0].ai_last_analyzed_at is not None

    inbound = (
        db_session.query(Message).filter(Message.direction == "inbound").all()
    )
    assert len(inbound) == 1
    assert inbound[0].channel == "sms"
    assert inbound[0].provider == "twilio"
    assert inbound[0].status == "received"
    assert inbound[0].provider_sid == "SM_TEST_NEW_001"
    assert inbound[0].body == "Need help with a roof leak"
    assert db_session.query(Message).filter(Message.direction == "outbound").count() == 1


def test_second_sms_reuses_existing_lead(
    client: TestClient,
    db_session: Session,
) -> None:
    _setup_business_phone(db_session)

    first = _post_sms(client, MessageSid="SM_TEST_REUSE_001", Body="First message")
    assert first.status_code == 200

    second = _post_sms(
        client,
        MessageSid="SM_TEST_REUSE_002",
        Body="Second message",
    )
    assert second.status_code == 200

    assert db_session.query(Lead).count() == 1
    assert db_session.query(Message).filter(Message.direction == "inbound").count() == 2
    assert db_session.query(Message).filter(Message.direction == "outbound").count() == 2


def test_duplicate_message_sid_does_not_duplicate_message(
    client: TestClient,
    db_session: Session,
) -> None:
    _setup_business_phone(db_session)

    sid = "SM_TEST_DUP_001"
    first = _post_sms(client, MessageSid=sid)
    second = _post_sms(client, MessageSid=sid, Body="Duplicate attempt")

    assert first.status_code == 200
    assert second.status_code == 200
    assert db_session.query(Lead).count() == 1
    assert db_session.query(Message).filter(Message.direction == "inbound").count() == 1
    assert db_session.query(Message).filter(Message.direction == "outbound").count() == 1


def test_missing_body_returns_twiml_without_message(
    client: TestClient,
    db_session: Session,
) -> None:
    _setup_business_phone(db_session)

    response = client.post(
        TWILIO_SMS_URL,
        data={
            "From": SENDER_PHONE,
            "To": BUSINESS_PHONE,
            "Body": "",
            "MessageSid": "SM_TEST_NO_BODY",
        },
    )

    assert response.status_code == 200
    assert "<Response" in response.text
    assert db_session.query(Message).count() == 0


def test_missing_from_returns_twiml_without_message(
    client: TestClient,
    db_session: Session,
) -> None:
    _setup_business_phone(db_session)

    response = client.post(
        TWILIO_SMS_URL,
        data={
            "From": "",
            "To": BUSINESS_PHONE,
            "Body": "Hello",
            "MessageSid": "SM_TEST_NO_FROM",
        },
    )

    assert response.status_code == 200
    assert "<Response" in response.text
    assert db_session.query(Message).count() == 0


def test_missing_to_returns_twiml_without_message(
    client: TestClient,
    db_session: Session,
) -> None:
    _setup_business_phone(db_session)

    response = client.post(
        TWILIO_SMS_URL,
        data={
            "From": SENDER_PHONE,
            "To": "",
            "Body": "Hello",
            "MessageSid": "SM_TEST_NO_TO",
        },
    )

    assert response.status_code == 200
    assert "<Response" in response.text
    assert db_session.query(Message).count() == 0


def test_route_works_without_twilio_credentials_when_auth_disabled(
    client: TestClient,
    db_session: Session,
) -> None:
    settings = get_settings()
    assert settings.twilio_webhook_auth_enabled is False

    _setup_business_phone(db_session)
    response = _post_sms(client, MessageSid="SM_TEST_NO_CREDS")

    assert response.status_code == 200
    assert "<Response" in response.text
    assert db_session.query(Message).filter(Message.direction == "inbound").count() == 1
    assert db_session.query(Message).filter(Message.direction == "outbound").count() == 1
