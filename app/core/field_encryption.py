"""Fernet encryption for sensitive partner tax fields (TIN/SSN/EIN)."""

from __future__ import annotations

import logging
import re

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_NON_DIGIT = re.compile(r"\D+")


def _fernet() -> Fernet:
    settings = get_settings()
    raw = (settings.partner_tax_encryption_key or "").strip()
    if not raw:
        if settings.app_env.lower() == "production":
            raise ValueError(
                "PARTNER_TAX_ENCRYPTION_KEY is required in production for partner tax information."
            )
        raise ValueError(
            "PARTNER_TAX_ENCRYPTION_KEY is not configured. Set it in the environment before collecting W-9 data."
        )
    return Fernet(raw.encode("utf-8") if isinstance(raw, str) else raw)


def encrypt_field(value: str) -> str:
    """Encrypt a string value; returns URL-safe token string for DB storage."""
    plaintext = value.strip()
    if not plaintext:
        raise ValueError("Cannot encrypt empty value")
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_field(encrypted: str) -> str:
    """Decrypt a value previously stored with encrypt_field."""
    try:
        return _fernet().decrypt(encrypted.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        logger.error("Field decryption failed (invalid token)")
        raise ValueError("Unable to decrypt stored tax information") from exc


def mask_tin(tin_type: str, tin_digits: str) -> str:
    """Mask TIN for display. tin_digits must be 9 numeric digits only."""
    digits = _NON_DIGIT.sub("", tin_digits)
    if len(digits) != 9:
        return "***-**-****"
    tin = tin_type.strip().lower()
    if tin == "ein":
        return f"**-***{digits[-4:]}"
    return f"***-**-{digits[-4:]}"
