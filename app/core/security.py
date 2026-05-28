"""Password hashing utilities (framework-independent)."""

from __future__ import annotations

from passlib.context import CryptContext

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """Return a bcrypt hash for *password*. Never store the plain value."""
    if not password or not password.strip():
        raise ValueError("Password must not be empty")
    return _pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return True if *plain_password* matches *hashed_password*."""
    if not plain_password or not hashed_password:
        return False
    return _pwd_context.verify(plain_password, hashed_password)
