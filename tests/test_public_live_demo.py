"""Phase 3A: public live missed-call demo flow."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.lead import Lead
from app.models.message import Message
from app.services.business_service import create_business
from app.services.demo_live_service import DEMO_MISSED_CALL_SMS
from app.services.phone_number_service import create_phone_number

DEMO_PHONE = "+18336691335"
CALLER = "+15551234999"
VOICE_URL = "/webhooks/twilio/voice"
SMS_URL = "/webhooks/twilio/sms"


@pytest.fixture(autouse=True)
def _twilio_webhook_auth_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TWILIO_WEBHOOK_AUTH_ENABLED", "false")
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def demo_env(monkeypatch: pytest.MonkeyPatch, db_session: Session):
    business = create_business(db_session, name="LeadCare AI Demo", industry="Plumbing")
    create_phone_number(
        db_session,
        business.id,
        phone_number=DEMO_PHONE,
        provider="twilio",
        status="active",
    )
    db_session.commit()
    monkeypatch.setenv("DEMO_ENABLED", "true")
    monkeypatch.setenv("DEMO_BUSINESS_ID", str(business.id))
    monkeypatch.setenv("DEMO_TWILIO_NUMBER", DEMO_PHONE)
    get_settings.cache_clear()
    yield business
    get_settings.cache_clear()


def test_public_demo_page_loads(client: TestClient) -> None:
    response = client.get("/demo")
    assert response.status_code == 200
    assert "Try the missed-call demo" in response.text
    assert "1-833-669-1335" in response.text
    assert "Plumbing Demo" in response.text
    assert "demo dashboard" in response.text.lower()


def test_demo_voice_webhook_returns_demo_twiml(
    client: TestClient,
    db_session: Session,
    demo_env,
) -> None:
    response = client.post(
        VOICE_URL,
        data={
            "From": CALLER,
            "To": DEMO_PHONE,
            "CallSid": "CA_DEMO_TWIML_1",
            "CallStatus": "ringing",
        },
    )
    assert response.status_code == 200
    assert "just sent you a text message" in response.text
    assert "Thanks for calling. We will text you now." not in response.text


def test_demo_call_creates_lead_and_sends_demo_sms(
    client: TestClient,
    db_session: Session,
    demo_env,
    mock_twilio_send_sms,
) -> None:
    client.post(
        VOICE_URL,
        data={
            "From": CALLER,
            "To": DEMO_PHONE,
            "CallSid": "CA_DEMO_LEAD_1",
            "CallStatus": "ringing",
        },
    )
    leads = db_session.query(Lead).filter(Lead.business_id == demo_env.id).all()
    assert len(leads) == 1
    assert leads[0].phone == CALLER
    assert leads[0].source == "missed_call"
    assert mock_twilio_send_sms.called
    sent_body = mock_twilio_send_sms.call_args.kwargs.get("body") or mock_twilio_send_sms.call_args[1].get("body", "")
    assert DEMO_MISSED_CALL_SMS in sent_body
    outbound = (
        db_session.query(Message)
        .filter(Message.channel == "sms", Message.direction == "outbound")
        .all()
    )
    assert len(outbound) == 1
    assert "Joe's Plumbing Demo" in outbound[0].body or "Plumbing Demo" in outbound[0].body


def test_duplicate_demo_call_does_not_duplicate_lead(
    client: TestClient,
    db_session: Session,
    demo_env,
    mock_twilio_send_sms,
) -> None:
    data = {
        "From": CALLER,
        "To": DEMO_PHONE,
        "CallSid": "CA_DEMO_DUP_1",
        "CallStatus": "ringing",
    }
    client.post(VOICE_URL, data=data)
    client.post(VOICE_URL, data=data)
    leads = db_session.query(Lead).filter(Lead.business_id == demo_env.id).all()
    assert len(leads) == 1
    assert mock_twilio_send_sms.call_count == 1


def test_inbound_demo_sms_advances_intake(
    client: TestClient,
    db_session: Session,
    demo_env,
    mock_twilio_send_sms,
) -> None:
    client.post(
        VOICE_URL,
        data={
            "From": CALLER,
            "To": DEMO_PHONE,
            "CallSid": "CA_DEMO_SMS_FLOW",
            "CallStatus": "ringing",
        },
    )
    mock_twilio_send_sms.reset_mock()

    replies = [
        ("SM_DEMO_1", "Kitchen sink is backing up"),
        ("SM_DEMO_2", "Urgent leak in Austin"),
        ("SM_DEMO_3", "Jane Caller"),
        ("SM_DEMO_4", "jane@example.com"),
        ("SM_DEMO_5", "Callback today"),
    ]
    for sid, body in replies:
        client.post(
            SMS_URL,
            data={
                "From": CALLER,
                "To": DEMO_PHONE,
                "Body": body,
                "MessageSid": sid,
            },
        )

    lead = db_session.query(Lead).filter(Lead.business_id == demo_env.id).one()
    assert lead.service_needed == "Kitchen sink is backing up"
    assert lead.name == "Jane Caller"
    assert lead.email == "jane@example.com"
    assert lead.preferred_contact_time == "Callback today"
    assert lead.status == "qualified"
    assert mock_twilio_send_sms.call_count == 5
    last_body = mock_twilio_send_sms.call_args.kwargs.get("body", mock_twilio_send_sms.call_args[1].get("body", ""))
    assert "Joe's team has the details" in last_body


def test_demo_dashboard_masks_phone_numbers(
    client: TestClient,
    db_session: Session,
    demo_env,
) -> None:
    from app.services import lead_service

    lead_service.create_lead(
        db_session,
        demo_env.id,
        phone="+15557771234",
        source="missed_call",
        service_needed="Clogged drain",
        urgency="urgent",
        location="Round Rock",
        summary="Demo summary",
    )
    db_session.commit()

    response = client.get("/demo/dashboard")
    assert response.status_code == 200
    assert "Read-only sample view" in response.text
    assert "1234" in response.text
    assert "+15557771234" not in response.text
    assert "Clogged drain" in response.text


def test_demo_dashboard_is_read_only(client: TestClient, demo_env) -> None:
    response = client.get("/demo/dashboard")
    assert response.status_code == 200
    assert "cannot edit" in response.text.lower() or "read-only" in response.text.lower()
    assert 'href="/admin"' not in response.text
    assert 'href="/business/' not in response.text
    assert 'method="post"' not in response.text


def test_non_demo_phone_uses_standard_voice_twiml(
    client: TestClient,
    db_session: Session,
    demo_env,
) -> None:
    other = create_business(db_session, name="Other Co")
    other_phone = "+15559998888"
    create_phone_number(
        db_session,
        other.id,
        phone_number=other_phone,
        provider="twilio",
        status="active",
    )
    db_session.commit()

    response = client.post(
        VOICE_URL,
        data={
            "From": CALLER,
            "To": other_phone,
            "CallSid": "CA_OTHER_1",
            "CallStatus": "ringing",
        },
    )
    assert response.status_code == 200
    assert "Thanks for calling" in response.text
