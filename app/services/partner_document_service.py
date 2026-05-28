"""Partner document templates and e-sign capture."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.partner_document_template import PartnerDocumentTemplate
from app.models.partner_signed_document import ELECTRONIC_CONSENT_TEXT, PartnerSignedDocument

DEFAULT_DOCUMENT_SPECS: tuple[tuple[str, str, str], ...] = (
    (
        "independent_contractor_agreement",
        "Independent Contractor Agreement",
        (
            "DRAFT PLACEHOLDER — NOT LEGAL ADVICE.\n\n"
            "This Independent Contractor Agreement placeholder must be reviewed and replaced "
            "by qualified legal counsel before use with real independent contractors.\n\n"
            "LeadCare AI engages partners as non-employee sales contractors. Partners may refer "
            "paying business customers only. Partners do not earn commissions for recruiting other partners."
        ),
    ),
    (
        "partner_program_terms",
        "Partner Program Terms",
        (
            "DRAFT PLACEHOLDER — NOT LEGAL ADVICE.\n\n"
            "These Partner Program Terms are a draft placeholder. Do not rely on this text for "
            "production partner relationships until reviewed by legal counsel.\n\n"
            "Partners must comply with applicable laws, represent LeadCare AI accurately, and "
            "must not operate multi-level or downline compensation structures."
        ),
    ),
    (
        "commission_schedule_acknowledgment",
        "Commission Schedule Acknowledgment",
        (
            "DRAFT PLACEHOLDER — NOT LEGAL ADVICE.\n\n"
            "This acknowledgment confirms the partner understands that commissions apply only "
            "to real paying business customers referred by the partner, not to partner recruitment. "
            "Payout timing and amounts will be defined in a future commission schedule after legal review.\n\n"
            "No automated payouts are provided in V1."
        ),
    ),
)


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


def seed_default_document_templates(db: Session) -> list[PartnerDocumentTemplate]:
    """Create or refresh default active partner document templates (idempotent by code)."""
    results: list[PartnerDocumentTemplate] = []
    for code, title, body in DEFAULT_DOCUMENT_SPECS:
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
        else:
            existing.title = title
            existing.body = body
            existing.is_active = True
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
