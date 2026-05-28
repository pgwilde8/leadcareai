#!/usr/bin/env python3
"""Seed demo business and LeadCare Twilio number (+18336691335). Safe to rerun."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.database import get_session_local
from app.models.business import Business
from app.services.business_service import create_business
from app.services.phone_number_service import create_or_update_phone_number

DEMO_BUSINESS_NAME = "LeadCare AI Demo"
DEMO_PHONE_E164 = "+18336691335"
DEMO_PHONE_LABEL = "LeadCare Twilio SMS"


def _get_or_create_demo_business(db) -> Business:
    existing = (
        db.query(Business).filter(Business.name == DEMO_BUSINESS_NAME).one_or_none()
    )
    if existing is not None:
        return existing
    return create_business(db, name=DEMO_BUSINESS_NAME, industry="Demo")


def main() -> int:
    db = get_session_local()()
    try:
        business = _get_or_create_demo_business(db)
        phone = create_or_update_phone_number(
            db,
            business.id,
            DEMO_PHONE_E164,
            label=DEMO_PHONE_LABEL,
            provider="twilio",
            status="active",
        )
        db.commit()
        print(f"Business: {business.name} ({business.id})")
        print(f"Phone: {phone.phone_number} status={phone.status} provider={phone.provider}")
        return 0
    except Exception as exc:
        db.rollback()
        print(f"Seed failed: {exc}", file=sys.stderr)
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
