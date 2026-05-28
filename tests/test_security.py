"""Tests for password hashing utilities."""

from __future__ import annotations

import pytest

from app.core.security import hash_password, verify_password


def test_hash_password_returns_non_plain_value() -> None:
    plain = "super-secret-password"
    hashed = hash_password(plain)
    assert hashed != plain
    assert hashed.startswith("$2")


def test_verify_password_works() -> None:
    plain = "another-secret"
    hashed = hash_password(plain)
    assert verify_password(plain, hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_empty_password_raises_value_error() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        hash_password("")
    with pytest.raises(ValueError, match="must not be empty"):
        hash_password("   ")
