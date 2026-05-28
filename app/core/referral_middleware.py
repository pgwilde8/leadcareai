"""Capture ?ref= partner referral codes into the session (validated later per request)."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware

from app.services.referral_service import REFERRAL_CODE_SESSION_KEY


class ReferralCaptureMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        ref = request.query_params.get("ref")
        if ref and ref.strip():
            request.session[REFERRAL_CODE_SESSION_KEY] = ref.strip().upper()
        return await call_next(request)
