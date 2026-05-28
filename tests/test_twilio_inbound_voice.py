"""Twilio inbound voice webhook tests (missed-call text-back)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.twilio_webhook import compute_twilio_signature
from app.models.lead import Lead
from app.models.message import Message
from app.services.business_service import create_business
from app.services.phone_number_service import create_phone_number

VOICE_URL = "/webhooks/twilio/voice"
VOICE_STATUS_URL = "/webhooks/twilio/voice/status"
BUSINESS_PHONE = "+15559876543"
CALLER_PHONE = "+15551234567"
CALL_SID = "CA_TEST_VOICE_001"


@pytest.fixture(autouse=True)
def _twilio_webhook_auth_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TWILIO_WEBHOOK_AUTH_ENABLED", "false")
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _post_voice(client: TestClient, **fields: str) -> object:
    data = {
        "From": CALLER_PHONE,
        "To": BUSINESS_PHONE,
        "CallSid": CALL_SID,
        "CallStatus": "ringing",
        "Direction": "inbound",
    }
    data.update(fields)
    return client.post(VOICE_URL, data=data)


def _post_voice_status(client: TestClient, **fields: str) -> object:
    data = {
        "CallSid": CALL_SID,
        "CallStatus": "completed",
        "From": CALLER_PHONE,
        "To": BUSINESS_PHONE,
        "CallDuration": "12",
        "Direction": "inbound",
    }
    data.update(fields)
    return client.post(VOICE_STATUS_URL, data=data)


def _setup_business_phone(db_session: Session) -> None:
    business = create_business(db_session, name="Twilio Voice Co")
    create_phone_number(
        db_session,
        business.id,
        phone_number=BUSINESS_PHONE,
        provider="twilio",
        status="active",
    )
    db_session.commit()


def test_voice_webhook_returns_xml_with_say_and_hangup(
    client: TestClient,
    db_session: Session,
) -> None:
    _setup_business_phone(db_session)

    response = _post_voice(client, CallSid="CA_TEST_XML_001")

    assert response.status_code == 200
    assert "application/xml" in response.headers.get("content-type", "")
    assert "<Response" in response.text
    assert "<Say>" in response.text
    assert "Thanks for calling" in response.text
    assert "<Hangup" in response.text


def test_active_to_creates_lead_and_voice_message(
    client: TestClient,
    db_session: Session,
) -> None:
    _setup_business_phone(db_session)

    response = _post_voice(client, CallSid="CA_TEST_LEAD_001")

    assert response.status_code == 200

    leads = db_session.query(Lead).all()
    assert len(leads) == 1
    assert leads[0].phone == CALLER_PHONE
    assert leads[0].source == "missed_call"
    assert leads[0].status in {"new", "qualifying"}
    assert CALLER_PHONE in (leads[0].summary or "")

    inbound = (
        db_session.query(Message)
        .filter(Message.direction == "inbound", Message.channel == "voice")
        .all()
    )
    assert len(inbound) == 1
    assert inbound[0].provider == "twilio"
    assert inbound[0].provider_sid == "CA_TEST_LEAD_001"
    assert inbound[0].status == "ringing"
    assert "Inbound call" in inbound[0].body


def test_active_to_sends_one_missed_call_sms(
    client: TestClient,
    db_session: Session,
    mock_twilio_send_sms,
) -> None:
    _setup_business_phone(db_session)

    response = _post_voice(client, CallSid="CA_TEST_SMS_001")

    assert response.status_code == 200
    assert mock_twilio_send_sms.call_count == 1
    sent_body = mock_twilio_send_sms.call_args.kwargs.get("body") or mock_twilio_send_sms.call_args[1].get("body")
    assert "Sorry we missed your call" in sent_body
    assert "Twilio Voice Co" in sent_body
    assert "STOP" in sent_body

    outbound = (
        db_session.query(Message)
        .filter(Message.direction == "outbound", Message.channel == "sms")
        .all()
    )
    assert len(outbound) == 1
    assert "Sorry we missed your call" in outbound[0].body


def test_duplicate_call_sid_does_not_duplicate_sms(
    client: TestClient,
    db_session: Session,
    mock_twilio_send_sms,
) -> None:
    _setup_business_phone(db_session)

    sid = "CA_TEST_DUP_001"
    first = _post_voice(client, CallSid=sid)
    second = _post_voice(client, CallSid=sid)

    assert first.status_code == 200
    assert second.status_code == 200
    assert db_session.query(Lead).count() == 1
    assert (
        db_session.query(Message)
        .filter(Message.direction == "inbound", Message.channel == "voice")
        .count()
        == 1
    )
    assert mock_twilio_send_sms.call_count == 1
    assert (
        db_session.query(Message)
        .filter(Message.direction == "outbound", Message.channel == "sms")
        .count()
        == 1
    )


def test_unknown_to_returns_200_without_sms(
    client: TestClient,
    db_session: Session,
    mock_twilio_send_sms,
) -> None:
    create_business(db_session, name="No Phone Co")
    db_session.commit()

    response = _post_voice(client, To="+15550001111", CallSid="CA_TEST_UNKNOWN_001")

    assert response.status_code == 200
    assert "<Response" in response.text
    assert db_session.query(Lead).count() == 0
    assert db_session.query(Message).count() == 0
    assert mock_twilio_send_sms.call_count == 0


def test_inactive_to_returns_200_without_sms(
    client: TestClient,
    db_session: Session,
    mock_twilio_send_sms,
) -> None:
    business = create_business(db_session, name="Inactive Phone Co")
    create_phone_number(
        db_session,
        business.id,
        phone_number=BUSINESS_PHONE,
        provider="twilio",
        status="inactive",
    )
    db_session.commit()

    response = _post_voice(client, CallSid="CA_TEST_INACTIVE_001")

    assert response.status_code == 200
    assert db_session.query(Lead).count() == 0
    assert db_session.query(Message).count() == 0
    assert mock_twilio_send_sms.call_count == 0


def test_missing_fields_do_not_crash(
    client: TestClient,
    db_session: Session,
    mock_twilio_send_sms,
) -> None:
    _setup_business_phone(db_session)

    for payload in (
        {"From": "", "To": BUSINESS_PHONE, "CallSid": "CA_NO_FROM"},
        {"From": CALLER_PHONE, "To": "", "CallSid": "CA_NO_TO"},
        {"From": CALLER_PHONE, "To": BUSINESS_PHONE, "CallSid": ""},
    ):
        response = client.post(VOICE_URL, data=payload)
        assert response.status_code == 200
        assert "<Response" in response.text

    assert mock_twilio_send_sms.call_count == 0


def test_status_webhook_returns_200_and_updates_call_status(
    client: TestClient,
    db_session: Session,
) -> None:
    _setup_business_phone(db_session)
    _post_voice(client, CallSid=CALL_SID)
    db_session.expire_all()

    response = _post_voice_status(client, CallStatus="completed", CallDuration="15")

    assert response.status_code == 200

    voice_msg = (
        db_session.query(Message)
        .filter(Message.channel == "voice", Message.provider_sid == CALL_SID)
        .one()
    )
    assert voice_msg.status == "completed"
    assert "duration 15s" in voice_msg.body


def test_status_webhook_missing_fields_returns_200(
    client: TestClient,
) -> None:
    response = client.post(VOICE_STATUS_URL, data={})
    assert response.status_code == 200


def test_voice_webhook_signature_auth_when_enabled(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_business_phone(db_session)
    monkeypatch.setenv("TWILIO_WEBHOOK_AUTH_ENABLED", "true")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "test_auth_token_for_voice")
    get_settings.cache_clear()

    data = {
        "From": CALLER_PHONE,
        "To": BUSINESS_PHONE,
        "CallSid": "CA_TEST_AUTH_001",
        "CallStatus": "ringing",
        "Direction": "inbound",
    }
    unsigned = client.post(VOICE_URL, data=data)
    assert unsigned.status_code == 403

    url = "http://testserver/webhooks/twilio/voice"
    signature = compute_twilio_signature(url, data, "test_auth_token_for_voice")
    signed = client.post(
        VOICE_URL,
        data=data,
        headers={"X-Twilio-Signature": signature},
    )
    assert signed.status_code == 200
    assert "<Say>" in signed.text

    get_settings.cache_clear()
