#!/usr/bin/env python3
"""Create the platform admin user from ADMIN_EMAIL / ADMIN_PASSWORD settings."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import get_settings
from app.core.database import get_session_local
from app.services.user_service import create_admin_user, get_user_by_email


def main() -> int:
    settings = get_settings()

    if not settings.admin_email.strip():
        print("ADMIN_EMAIL is not set.", file=sys.stderr)
        return 1
    if not settings.admin_password.strip():
        print("ADMIN_PASSWORD is not set.", file=sys.stderr)
        return 1

    db = get_session_local()()
    try:
        existing = get_user_by_email(db, settings.admin_email)
        if existing is not None:
            print(f"Admin user already exists: {existing.email}")
            return 0

        user = create_admin_user(
            db,
            email=settings.admin_email,
            password=settings.admin_password,
        )
        db.commit()
        print(f"Admin user created: {user.email}")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"Seed failed: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
