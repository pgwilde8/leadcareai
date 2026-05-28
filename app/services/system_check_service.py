"""Production readiness checks for admin system-check page (no secret values)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from sqlalchemy import text
from sqlalchemy.engine import Engine, create_engine
from sqlalchemy.orm import Session

from app.core import config
from app.core.config import Settings

_DB_URL_RE = re.compile(r"://([^:]+):([^@]+)@")


@dataclass(frozen=True)
class SystemCheckItem:
    name: str
    value: str
    status: str = "info"  # ok | warn | error | info


@dataclass(frozen=True)
class SystemCheckSection:
    title: str
    items: list[SystemCheckItem] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def mask_database_url(database_url: str) -> str:
    """Return a connection string with credentials redacted."""
    raw = (database_url or "").strip()
    if not raw:
        return "not configured"
    return _DB_URL_RE.sub("://***:***@", raw, count=1)


def mask_configured_suffix(value: str | None) -> tuple[str, str]:
    """Return (display, status) for a secret — never the full value."""
    raw = (value or "").strip()
    if not raw:
        return "not configured", "error"
    if len(raw) <= 4:
        return "configured", "ok"
    return f"configured (…{raw[-4:]})", "ok"


def stripe_key_mode(secret_key: str | None) -> tuple[str, str]:
    raw = (secret_key or "").strip()
    if not raw:
        return "not configured", "error"
    if raw.startswith("sk_live"):
        return "configured — live mode", "ok"
    if raw.startswith("sk_test"):
        return "configured — test mode", "warn"
    suffix = raw[-4:] if len(raw) >= 4 else ""
    return f"configured — unknown prefix (…{suffix})", "warn"


def _alembic_revision_status(database_url: str) -> tuple[str, str]:
    try:
        from alembic.config import Config
        from alembic.runtime.migration import MigrationContext
        from alembic.script import ScriptDirectory

        cfg = Config("alembic.ini")
        script = ScriptDirectory.from_config(cfg)
        head = script.get_current_head()
        engine: Engine = create_engine(database_url)
        with engine.connect() as conn:
            current = MigrationContext.configure(conn).get_current_revision()
        engine.dispose()
        if not head:
            return "unknown (no head revision)", "warn"
        if current == head:
            return f"{current} (head)", "ok"
        if current is None:
            return f"not migrated — run: alembic upgrade head (head: {head})", "error"
        return f"{current} — run: alembic upgrade head (head: {head})", "warn"
    except Exception:
        return "unavailable — run: alembic current", "warn"


def _is_production(settings: Settings) -> bool:
    return settings.app_env.strip().lower() in {"production", "prod"}


def _yes_no(label: str, value: str | None) -> SystemCheckItem:
    configured = bool((value or "").strip())
    return SystemCheckItem(
        f"{label} configured",
        "yes" if configured else "no",
        "ok" if configured else "error",
    )


def build_system_check_sections(db: Session) -> list[SystemCheckSection]:
    settings = config.get_settings()
    base = (settings.effective_public_base_url or settings.app_base_url or "").rstrip("/")
    production = _is_production(settings)

    db_reachable = "no"
    db_status = "error"
    try:
        db.execute(text("SELECT 1"))
        db_reachable = "yes"
        db_status = "ok"
    except Exception:
        pass

    alembic_value, alembic_status = _alembic_revision_status(settings.database_url)

    secret_display, secret_status = mask_configured_suffix(settings.secret_key)
    if production and (settings.secret_key or "").strip() in {"", "change-me"}:
        secret_display = "weak or default — change SECRET_KEY for production"
        secret_status = "error"

    tax_display, tax_status = mask_configured_suffix(settings.partner_tax_encryption_key)
    tax_notes: list[str] = []
    if production and not (settings.partner_tax_encryption_key or "").strip():
        tax_display = "not configured — required for partner W-9 in production"
        tax_status = "error"
        tax_notes.append("Set PARTNER_TAX_ENCRYPTION_KEY before partner onboarding with W-9.")

    stripe_mode_value, stripe_mode_status = stripe_key_mode(settings.stripe_secret_key)
    setup_fee_ok = bool((settings.stripe_price_id_setup_fee or "").strip())
    setup_display = (
        "configured"
        if setup_fee_ok
        else f"not set (fallback STRIPE_SETUP_AMOUNT_CENTS={settings.stripe_setup_amount_cents})"
    )

    openai_display, openai_status = mask_configured_suffix(settings.openai_api_key)
    if not (settings.openai_api_key or "").strip():
        openai_display = "no"
        openai_status = "error"
    else:
        openai_display = openai_display.replace("configured", "yes", 1)

    smtp_password_display, smtp_password_status = mask_configured_suffix(settings.smtp_password)

    core = SystemCheckSection(
        title="Core",
        items=[
            SystemCheckItem("APP_ENV", settings.app_env, "info"),
            SystemCheckItem(
                "APP_BASE_URL",
                settings.app_base_url or "not configured",
                "ok" if settings.app_base_url else "warn",
            ),
            SystemCheckItem(
                "PUBLIC_BASE_URL / effective public URL",
                settings.effective_public_base_url or "not configured",
                "ok" if settings.effective_public_base_url else "error",
            ),
            SystemCheckItem(
                "DATABASE_URL",
                mask_database_url(settings.database_url),
                "ok" if settings.database_url else "error",
            ),
            SystemCheckItem("Database reachable", db_reachable, db_status),
            SystemCheckItem("Alembic revision", alembic_value, alembic_status),
        ],
    )

    twilio_notes = (
        [
            f"{base}/webhooks/twilio/sms",
            f"{base}/webhooks/twilio/voice",
            f"{base}/webhooks/twilio/voice/status",
        ]
        if base
        else ["Configure PUBLIC_BASE_URL or APP_BASE_URL to show full webhook URLs."]
    )
    twilio = SystemCheckSection(
        title="Twilio",
        items=[
            _yes_no("TWILIO_ACCOUNT_SID", settings.twilio_account_sid),
            _yes_no("TWILIO_AUTH_TOKEN", settings.twilio_auth_token),
            _yes_no("TWILIO_PHONE_NUMBER", settings.twilio_phone_number),
            SystemCheckItem(
                "TWILIO_WEBHOOK_AUTH_ENABLED",
                "true" if settings.twilio_webhook_auth_enabled else "false",
                "ok" if settings.twilio_webhook_auth_enabled else ("warn" if production else "info"),
            ),
        ],
        notes=twilio_notes,
    )

    openai = SystemCheckSection(
        title="OpenAI",
        items=[
            SystemCheckItem(
                "OPENAI_ENABLED",
                "true" if settings.openai_enabled else "false",
                "info",
            ),
            SystemCheckItem("OPENAI_API_KEY configured", openai_display, openai_status),
            SystemCheckItem("OPENAI_MODEL", settings.openai_model, "ok"),
        ],
    )

    stripe = SystemCheckSection(
        title="Stripe",
        items=[
            SystemCheckItem("STRIPE_SECRET_KEY", stripe_mode_value, stripe_mode_status),
            _yes_no("STRIPE_WEBHOOK_SECRET", settings.stripe_webhook_secret),
            _yes_no("STRIPE_PRICE_ID_GROWTH_MONTHLY", settings.stripe_price_id_growth_monthly),
            SystemCheckItem(
                "STRIPE_PRICE_ID_SETUP_FEE",
                setup_display,
                "ok" if setup_fee_ok else "warn",
            ),
        ],
        notes=[f"{base}/webhooks/stripe" if base else "/webhooks/stripe (set public base URL for full URL)"],
    )

    email = SystemCheckSection(
        title="Email / SMTP",
        items=[
            _yes_no("SMTP_HOST", settings.smtp_host),
            SystemCheckItem("SMTP_PORT", str(settings.smtp_port), "info"),
            _yes_no("SMTP_USERNAME", settings.smtp_username),
            SystemCheckItem("SMTP_PASSWORD", smtp_password_display, smtp_password_status),
            _yes_no("SMTP_FROM_EMAIL", settings.smtp_from_email),
            SystemCheckItem(
                "DEFAULT_SUPPORT_EMAIL",
                settings.default_support_email or "not configured",
                "ok" if settings.default_support_email else "warn",
            ),
        ],
        notes=[
            "Configure SPF, DKIM, and DMARC for your sending domain before production launch.",
            "This page does not run live DNS checks.",
        ],
    )

    partner_tax = SystemCheckSection(
        title="Partner tax (W-9)",
        items=[SystemCheckItem("PARTNER_TAX_ENCRYPTION_KEY", tax_display, tax_status)],
        notes=tax_notes,
    )

    security = SystemCheckSection(
        title="Security / admin",
        items=[
            SystemCheckItem("SECRET_KEY", secret_display, secret_status),
            SystemCheckItem(
                "ADMIN_EMAIL configured",
                "yes" if (settings.admin_email or "").strip() else "no",
                "ok" if (settings.admin_email or "").strip() else "warn",
            ),
        ],
        notes=[
            "Launch checklist: docs/production-launch-checklist-v1.md",
            "Secrets are never displayed on this page.",
        ],
    )

    return [core, twilio, openai, stripe, email, partner_tax, security]
