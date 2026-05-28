"""Twilio webhook helpers (no outbound API calls)."""

from __future__ import annotations

import base64
import hmac
from hashlib import sha1


def compute_twilio_signature(url: str, params: dict[str, str], auth_token: str) -> str:
    """Compute expected X-Twilio-Signature for form POST validation."""
    data = url
    for key in sorted(params):
        data += key + params[key]
    digest = hmac.new(auth_token.encode("utf-8"), data.encode("utf-8"), sha1).digest()
    return base64.b64encode(digest).decode("utf-8")


def validate_twilio_signature(
    url: str,
    params: dict[str, str],
    signature: str,
    auth_token: str,
) -> bool:
    if not signature or not auth_token:
        return False
    expected = compute_twilio_signature(url, params, auth_token)
    return hmac.compare_digest(expected, signature)
