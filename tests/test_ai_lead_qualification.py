"""OpenAI lead qualification for inbound SMS (mocked)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.lead import Lead
from app.models.message import Message
from app.schemas.lead_ai import LeadAIAnalysis
from app.services.ai_service import analyze_inbound_sms_for_lead
from app.services.business_service import create_business
from app.services.phone_number_service import create_phone_number
from app.services.sms_service import _ai_guided_response_body
from app.services.twilio_service import SendSmsResult

TWILIO_SMS_URL = "/webhooks/twilio/sms"
BUSINESS_PHONE = "+18336691335"
SENDER_PHONE = "+15551234567"


@pytest.fixture(autouse=True)
def _twilio_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TWILIO_WEBHOOK_AUTH_ENABLED", "false")
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "AC_test")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "test_token")
    monkeypatch.setenv("TWILIO_PHONE_NUMBER", BUSINESS_PHONE)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _sample_analysis(**overrides) -> LeadAIAnalysis:
    data = {
        "service_needed": "roof repair",
        "urgency": "urgent",
        "location": "Austin, TX",
        "customer_name": "Jane",
        "summary": "Customer reports a roof leak after recent rain.",
        "lead_temperature": "hot",
        "next_question": "What part of the roof is leaking?",
        "confidence": 0.85,
    }
    data.update(overrides)
    return LeadAIAnalysis(**data)


def test_analyze_returns_structured_analysis_from_mocked_openai(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_ENABLED", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    get_settings.cache_clear()

    with patch("app.services.ai_service._call_openai", return_value=_sample_analysis()):
        result = analyze_inbound_sms_for_lead(
            business_name="Acme HVAC",
            business_industry="HVAC",
            customer_message="My AC stopped working",
        )

    assert result.service_needed == "roof repair"
    assert result.urgency == "urgent"
    assert result.lead_temperature == "hot"
    assert result.confidence == 0.85


def test_ai_disabled_returns_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_ENABLED", "false")
    get_settings.cache_clear()

    result = analyze_inbound_sms_for_lead(
        business_name="Acme",
        business_industry=None,
        customer_message="  Need help with plumbing  ",
    )

    assert result.urgency == "unknown"
    assert result.lead_temperature == "warm"
    assert result.summary == "Need help with plumbing"
    assert result.next_question is not None
    assert result.confidence == 0.0


def test_openai_exception_returns_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_ENABLED", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    get_settings.cache_clear()

    with patch("app.services.ai_service._call_openai", side_effect=RuntimeError("API down")):
        result = analyze_inbound_sms_for_lead(
            business_name="Acme",
            business_industry=None,
            customer_message="Help",
        )

    assert result.lead_temperature == "warm"
    assert result.confidence == 0.0


def test_next_question_capped_at_160_chars() -> None:
    long_q = "x" * 200
    analysis = LeadAIAnalysis(next_question=long_q, summary="s")
    capped = analysis.capped_next_question()
    assert capped is not None
    assert len(capped) <= 160


def test_forbidden_next_question_omitted_from_sms_body() -> None:
    analysis = LeadAIAnalysis(
        summary="s",
        next_question="We can call you back in 5 minutes with a $99 price",
    )
    body = _ai_guided_response_body("Acme Co", analysis)
    assert "$99" not in body
    assert "call you back in" not in body.lower()


def _setup_phone(db_session: Session) -> None:
    business = create_business(db_session, name="AI SMS Co", industry="Plumbing")
    create_phone_number(
        db_session,
        business.id,
        phone_number=BUSINESS_PHONE,
        provider="twilio",
        status="active",
    )
    db_session.commit()


@patch("app.services.ai_service._call_openai")
def test_inbound_sms_updates_lead_ai_fields(
    mock_openai: MagicMock,
    client: TestClient,
    db_session: Session,
    mock_twilio_send_sms: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_ENABLED", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    get_settings.cache_clear()
    mock_openai.return_value = _sample_analysis()
    mock_twilio_send_sms.return_value = SendSmsResult(sid="SM_AI_OUT", status="queued")

    _setup_phone(db_session)
    response = client.post(
        TWILIO_SMS_URL,
        data={
            "From": SENDER_PHONE,
            "To": BUSINESS_PHONE,
            "Body": "Water heater is leaking in garage",
            "MessageSid": "SM_AI_IN_001",
        },
    )
    assert response.status_code == 200

    lead = db_session.query(Lead).one()
    assert lead.service_needed == "roof repair"
    assert lead.ai_temperature == "hot"
    assert lead.ai_confidence == 0.85
    assert lead.ai_last_analyzed_at is not None
    assert lead.status == "qualifying"


@patch("app.services.ai_service._call_openai")
def test_inbound_sms_sends_ai_guided_next_question(
    mock_openai: MagicMock,
    client: TestClient,
    db_session: Session,
    mock_twilio_send_sms: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_ENABLED", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    get_settings.cache_clear()
    mock_openai.return_value = _sample_analysis(
        next_question="Is water actively pooling right now?",
    )
    mock_twilio_send_sms.return_value = SendSmsResult(sid="SM_AI_OUT2", status="queued")

    _setup_phone(db_session)
    client.post(
        TWILIO_SMS_URL,
        data={
            "From": SENDER_PHONE,
            "To": BUSINESS_PHONE,
            "Body": "Leak",
            "MessageSid": "SM_AI_IN_002",
        },
    )

    body = mock_twilio_send_sms.call_args.kwargs["body"]
    assert "AI SMS Co" in body
    assert "Is water actively pooling" in body
    assert "STOP" in body


@patch("app.services.ai_service._call_openai")
def test_duplicate_inbound_does_not_rerun_ai_or_send_duplicate_sms(
    mock_openai: MagicMock,
    client: TestClient,
    db_session: Session,
    mock_twilio_send_sms: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_ENABLED", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    get_settings.cache_clear()
    mock_openai.return_value = _sample_analysis()
    mock_twilio_send_sms.return_value = SendSmsResult(sid="SM_AI_DUP", status="queued")

    _setup_phone(db_session)
    data = {
        "From": SENDER_PHONE,
        "To": BUSINESS_PHONE,
        "Body": "Same",
        "MessageSid": "SM_AI_DUP_SID",
    }
    client.post(TWILIO_SMS_URL, data=data)
    client.post(TWILIO_SMS_URL, data=data)

    assert mock_openai.call_count == 1
    assert mock_twilio_send_sms.call_count == 1
    assert db_session.query(Message).filter(Message.direction == "inbound").count() == 1


@patch("app.services.ai_service._call_openai")
def test_inbound_without_next_question_uses_simple_reply(
    mock_openai: MagicMock,
    client: TestClient,
    db_session: Session,
    mock_twilio_send_sms: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_ENABLED", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    get_settings.cache_clear()
    mock_openai.return_value = _sample_analysis(next_question=None)
    mock_twilio_send_sms.return_value = SendSmsResult(sid="SM_AI_SIMPLE", status="queued")

    _setup_phone(db_session)
    client.post(
        TWILIO_SMS_URL,
        data={
            "From": SENDER_PHONE,
            "To": BUSINESS_PHONE,
            "Body": "Book service tomorrow",
            "MessageSid": "SM_AI_IN_003",
        },
    )

    body = mock_twilio_send_sms.call_args.kwargs["body"]
    assert "follow up shortly" in body
    assert "STOP" in body
