"""FastAPI application entrypoint."""

from __future__ import annotations

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import get_settings
from app.core.referral_middleware import ReferralCaptureMiddleware
from app.routers import (
    admin,
    auth,
    business_dashboard,
    partner_dashboard,
    partner_onboard,
    public,
    webhooks_stripe,
    webhooks_twilio,
)

settings = get_settings()

app = FastAPI(title=settings.app_name, debug=settings.app_debug)

app.include_router(auth.router)
app.include_router(public.router)
app.include_router(partner_onboard.router)
app.include_router(partner_dashboard.router)
app.include_router(business_dashboard.router)
app.include_router(admin.router)
app.include_router(webhooks_twilio.router)
app.include_router(webhooks_stripe.router)

app.add_middleware(ReferralCaptureMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    session_cookie="leadcareai_session",
    same_site="lax",
    https_only=settings.app_env.lower() in {"production", "prod"},
)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "app": settings.app_name,
        "env": settings.app_env,
    }
