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
from app.models.business import Business
from app.services.business_settings_service import resolve_outbound_sms_label
from app.services.lead_service import recommended_action_for_lead
from app.services.sms_service import SMS_TEMPLATE_LIBRARY, _ai_guided_response_body
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


def test_resolve_outbound_sms_label_prefers_signature_then_name() -> None:
    business = Business(name="Long Business Name LLC", sms_signature="Joe's Plumbing")
    assert resolve_outbound_sms_label(business) == "Joe's Plumbing"
    assert resolve_outbound_sms_label(Business(name="Only Name Co")) == "Only Name Co"
    assert resolve_outbound_sms_label() == "LeadCare AI"


def test_sms_signature_used_as_outbound_opener_over_business_name() -> None:
    business = Business(name="Acme HVAC Services", sms_signature="Joe's Plumbing")
    analysis = LeadAIAnalysis(
        summary="s",
        next_question="What town are you in?",
        confidence=0.9,
    )
    body = _ai_guided_response_body(business, analysis, "no heat at home")
    assert body.startswith("Joe's Plumbing:")
    assert "Acme HVAC" not in body.split(":", 1)[0]


def test_forbidden_next_question_omitted_from_sms_body() -> None:
    analysis = LeadAIAnalysis(
        summary="s",
        next_question="We can call you back in 5 minutes with a $99 price",
    )
    business = Business(name="Acme Co")
    body = _ai_guided_response_body(business, analysis, "Need help")
    assert "$99" not in body
    assert "call you back in" not in body.lower()
    assert "What service is needed" in body


def test_one_question_per_message_is_enforced() -> None:
    analysis = LeadAIAnalysis(
        summary="s",
        next_question="What service? What town are you in? Is this urgent?",
        confidence=0.9,
    )
    body = _ai_guided_response_body(Business(name="Acme Co"), analysis, "Need service")
    assert body.count("?") == 1


def test_urgent_routing_adds_safety_line() -> None:
    analysis = LeadAIAnalysis(
        summary="s",
        urgency="urgent",
        next_question="What town are you in?",
        confidence=0.9,
    )
    body = _ai_guided_response_body(Business(name="Acme Co"), analysis, "leak now at home")
    assert "call 911" in body.lower()
    assert body.startswith("Acme Co:")
    assert len(body) <= 160


def test_low_confidence_uses_safe_fallback_template() -> None:
    analysis = LeadAIAnalysis(
        summary="s",
        next_question="Tell me everything in detail?",
        confidence=0.1,
    )
    body = _ai_guided_response_body(Business(name="Acme Co"), analysis, "Need help")
    assert "What service is needed and what town are you in?" in body
    assert body.endswith("Reply STOP to opt out.")
    assert len(body) <= 160


def test_template_library_contains_phase_1q_keys() -> None:
    keys = {"missed_call", "inbound_sms", "urgent", "fallback", "handoff"}
    assert keys.issubset(set(SMS_TEMPLATE_LIBRARY.keys()))


def test_recommended_action_helper_behavior() -> None:
    hot_urgent = Lead(ai_temperature="hot", urgency="urgent")
    assert recommended_action_for_lead(hot_urgent) == "Call immediately"

    hot = Lead(ai_temperature="hot", urgency="unknown")
    assert recommended_action_for_lead(hot) == "Call as soon as possible"

    warm = Lead(ai_temperature="warm")
    assert recommended_action_for_lead(warm) == "Follow up today"

    cold = Lead(ai_temperature="cold")
    assert recommended_action_for_lead(cold) == "Review when available"

    no_ai = Lead()
    assert recommended_action_for_lead(no_ai) == "Review lead details"


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
    assert body.count("?") <= 1
    assert len(body) <= 160


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
    assert "What service is needed and what town are you in?" in body
    assert "STOP" in body
    assert len(body) <= 160
