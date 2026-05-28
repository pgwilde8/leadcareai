"""Tests for user creation service."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.core.security import verify_password
from app.services.user_service import create_admin_user, create_user, get_user_by_email


def test_create_user_stores_lowercase_email(db_session: Session) -> None:
    user = create_user(db_session, email="  Owner@Example.COM  ", password="secret123")
    assert user.email == "owner@example.com"
    assert get_user_by_email(db_session, "OWNER@example.com") is user


def test_create_user_hashes_password(db_session: Session) -> None:
    user = create_user(db_session, email="hash@example.com", password="plain-text-pass")
    assert user.hashed_password != "plain-text-pass"
    assert verify_password("plain-text-pass", user.hashed_password) is True


def test_duplicate_email_raises_clear_error(db_session: Session) -> None:
    create_user(db_session, email="dup@example.com", password="secret123")
    with pytest.raises(ValueError, match="already exists"):
        create_user(db_session, email="DUP@example.com", password="other-secret")


def test_create_admin_user_sets_admin_role(db_session: Session) -> None:
    user = create_admin_user(db_session, email="admin@example.com", password="admin-pass")
    assert user.role == "admin"
