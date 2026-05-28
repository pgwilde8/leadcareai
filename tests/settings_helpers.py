"""Test helpers for isolating app settings from repo `.env`."""

from __future__ import annotations

from typing import Any

import pytest

from app.core.config import Settings


def build_test_settings(**overrides: Any) -> Settings:
    """Instantiate Settings without loading `.env` (environment vars still apply unless overridden)."""
    return Settings(_env_file=None, **overrides)


def patch_get_settings(monkeypatch: pytest.MonkeyPatch, **overrides: Any) -> Settings:
    """
    Replace cached get_settings() for config and field_encryption.

    Explicit kwargs override environment variables and ignore `.env`.
    """
    import app.core.config as config_module
    import app.core.field_encryption as field_encryption

    settings = build_test_settings(**overrides)
    clear_settings_cache()

    def _get_settings() -> Settings:
        return settings

    monkeypatch.setattr(config_module, "get_settings", _get_settings)
    monkeypatch.setattr(field_encryption, "get_settings", _get_settings)
    import app.services.system_check_service as system_check_service

    monkeypatch.setattr(system_check_service.config, "get_settings", _get_settings)
    return settings


def clear_settings_cache() -> None:
    """Clear lru_cache on get_settings when it has not been replaced by a test patch."""
    import app.core.config as config_module

    getter = config_module.get_settings
    if hasattr(getter, "cache_clear"):
        getter.cache_clear()
