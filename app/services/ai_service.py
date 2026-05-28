"""OpenAI-assisted inbound SMS lead qualification (structured intake only)."""

from __future__ import annotations

import json
import logging
from typing import Any

from app.core.config import get_settings
from app.schemas.lead_ai import LeadAIAnalysis

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an intake classifier for a local service business SMS line.
Analyze the customer's latest SMS and return structured JSON only.

Rules:
- Do not quote prices or fees.
- Do not promise appointment times or that someone is available now.
- Do not claim a human has read the message or will call immediately.
- Do not provide legal, medical, financial, or emergency advice.
- If the message sounds like a life-threatening emergency, set urgency to emergency and next_question to null.
- Ask at most one short follow-up question in next_question (under 160 characters).
- If the message is complete enough, set next_question to null.
- summary: one or two plain sentences for the business owner (no marketing fluff).
- confidence: 0.0 to 1.0 for how clear the request is."""

FALLBACK_NEXT_QUESTION = "Can you share a little more detail about what you need help with?"


def _fallback_analysis(customer_message: str) -> LeadAIAnalysis:
    trimmed = customer_message.strip()
    summary = trimmed[:500] if trimmed else "Inbound SMS"
    return LeadAIAnalysis(
        service_needed=None,
        urgency="unknown",
        location=None,
        customer_name=None,
        summary=summary,
        lead_temperature="warm",
        next_question=FALLBACK_NEXT_QUESTION,
        confidence=0.0,
    )


def _build_user_prompt(
    *,
    business_name: str,
    business_industry: str | None,
    customer_message: str,
    existing_lead_context: dict[str, Any] | None,
) -> str:
    parts = [
        f"Business name: {business_name}",
        f"Industry: {business_industry or 'local services'}",
        f"Customer SMS: {customer_message.strip()}",
    ]
    if existing_lead_context:
        ctx = {k: v for k, v in existing_lead_context.items() if v is not None and v != ""}
        if ctx:
            parts.append(f"Existing lead context (JSON): {json.dumps(ctx, default=str)}")
    return "\n".join(parts)


def _call_openai(
    *,
    business_name: str,
    business_industry: str | None,
    customer_message: str,
    existing_lead_context: dict[str, Any] | None,
) -> LeadAIAnalysis | None:
    settings = get_settings()
    if not settings.openai_api_key:
        return None

    try:
        from openai import OpenAI
    except ImportError:
        logger.warning("openai package not installed")
        return None

    client = OpenAI(api_key=settings.openai_api_key, timeout=settings.openai_timeout_seconds)
    user_prompt = _build_user_prompt(
        business_name=business_name,
        business_industry=business_industry,
        customer_message=customer_message,
        existing_lead_context=existing_lead_context,
    )

    try:
        completion = client.chat.completions.parse(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format=LeadAIAnalysis,
        )
    except Exception:
        logger.exception("OpenAI chat completion failed")
        return None

    message = completion.choices[0].message
    parsed = getattr(message, "parsed", None)
    if parsed is not None:
        return parsed

    raw = message.content
    if raw:
        try:
            return LeadAIAnalysis.model_validate_json(raw)
        except Exception:
            logger.warning("Failed to parse OpenAI JSON content")
    return None


def analyze_inbound_sms_for_lead(
    *,
    business_name: str,
    business_industry: str | None,
    customer_message: str,
    existing_lead_context: dict[str, Any] | None = None,
) -> LeadAIAnalysis:
    """
    Classify inbound SMS for lead intake. Never raises; returns fallback when disabled or on error.
    """
    settings = get_settings()
    if not settings.openai_enabled or not settings.openai_api_key:
        return _fallback_analysis(customer_message)

    try:
        result = _call_openai(
            business_name=business_name,
            business_industry=business_industry,
            customer_message=customer_message,
            existing_lead_context=existing_lead_context,
        )
        if result is not None:
            return result
    except Exception:
        logger.exception("analyze_inbound_sms_for_lead failed")

    return _fallback_analysis(customer_message)
