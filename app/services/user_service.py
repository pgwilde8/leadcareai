"""User creation and lookup helpers (no auth/session logic)."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import User


def _normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not normalized:
        raise ValueError("Email must not be empty")
    return normalized


def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == _normalize_email(email)).one_or_none()


def create_user(
    db: Session,
    email: str,
    password: str,
    full_name: str | None = None,
    role: str = "business_user",
) -> User:
    normalized_email = _normalize_email(email)
    if get_user_by_email(db, normalized_email) is not None:
        raise ValueError(f"User with email {normalized_email!r} already exists")

    user = User(
        email=normalized_email,
        hashed_password=hash_password(password),
        full_name=full_name,
        role=role,
    )
    db.add(user)
    db.flush()
    return user


def create_admin_user(
    db: Session,
    email: str,
    password: str,
    full_name: str | None = None,
) -> User:
    return create_user(
        db,
        email=email,
        password=password,
        full_name=full_name,
        role="admin",
    )


def get_user_by_id(db: Session, user_id) -> User | None:
    return db.get(User, user_id)


def link_existing_user_as_partner(
    db: Session,
    *,
    user: User,
    display_name: str,
) -> User:
    """Link an existing account to a partner login (no password change)."""
    if user.role == "admin":
        raise ValueError("Cannot link partner login: email belongs to an admin account")
    if user.role not in {"partner", "business_user"}:
        raise ValueError(f"Cannot link partner login: unsupported role {user.role!r}")

    user.role = "partner"
    user.is_active = True
    if not user.full_name:
        user.full_name = display_name
    db.flush()
    return user
