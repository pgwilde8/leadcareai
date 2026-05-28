"""Business lead notification tests (mocked email/Twilio)."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.notification_log import NotificationLog
from app.services.business_service import create_business, link_user_to_business
from app.services.phone_number_service import create_phone_number
from app.services.user_service import create_user

VOICE_URL = "/webhooks/twilio/voice"
SMS_URL = "/webhooks/twilio/sms"
BUSINESS_PHONE = "+15559876543"
CALLER_PHONE = "+15551234567"


@pytest.fixture(autouse=True)
def _twilio_webhook_auth_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TWILIO_WEBHOOK_AUTH_ENABLED", "false")
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _setup_business_with_notifications(
    db_session: Session,
    *,
    name: str = "Notify Co",
    notification_email: str | None = "alerts@notifyco.example.com",
    notification_phone: str | None = "+15559990001",
) -> object:
    business = create_business(db_session, name=name)
    business.notification_email = notification_email
    business.notification_phone = notification_phone
    create_phone_number(
        db_session,
        business.id,
        BUSINESS_PHONE,
        provider="twilio",
        status="active",
    )
    db_session.commit()
    return business


@patch("app.services.notification_service._send_notification_email")
@patch("app.services.notification_service.send_sms")
def test_missed_call_triggers_email_and_staff_sms(
    mock_staff_sms,
    mock_email,
    client: TestClient,
    db_session: Session,
) -> None:
    from app.services.twilio_service import SendSmsResult

    mock_email.return_value = ("sent", None, None)
    mock_staff_sms.return_value = SendSmsResult(sid="SM_STAFF_001", status="queued")

    _setup_business_with_notifications(db_session)

    response = client.post(
        VOICE_URL,
        data={
            "From": CALLER_PHONE,
            "To": BUSINESS_PHONE,
            "CallSid": "CA_NOTIFY_001",
            "CallStatus": "ringing",
            "Direction": "inbound",
        },
    )
    assert response.status_code == 200
    assert mock_email.call_count == 1
    assert "New missed-call lead" in mock_email.call_args.kwargs["subject"]
    assert mock_staff_sms.call_count >= 1
    staff_calls = [
        c
        for c in mock_staff_sms.call_args_list
        if c.kwargs.get("to_phone") == "+15559990001" or c[1].get("to_phone") == "+15559990001"
    ]
    assert len(staff_calls) >= 1
    staff_body = staff_calls[0].kwargs.get("body") or staff_calls[0][1].get("body")
    assert "New lead" in staff_body
    assert CALLER_PHONE in staff_body

    logs = db_session.query(NotificationLog).all()
    assert len(logs) >= 2
    assert {log.event_type for log in logs} == {"missed_call"}


@patch("app.services.notification_service._send_notification_email")
@patch("app.services.notification_service.send_sms")
def test_inbound_sms_triggers_notification_once(
    mock_staff_sms,
    mock_email,
    client: TestClient,
    db_session: Session,
) -> None:
    mock_email.return_value = ("sent", None, None)
    mock_staff_sms.return_value = None

    _setup_business_with_notifications(
        db_session,
        notification_phone=None,
    )

    response = client.post(
        SMS_URL,
        data={
            "From": CALLER_PHONE,
            "To": BUSINESS_PHONE,
            "Body": "Need a plumber today",
            "MessageSid": "SM_NOTIFY_001",
        },
    )
    assert response.status_code == 200
    assert mock_email.call_count == 1
    assert "New SMS reply" in mock_email.call_args.kwargs["subject"]
    assert "Need a plumber today" in mock_email.call_args.kwargs["body"]

    logs = db_session.query(NotificationLog).filter_by(event_type="inbound_sms").all()
    assert len(logs) == 1


@patch("app.services.notification_service._send_notification_email")
def test_duplicate_call_sid_does_not_notify_twice(
    mock_email,
    client: TestClient,
    db_session: Session,
) -> None:
    mock_email.return_value = ("sent", None, None)
    _setup_business_with_notifications(db_session, notification_phone=None)

    sid = "CA_NOTIFY_DUP"
    first = client.post(
        VOICE_URL,
        data={
            "From": CALLER_PHONE,
            "To": BUSINESS_PHONE,
            "CallSid": sid,
            "CallStatus": "ringing",
            "Direction": "inbound",
        },
    )
    second = client.post(
        VOICE_URL,
        data={
            "From": CALLER_PHONE,
            "To": BUSINESS_PHONE,
            "CallSid": sid,
            "CallStatus": "completed",
            "Direction": "inbound",
        },
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert mock_email.call_count == 1


@patch("app.services.notification_service._send_notification_email")
def test_duplicate_message_sid_does_not_notify_twice(
    mock_email,
    client: TestClient,
    db_session: Session,
) -> None:
    mock_email.return_value = ("sent", None, None)
    _setup_business_with_notifications(db_session, notification_phone=None)

    sid = "SM_NOTIFY_DUP"
    client.post(
        SMS_URL,
        data={
            "From": CALLER_PHONE,
            "To": BUSINESS_PHONE,
            "Body": "First",
            "MessageSid": sid,
        },
    )
    client.post(
        SMS_URL,
        data={
            "From": CALLER_PHONE,
            "To": BUSINESS_PHONE,
            "Body": "Duplicate",
            "MessageSid": sid,
        },
    )
    assert mock_email.call_count == 1


@patch("app.services.notification_service._send_notification_email", side_effect=RuntimeError("smtp down"))
def test_notification_failure_does_not_fail_webhook(
    mock_email,
    client: TestClient,
    db_session: Session,
) -> None:
    _setup_business_with_notifications(db_session, notification_phone=None)

    response = client.post(
        VOICE_URL,
        data={
            "From": CALLER_PHONE,
            "To": BUSINESS_PHONE,
            "CallSid": "CA_NOTIFY_FAIL",
            "CallStatus": "ringing",
            "Direction": "inbound",
        },
    )
    assert response.status_code == 200
    assert "<Response" in response.text


@patch("app.services.notification_service.send_sms")
def test_staff_sms_skipped_when_same_as_customer_phone(
    mock_staff_sms,
    client: TestClient,
    db_session: Session,
) -> None:
    _setup_business_with_notifications(
        db_session,
        notification_email=None,
        notification_phone=CALLER_PHONE,
    )

    client.post(
        VOICE_URL,
        data={
            "From": CALLER_PHONE,
            "To": BUSINESS_PHONE,
            "CallSid": "CA_SAME_PHONE",
            "CallStatus": "ringing",
            "Direction": "inbound",
        },
    )

    staff_to_customer = [
        c
        for c in mock_staff_sms.call_args_list
        if (c.kwargs.get("to_phone") or c[1].get("to_phone")) == CALLER_PHONE
    ]
    assert staff_to_customer == []

    skipped = (
        db_session.query(NotificationLog)
        .filter_by(channel="sms", status="skipped")
        .all()
    )
    assert len(skipped) >= 1


def test_no_notification_when_fields_blank(
    client: TestClient,
    db_session: Session,
) -> None:
    with patch("app.services.notification_service._send_notification_email") as mock_email:
        with patch("app.services.notification_service.send_sms") as mock_sms:
            _setup_business_with_notifications(
                db_session,
                notification_email=None,
                notification_phone=None,
            )
            client.post(
                VOICE_URL,
                data={
                    "From": CALLER_PHONE,
                    "To": BUSINESS_PHONE,
                    "CallSid": "CA_NO_NOTIFY",
                    "CallStatus": "ringing",
                    "Direction": "inbound",
                },
            )
            assert mock_email.call_count == 0
            assert mock_sms.call_count == 0

    logs = db_session.query(NotificationLog).count()
    assert logs == 0


@patch("app.services.notification_service.send_sms")
def test_staff_sms_includes_dashboard_link_when_public_base_url_set(
    mock_staff_sms,
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.twilio_service import SendSmsResult

    monkeypatch.setenv("PUBLIC_BASE_URL", "https://leadcareai.example.com")
    get_settings.cache_clear()
    mock_staff_sms.return_value = SendSmsResult(sid="SM_LINK", status="queued")

    _setup_business_with_notifications(db_session, notification_email=None)

    client.post(
        VOICE_URL,
        data={
            "From": CALLER_PHONE,
            "To": BUSINESS_PHONE,
            "CallSid": "CA_LINK_001",
            "CallStatus": "ringing",
            "Direction": "inbound",
        },
    )

    staff_calls = [c for c in mock_staff_sms.call_args_list if "to_phone" in (c.kwargs or c[1])]
    assert staff_calls
    body = staff_calls[-1].kwargs.get("body") or staff_calls[-1][1].get("body")
    assert "https://leadcareai.example.com/business/leads/" in body


@patch("app.services.notification_service.send_sms")
def test_staff_sms_omits_url_when_public_base_url_missing(
    mock_staff_sms,
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.twilio_service import SendSmsResult

    monkeypatch.setenv("APP_BASE_URL", "")
    monkeypatch.setenv("PUBLIC_BASE_URL", "")
    get_settings.cache_clear()
    mock_staff_sms.return_value = SendSmsResult(sid="SM_NOURL", status="queued")

    _setup_business_with_notifications(db_session, notification_email=None)

    client.post(
        VOICE_URL,
        data={
            "From": CALLER_PHONE,
            "To": BUSINESS_PHONE,
            "CallSid": "CA_NOURL_001",
            "CallStatus": "ringing",
            "Direction": "inbound",
        },
    )

    body = mock_staff_sms.call_args.kwargs.get("body") or mock_staff_sms.call_args[1].get("body")
    assert "View dashboard" not in body
