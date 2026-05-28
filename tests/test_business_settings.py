"""Business settings page and missed-call message tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings

from app.services import phone_number_service
from app.services.business_service import create_business, link_user_to_business
from app.services.business_settings_service import (
    MISSED_CALL_MESSAGE_MAX_LEN,
    build_missed_call_textback_body,
    normalize_missed_call_textback_message,
)
from app.services.user_service import create_user

SETTINGS_URL = "/business/settings"


@pytest.fixture(autouse=True)
def _twilio_webhook_auth_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TWILIO_WEBHOOK_AUTH_ENABLED", "false")
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _create_business_user(
    db_session: Session,
    *,
    email: str,
    password: str,
    business_name: str,
):
    business = create_business(db_session, name=business_name)
    user = create_user(
        db_session,
        email=email,
        password=password,
        role="business_user",
    )
    link_user_to_business(db_session, user.id, business.id)
    db_session.commit()
    return user, business


def _login(client: TestClient, email: str, password: str) -> None:
    client.post("/login", data={"email": email, "password": password})


def test_business_user_can_get_settings(
    client: TestClient,
    db_session: Session,
) -> None:
    _user, business = _create_business_user(
        db_session,
        email="settings@example.com",
        password="settings-secret",
        business_name="Settings Co",
    )
    phone_number_service.create_phone_number(
        db_session,
        business.id,
        "+15551234000",
        provider="twilio",
        status="active",
    )
    db_session.commit()

    _login(client, "settings@example.com", "settings-secret")
    response = client.get(SETTINGS_URL)
    assert response.status_code == 200
    assert "Business settings" in response.text
    assert "Settings Co" in response.text
    assert "+15551234000" in response.text
    assert "Read-only" in response.text
    assert "notification_email" in response.text
    assert "best-effort" in response.text


def test_unauthenticated_user_blocked(client: TestClient) -> None:
    response = client.get(SETTINGS_URL, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_partner_user_blocked(
    client: TestClient,
    db_session: Session,
) -> None:
    from app.models.partner import Partner

    user = create_user(
        db_session,
        email="partner-settings@example.com",
        password="partner-secret",
        role="partner",
    )
    db_session.add(
        Partner(
            user_id=user.id,
            display_name="Partner Settings",
            email=user.email,
            phone="+15551230099",
            referral_code="REFSET001",
            status="active",
        )
    )
    db_session.commit()
    _login(client, "partner-settings@example.com", "partner-secret")

    response = client.get(SETTINGS_URL, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_business_users_see_only_own_settings(
    client: TestClient,
    db_session: Session,
) -> None:
    _create_business_user(
        db_session,
        email="biz-a-settings@example.com",
        password="a-secret",
        business_name="Alpha Settings LLC",
    )
    _create_business_user(
        db_session,
        email="biz-b-settings@example.com",
        password="b-secret",
        business_name="Beta Settings LLC",
    )

    _login(client, "biz-a-settings@example.com", "a-secret")
    page_a = client.get(SETTINGS_URL)
    assert "Alpha Settings LLC" in page_a.text
    assert "Beta Settings LLC" not in page_a.text

    client.post("/logout")
    _login(client, "biz-b-settings@example.com", "b-secret")
    page_b = client.get(SETTINGS_URL)
    assert "Beta Settings LLC" in page_b.text
    assert "Alpha Settings LLC" not in page_b.text


def test_post_updates_business_profile(
    client: TestClient,
    db_session: Session,
) -> None:
    _user, business = _create_business_user(
        db_session,
        email="update@example.com",
        password="update-secret",
        business_name="Old Name Co",
    )
    db_session.commit()

    _login(client, "update@example.com", "update-secret")
    response = client.post(
        SETTINGS_URL,
        data={
            "name": "New Name Co",
            "industry": "HVAC",
            "website_url": "https://newname.example.com",
            "contact_email": "hello@newname.example.com",
            "contact_phone": "+15551112222",
            "notification_email": "alerts@newname.example.com",
            "notification_phone": "+15553334444",
            "missed_call_textback_message": "",
            "sms_signature": "New Name",
            "lead_intake_prompt": "Ask about urgency first.",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/business/settings?saved=1"

    db_session.expire_all()
    db_session.refresh(business)
    assert business.name == "New Name Co"
    assert business.industry == "HVAC"
    assert business.contact_email == "hello@newname.example.com"
    assert business.main_phone == "+15551112222"
    assert business.notification_email == "alerts@newname.example.com"
    assert business.sms_signature == "New Name"
    assert business.lead_intake_prompt == "Ask about urgency first."


def test_blank_missed_call_message_rejected(
    client: TestClient,
    db_session: Session,
) -> None:
    _create_business_user(
        db_session,
        email="blank@example.com",
        password="blank-secret",
        business_name="Blank Msg Co",
    )
    _login(client, "blank@example.com", "blank-secret")

    response = client.post(
        SETTINGS_URL,
        data={
            "name": "Blank Msg Co",
            "missed_call_textback_message": "   ",
        },
    )
    assert response.status_code == 400
    assert "cannot be blank" in response.text


def test_long_missed_call_message_rejected(
    client: TestClient,
    db_session: Session,
) -> None:
    _create_business_user(
        db_session,
        email="long@example.com",
        password="long-secret",
        business_name="Long Msg Co",
    )
    _login(client, "long@example.com", "long-secret")

    too_long = "x" * (MISSED_CALL_MESSAGE_MAX_LEN + 5) + " STOP"
    response = client.post(
        SETTINGS_URL,
        data={
            "name": "Long Msg Co",
            "missed_call_textback_message": too_long,
        },
    )
    assert response.status_code == 400
    assert "240" in response.text


def test_message_without_stop_gets_stop_appended() -> None:
    normalized = normalize_missed_call_textback_message("We missed your call — reply here.")
    assert normalized is not None
    assert "STOP" in normalized
    assert normalized.endswith("opt out.")


def test_missed_call_sms_uses_custom_business_message(
    client: TestClient,
    db_session: Session,
    mock_twilio_send_sms,
) -> None:
    from tests.test_twilio_inbound_voice import BUSINESS_PHONE, CALLER_PHONE, VOICE_URL

    business = create_business(db_session, name="Custom SMS Co")
    business.missed_call_textback_message = (
        "Custom Co: Thanks for calling. Text us back. Reply STOP to opt out."
    )
    phone_number_service.create_phone_number(
        db_session,
        business.id,
        BUSINESS_PHONE,
        provider="twilio",
        status="active",
    )
    db_session.commit()

    response = client.post(
        VOICE_URL,
        data={
            "From": CALLER_PHONE,
            "To": BUSINESS_PHONE,
            "CallSid": "CA_CUSTOM_MSG_001",
            "CallStatus": "ringing",
            "Direction": "inbound",
        },
    )
    assert response.status_code == 200
    sent_body = mock_twilio_send_sms.call_args.kwargs.get("body") or mock_twilio_send_sms.call_args[1].get(
        "body"
    )
    assert "Thanks for calling. Text us back." in sent_body
    assert "Custom Co" in sent_body


def test_missed_call_sms_fallback_default_without_custom_message(
    client: TestClient,
    db_session: Session,
    mock_twilio_send_sms,
) -> None:
    from tests.test_twilio_inbound_voice import BUSINESS_PHONE, CALLER_PHONE, VOICE_URL

    business = create_business(db_session, name="Default SMS Co")
    phone_number_service.create_phone_number(
        db_session,
        business.id,
        BUSINESS_PHONE,
        provider="twilio",
        status="active",
    )
    db_session.commit()

    client.post(
        VOICE_URL,
        data={
            "From": CALLER_PHONE,
            "To": BUSINESS_PHONE,
            "CallSid": "CA_DEFAULT_MSG_001",
            "CallStatus": "ringing",
            "Direction": "inbound",
        },
    )
    sent_body = mock_twilio_send_sms.call_args.kwargs.get("body") or mock_twilio_send_sms.call_args[1].get(
        "body"
    )
    assert "Default SMS Co" in sent_body
    assert "Sorry we missed your call" in sent_body


def test_build_missed_call_textback_body_prefers_custom(db_session: Session) -> None:
    business = create_business(db_session, name="Test Co")
    business.missed_call_textback_message = "Hi there STOP"
    assert build_missed_call_textback_body(business) == "Hi there STOP"
