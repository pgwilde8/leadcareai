"""Capture ?ref= partner referral codes into session and 30-day cookie."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware

from app.services.referral_service import (
    REFERRAL_CODE_SESSION_KEY,
    set_referral_cookie,
)


class ReferralCaptureMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        ref = request.query_params.get("ref")
        code: str | None = None
        if ref and ref.strip():
            code = ref.strip().upper()
            request.session[REFERRAL_CODE_SESSION_KEY] = code
        response = await call_next(request)
        if code:
            set_referral_cookie(response, code)
        return response
