"""Outbound Twilio SMS auto-response tests (mocked; no real API)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.message import Message
from app.services.business_service import create_business
from app.services.phone_number_service import create_phone_number
from app.services.twilio_service import SendSmsResult, TwilioConfigError

TWILIO_SMS_URL = "/webhooks/twilio/sms"
BUSINESS_PHONE = "+18336691335"
SENDER_PHONE = "+15551234567"


@pytest.fixture(autouse=True)
def _twilio_env_and_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TWILIO_WEBHOOK_AUTH_ENABLED", "false")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC_test")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "test_token")
    monkeypatch.setenv("TWILIO_PHONE_NUMBER", "+18336691335")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def mock_send_sms(mock_twilio_send_sms: MagicMock):
    mock_twilio_send_sms.return_value = SendSmsResult(sid="SM_OUTBOUND_001", status="queued")
    return mock_twilio_send_sms


def _setup_business_phone(db_session: Session, name: str = "Outbound Co") -> None:
    business = create_business(db_session, name=name)
    create_phone_number(
        db_session,
        business.id,
        phone_number=BUSINESS_PHONE,
        provider="twilio",
        status="active",
    )
    db_session.commit()


def test_inbound_sms_sends_one_outbound_auto_response(
    client: TestClient,
    db_session: Session,
    mock_send_sms: MagicMock,
) -> None:
    _setup_business_phone(db_session)

    response = client.post(
        TWILIO_SMS_URL,
        data={
            "From": SENDER_PHONE,
            "To": BUSINESS_PHONE,
            "Body": "Need help",
            "MessageSid": "SM_IN_001",
        },
    )

    assert response.status_code == 200
    assert "<Response" in response.text
    mock_send_sms.assert_called_once()
    call_kwargs = mock_send_sms.call_args.kwargs
    assert call_kwargs["to_phone"] == SENDER_PHONE
    assert "Outbound Co" in mock_send_sms.call_args.kwargs["body"]

    outbound = (
        db_session.query(Message)
        .filter(Message.direction == "outbound", Message.provider_sid == "SM_OUTBOUND_001")
        .all()
    )
    assert len(outbound) == 1
    assert outbound[0].status == "queued"
    assert outbound[0].to_phone == SENDER_PHONE


def test_duplicate_inbound_does_not_send_second_outbound(
    client: TestClient,
    db_session: Session,
    mock_send_sms: MagicMock,
) -> None:
    _setup_business_phone(db_session)

    data = {
        "From": SENDER_PHONE,
        "To": BUSINESS_PHONE,
        "Body": "Need help",
        "MessageSid": "SM_IN_DUP",
    }
    client.post(TWILIO_SMS_URL, data=data)
    client.post(TWILIO_SMS_URL, data=data)

    assert mock_send_sms.call_count == 1
    assert db_session.query(Message).filter(Message.direction == "outbound").count() == 1


def test_twilio_outbound_failure_returns_200_and_stores_failed_message(
    client: TestClient,
    db_session: Session,
    mock_twilio_send_sms: MagicMock,
) -> None:
    _setup_business_phone(db_session)

    mock_twilio_send_sms.side_effect = Exception("Twilio API down")
    response = client.post(
        TWILIO_SMS_URL,
        data={
            "From": SENDER_PHONE,
            "To": BUSINESS_PHONE,
            "Body": "Hello",
            "MessageSid": "SM_IN_FAIL",
        },
    )

    assert response.status_code == 200
    assert "<Response" in response.text
    failed = (
        db_session.query(Message)
        .filter(Message.direction == "outbound", Message.status == "failed")
        .all()
    )
    assert len(failed) == 1
    assert failed[0].provider_sid is None


@pytest.mark.allow_real_twilio_send
def test_missing_twilio_phone_number_stores_failed_outbound_webhook_200(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TWILIO_PHONE_NUMBER", "")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC_test")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "test_token")
    get_settings.cache_clear()
    _setup_business_phone(db_session)

    response = client.post(
        TWILIO_SMS_URL,
        data={
            "From": SENDER_PHONE,
            "To": BUSINESS_PHONE,
            "Body": "Hello",
            "MessageSid": "SM_IN_NO_FROM_NUM",
        },
    )

    assert response.status_code == 200
    inbound = db_session.query(Message).filter(Message.direction == "inbound").count()
    assert inbound == 1
    failed = (
        db_session.query(Message)
        .filter(Message.direction == "outbound", Message.status == "failed")
        .all()
    )
    assert len(failed) == 1


def test_twilio_config_error_message_is_clear(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.twilio_service import send_sms

    monkeypatch.setenv("TWILIO_PHONE_NUMBER", "")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC_test")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "test_token")
    get_settings.cache_clear()

    with pytest.raises(TwilioConfigError, match="TWILIO_PHONE_NUMBER"):
        send_sms(to_phone="+15551234567", body="Hi")
