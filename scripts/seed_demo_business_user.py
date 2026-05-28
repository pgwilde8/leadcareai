#!/usr/bin/env python3
"""Create or reuse a demo business user for LeadCare AI Demo. Safe to rerun."""

from __future__ import annotations

import secrets
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.database import get_session_local
from app.models.business import Business
from app.models.business_user import BusinessUser
from app.services.business_service import get_primary_business_for_user, link_user_to_business
from app.services.user_service import create_user, get_user_by_email

DEMO_BUSINESS_NAME = "LeadCare AI Demo"
DEMO_USER_EMAIL = "demo@leadcareai.com"
DEMO_USER_NAME = "Demo Business User"


def _get_demo_business(db) -> Business | None:
    return db.query(Business).filter(Business.name == DEMO_BUSINESS_NAME).one_or_none()


def main() -> int:
    db = get_session_local()()
    try:
        business = _get_demo_business(db)
        if business is None:
            print(
                f"No business named {DEMO_BUSINESS_NAME!r}. "
                "Run scripts/seed_demo_twilio_number.py first.",
                file=sys.stderr,
            )
            return 1

        user = get_user_by_email(db, DEMO_USER_EMAIL)
        created_password: str | None = None
        if user is None:
            created_password = secrets.token_urlsafe(12)
            user = create_user(
                db,
                email=DEMO_USER_EMAIL,
                password=created_password,
                full_name=DEMO_USER_NAME,
                role="business_user",
            )
            print(f"Created user: {user.email}")
        else:
            if user.role != "business_user":
                user.role = "business_user"
                user.is_active = True
            print(f"Reusing user: {user.email}")

        existing_link = (
            db.query(BusinessUser)
            .filter(
                BusinessUser.business_id == business.id,
                BusinessUser.user_id == user.id,
            )
            .one_or_none()
        )
        if existing_link is None:
            link_user_to_business(db, user.id, business.id, role="owner")
            print(f"Linked user to business: {business.name}")

        db.commit()

        if get_primary_business_for_user(db, user.id) is None:
            print("Warning: user has no business after seed.", file=sys.stderr)
            return 1

        print(f"Business: {business.name} ({business.id})")
        print(f"Login: {DEMO_USER_EMAIL}")
        print("Dashboard: /business/dashboard")
        if created_password:
            print(f"Temporary password (save now): {created_password}")
        else:
            print("Password unchanged (existing user).")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"Seed failed: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
