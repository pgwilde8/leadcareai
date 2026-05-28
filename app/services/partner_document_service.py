"""Partner document templates and e-sign capture."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.partner_document_template import PartnerDocumentTemplate
from app.models.partner_signed_document import ELECTRONIC_CONSENT_TEXT, PartnerSignedDocument

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DOCUMENTS_DIR = PROJECT_ROOT / "app" / "templates" / "partner" / "documents"

LEGAL_REVIEW_BANNER = (
    "DRAFT PLACEHOLDER — NOT LEGAL ADVICE. Must be reviewed by legal counsel before production use."
)

DOCUMENT_CATALOG: dict[str, str] = {
    "independent_contractor_agreement": "Independent Contractor Agreement",
    "commission_schedule_acknowledgment": "Commission Schedule Acknowledgment",
    "acceptable_marketing_policy": "Acceptable Marketing Policy",
    "privacy_data_handling": "Privacy / Data Handling",
    "electronic_signature_notice": "Electronic Signature and Records Notice",
}

LEGACY_INACTIVE_CODES = frozenset({"partner_program_terms"})


def load_document_body(code: str) -> str:
    """Load markdown body for a document code from app/templates/partner/documents/{code}.md."""
    if code not in DOCUMENT_CATALOG:
        raise ValueError(f"Unknown partner document code: {code!r}")
    path = DOCUMENTS_DIR / f"{code}.md"
    if not path.is_file():
        raise FileNotFoundError(f"Partner document file not found: {path}")
    body = path.read_text(encoding="utf-8").strip()
    if LEGAL_REVIEW_BANNER not in body:
        body = f"{LEGAL_REVIEW_BANNER}\n\n---\n\n{body}"
    return body


def list_active_document_templates(db: Session) -> list[PartnerDocumentTemplate]:
    return (
        db.query(PartnerDocumentTemplate)
        .filter(PartnerDocumentTemplate.is_active.is_(True))
        .order_by(PartnerDocumentTemplate.code)
        .all()
    )


def get_document_template_by_code(db: Session, code: str) -> PartnerDocumentTemplate | None:
    return (
        db.query(PartnerDocumentTemplate)
        .filter(PartnerDocumentTemplate.code == code)
        .one_or_none()
    )


def template_has_signed_documents(db: Session, template_id) -> bool:
    return (
        db.query(PartnerSignedDocument.id)
        .filter(PartnerSignedDocument.document_template_id == template_id)
        .limit(1)
        .first()
        is not None
    )


def _bump_version(version: str) -> str:
    parts = version.strip().split(".")
    try:
        major = int(parts[0])
        minor = int(parts[1]) if len(parts) > 1 else 0
    except (ValueError, IndexError):
        return "1.1"
    return f"{major}.{minor + 1}"


def _deactivate_legacy_templates(db: Session) -> None:
    for code in LEGACY_INACTIVE_CODES:
        existing = get_document_template_by_code(db, code)
        if existing is not None:
            existing.is_active = False


def seed_default_document_templates(db: Session) -> list[PartnerDocumentTemplate]:
    """
    Create or refresh active partner document templates from markdown files.

    Does not overwrite template body when signed documents already reference the template
    (preserves snapshots for existing applicants).
    """
    _deactivate_legacy_templates(db)
    results: list[PartnerDocumentTemplate] = []
    for code, title in DOCUMENT_CATALOG.items():
        body = load_document_body(code)
        existing = get_document_template_by_code(db, code)
        if existing is None:
            template = PartnerDocumentTemplate(
                code=code,
                title=title,
                body=body,
                version="1.0",
                is_active=True,
            )
            db.add(template)
            db.flush()
            results.append(template)
            continue

        existing.title = title
        existing.is_active = True
        if not template_has_signed_documents(db, existing.id):
            if existing.body != body:
                existing.body = body
                existing.version = _bump_version(existing.version)
        results.append(existing)
    return results


def sign_documents_for_application(
    db: Session,
    *,
    application_id,
    templates: list[PartnerDocumentTemplate],
    signer_name: str,
    signer_email: str,
    signature_text: str,
    ip_address: str | None,
    user_agent: str | None,
) -> list[PartnerSignedDocument]:
    if not signature_text.strip():
        raise ValueError("Typed signature is required")
    if not signer_name.strip():
        raise ValueError("Signer name is required")

    signed_at = datetime.now(timezone.utc)
    records: list[PartnerSignedDocument] = []
    for template in templates:
        record = PartnerSignedDocument(
            application_id=application_id,
            document_template_id=template.id,
            document_code=template.code,
            document_title=template.title,
            document_version=template.version,
            signer_name=signer_name.strip(),
            signer_email=signer_email.strip().lower(),
            signed_at=signed_at,
            ip_address=ip_address,
            user_agent=user_agent,
            consent_text=ELECTRONIC_CONSENT_TEXT,
            signature_text=signature_text.strip(),
            document_snapshot=template.body,
        )
        db.add(record)
        records.append(record)
    db.flush()
    return records
