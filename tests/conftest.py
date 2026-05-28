"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app import models  # noqa: F401
from app.services.twilio_service import SendSmsResult


@pytest.fixture(autouse=True)
def mock_stripe_checkout(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch):
    """Prevent tests from calling the real Stripe API unless explicitly allowed."""
    if request.node.get_closest_marker("allow_real_stripe"):
        yield None
        return
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_mock_key_for_pytest")
    monkeypatch.setenv("STRIPE_PRICE_ID_GROWTH_MONTHLY", "price_growth_test")
    monkeypatch.setenv("STRIPE_PRICE_ID_SETUP_FEE", "price_setup_test")
    from tests.settings_helpers import clear_settings_cache

    clear_settings_cache()
    yield None
    clear_settings_cache()


@pytest.fixture(autouse=True)
def openai_disabled_in_tests(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch):
    """Use AI fallback path in tests unless explicitly opted in."""
    if request.node.get_closest_marker("allow_real_openai"):
        yield None
        return
    monkeypatch.setenv("OPENAI_ENABLED", "false")
    from tests.settings_helpers import clear_settings_cache

    clear_settings_cache()
    yield None
    clear_settings_cache()


@pytest.fixture(autouse=True)
def smtp_disabled_in_tests(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch):
    """Prevent tests from sending real SMTP email unless explicitly allowed."""
    if request.node.get_closest_marker("allow_real_smtp"):
        yield None
        return
    monkeypatch.setenv("SMTP_HOST", "")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "")
    from tests.settings_helpers import clear_settings_cache

    clear_settings_cache()
    yield None
    clear_settings_cache()


@pytest.fixture(autouse=True)
def partner_tax_encryption_key(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
    """Fernet key for partner W-9 tests; isolated from repo `.env` via patched get_settings."""
    if request.node.get_closest_marker("no_partner_tax_encryption_key"):
        yield
        return
    from cryptography.fernet import Fernet

    from tests.settings_helpers import clear_settings_cache, patch_get_settings

    patch_get_settings(monkeypatch, partner_tax_encryption_key=Fernet.generate_key().decode())
    yield
    clear_settings_cache()


@pytest.fixture(autouse=True)
def mock_twilio_send_sms(request: pytest.FixtureRequest):
    """Prevent tests from calling the real Twilio REST API (uses .env credentials)."""
    if request.node.get_closest_marker("allow_real_twilio_send"):
        yield None
        return
    with patch("app.services.sms_service.send_sms") as mocked:
        mocked.return_value = SendSmsResult(sid="SM_TEST_MOCK", status="queued")
        with patch("app.services.demo_intake_service.send_sms", new=mocked):
            yield mocked


@pytest.fixture
def db_engine():
    """In-memory SQLite engine shared across threads (TestClient-safe)."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session(db_engine) -> Generator[Session, None, None]:
    """Database session for direct model/service tests."""
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)
    session = session_factory()
    try:
        yield session
        session.commit()
    finally:
        session.close()


@pytest.fixture
def client(db_engine) -> Generator[TestClient, None, None]:
    """FastAPI test client with per-request DB sessions on shared SQLite engine."""
    from app.main import app

    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=db_engine)

    def override_get_db() -> Generator[Session, None, None]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
