"""Unit tests for system_check_service helpers."""

from __future__ import annotations

from app.services.system_check_service import (
    mask_database_url,
    mask_configured_suffix,
    stripe_key_mode,
)


def test_mask_database_url_redacts_credentials() -> None:
    masked = mask_database_url("postgresql+psycopg://user:secretpass@db.example.com:5432/leadcareai")
    assert "secretpass" not in masked
    assert "***" in masked
    assert "db.example.com" in masked


def test_mask_configured_suffix_shows_last_four_only() -> None:
    display, status = mask_configured_suffix("abcdefghijklmnop")
    assert status == "ok"
    assert "mnop" in display
    assert "abcdefghijklmnop" not in display


def test_stripe_key_mode_test_and_live() -> None:
    assert stripe_key_mode("sk_test_abc")[0].lower().find("test") >= 0
    assert stripe_key_mode("sk_live_xyz")[0].lower().find("live") >= 0
    assert stripe_key_mode(None)[1] == "error"
