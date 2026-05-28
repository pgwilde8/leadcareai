"""Structured lead qualification output from OpenAI."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

UrgencyLevel = Literal["low", "normal", "urgent", "emergency", "unknown"]
TemperatureLevel = Literal["cold", "warm", "hot", "unknown"]

NEXT_QUESTION_MAX_LEN = 160


class LeadAIAnalysis(BaseModel):
    service_needed: str | None = None
    urgency: UrgencyLevel = "unknown"
    location: str | None = None
    customer_name: str | None = None
    summary: str = ""
    lead_temperature: TemperatureLevel = "unknown"
    next_question: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    def capped_next_question(self) -> str | None:
        if not self.next_question:
            return None
        q = self.next_question.strip()
        if not q:
            return None
        if len(q) > NEXT_QUESTION_MAX_LEN:
            return q[: NEXT_QUESTION_MAX_LEN - 3].rstrip() + "..."
        return q
