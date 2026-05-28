"""Shared partner onboarding form payloads for tests."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.services import partner_document_service, partner_service, partner_tax_service


def partner_onboard_form_data(**overrides: str) -> dict[str, str]:
    """Minimal valid partner apply POST (application fields only, no tax)."""
    data = {
        "first_name": "Pat",
        "last_name": "Ner",
        "email": "pat.ner@example.com",
        "phone": "+15551230001",
        "city": "Austin",
        "state": "TX",
        "company_name": "",
        "experience_summary": "",
        "why_interested": "",
    }
    data.update(overrides)
    return data


def partner_tax_info_form_data(**overrides: str) -> dict[str, str]:
    """Valid W-9 POST for /partner/tax-info."""
    data = {
        "tax_legal_name": "Pat Ner",
        "tax_business_name": "",
        "tax_address_line1": "100 Main St",
        "tax_address_line2": "",
        "tax_city": "Austin",
        "tax_state": "TX",
        "tax_postal_code": "78701",
        "tax_classification": "individual",
        "tax_tin_type": "ssn",
        "tax_tin": "123456789",
        "tax_certification": "on",
    }
    data.update(overrides)
    if overrides.get("first_name") and overrides.get("last_name"):
        name = f"{overrides['first_name']} {overrides['last_name']}"
        if "tax_legal_name" not in overrides:
            data["tax_legal_name"] = name
    return data


def partner_sign_documents_form_data(**overrides: str) -> dict[str, str]:
    """Valid IC document signing POST."""
    data = {
        "signature_text": "Pat Ner",
        "electronic_consent": "on",
    }
    data.update(overrides)
    return data


def ensure_partner_application_docs_signed(
    db: Session,
    application_id: uuid.UUID,
    *,
    signature_text: str = "Pat Ner",
) -> str | None:
    """Move application to docs_signed; return tax-info token when W-9 still pending."""
    application = partner_service.get_application(db, application_id)
    if application.status == partner_service.APPLICATION_STATUS_DOCS_SIGNED:
        if partner_tax_service.get_partner_tax_info_for_application(db, application_id):
            return None
        raw, _ = partner_service.issue_tax_info_token(db, application_id)
        db.flush()
        return raw

    partner_document_service.seed_default_document_templates(db)
    documents = partner_document_service.list_active_document_templates(db)
    if application.status != partner_service.APPLICATION_STATUS_DOCS_PENDING:
        partner_service.issue_docs_signing_invite(db, application_id)

    signer_name = f"{application.first_name} {application.last_name}"
    partner_document_service.sign_documents_for_application(
        db,
        application_id=application_id,
        templates=documents,
        signer_name=signer_name,
        signer_email=application.email,
        signature_text=signature_text,
        ip_address="127.0.0.1",
        user_agent="test",
    )
    _, tax_token = partner_service.mark_application_docs_signed(db, application_id)
    db.flush()
    return tax_token


def ensure_partner_application_tax_info(
    db: Session,
    application_id: uuid.UUID,
    **tax_overrides: str,
) -> None:
    """Create encrypted W-9 record for an application (test helper)."""
    if partner_tax_service.get_partner_tax_info_for_application(db, application_id) is not None:
        return

    form = partner_tax_info_form_data(**tax_overrides)
    data = partner_tax_service.validate_partner_tax_info(
        legal_name=form["tax_legal_name"],
        business_name=form.get("tax_business_name") or None,
        address_line1=form["tax_address_line1"],
        address_line2=form.get("tax_address_line2") or None,
        city=form["tax_city"],
        state=form["tax_state"],
        postal_code=form["tax_postal_code"],
        tax_classification=form["tax_classification"],
        tin_type=form["tax_tin_type"],
        tin=form["tax_tin"],
        tax_certified=True,
    )
    partner_tax_service.create_partner_tax_info_for_application(
        db,
        application_id=application_id,
        data=data,
    )
    partner_service.clear_tax_info_token(db, application_id)
    db.flush()
