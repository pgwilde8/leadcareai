"""Application settings loaded from environment / `.env`."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "LeadCare AI"
    app_env: str = "development"
    app_debug: bool = True
    app_base_url: str = "http://localhost:8788"
    secret_key: str = "change-me"
    database_url: str = "sqlite:///./leadcareai-dev.db"
    redis_url: str = "redis://localhost:6379/0"
    admin_email: str = "admin@example.com"
    admin_password: str = "change-me"
    default_support_email: str = "support@leadcareai.com"

    public_base_url: str | None = None

    email_provider: str = "smtp"
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str = "no-reply@leadcareai.com"

    twilio_account_sid: str | None = None
    twilio_auth_token: str | None = None
    twilio_phone_number: str | None = None
    twilio_messaging_service_sid: str | None = None
    twilio_webhook_auth_enabled: bool = False

    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    stripe_price_id_growth_monthly: str | None = None
    stripe_price_id_setup_fee: str | None = None
    stripe_setup_amount_cents: int = 19900

    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_enabled: bool = True
    openai_timeout_seconds: float = 20.0
    demo_enabled: bool = False
    demo_business_id: str | None = None
    demo_twilio_number: str | None = None
    partner_tax_encryption_key: str | None = None

    @property
    def effective_public_base_url(self) -> str | None:
        """Public URL for links in notifications (PUBLIC_BASE_URL or APP_BASE_URL)."""
        raw = (self.public_base_url or self.app_base_url or "").strip()
        return raw.rstrip("/") if raw else None


@lru_cache
def get_settings() -> Settings:
    return Settings()
