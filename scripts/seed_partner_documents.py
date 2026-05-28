#!/usr/bin/env python3
"""Seed default partner document templates. Safe to rerun."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.database import get_session_local
from app.services.partner_document_service import seed_default_document_templates


def main() -> int:
    db = get_session_local()()
    try:
        templates = seed_default_document_templates(db)
        db.commit()
        print(f"Seeded {len(templates)} partner document template(s):")
        for template in templates:
            print(f"  - {template.code} (v{template.version}, active={template.is_active})")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
