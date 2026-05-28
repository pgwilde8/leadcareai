"""Plain-text copies of signed partner documents and post-signing email delivery."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from app.core.config import get_settings
from app.models.partner_application import PartnerApplication
from app.models.partner_signed_document import PartnerSignedDocument
from app.services.email_service import EmailAttachment, EmailSendResult, send_email

logger = logging.getLogger(__name__)

_PARTNER_SUBJECT = "Your signed LeadCareAI partner documents"
_PARTNER_BODY = """Thanks for signing your LeadCareAI partner documents.

Attached are copies of the documents you signed. Please keep them for your records.

LeadCareAI will review your application and notify you about next steps."""


def format_signed_document_copy_text(document: PartnerSignedDocument) -> str:
    """Build a plain-text record for one signed document row."""
    signed_at = document.signed_at
    if isinstance(signed_at, datetime):
        signed_at_display = signed_at.isoformat()
    else:
        signed_at_display = str(signed_at)

    return (
        "LeadCareAI Signed Partner Document\n\n"
        f"Document title: {document.document_title}\n"
        f"Document code: {document.document_code}\n"
        f"Signed by: {document.signer_name}\n"
        f"Signer email: {document.signer_email}\n"
        f"Typed signature: {document.signature_text}\n"
        f"Signed at: {signed_at_display}\n"
        f"IP address: {document.ip_address or '—'}\n"
        f"User agent: {document.user_agent or '—'}\n\n"
        "------------------------------------------------------------\n\n"
        f"{document.document_snapshot}"
    )


def signed_document_attachment_filename(document_code: str) -> str:
    safe_code = document_code.strip().replace("/", "-")
    return f"{safe_code}-signed.txt"


def build_signed_document_attachments(
    documents: list[PartnerSignedDocument],
) -> list[EmailAttachment]:
    return [
        EmailAttachment(
            filename=signed_document_attachment_filename(doc.document_code),
            content=format_signed_document_copy_text(doc),
        )
        for doc in documents
    ]


def build_signed_documents_inline_body(documents: list[PartnerSignedDocument]) -> str:
    parts = [format_signed_document_copy_text(doc) for doc in documents]
    return "\n\n" + ("=" * 60 + "\n\n").join(parts)


def resolve_partner_docs_admin_email() -> str | None:
    """Legal/admin inbox: DEFAULT_SUPPORT_EMAIL, else ADMIN_EMAIL."""
    settings = get_settings()
    for candidate in (settings.default_support_email, settings.admin_email):
        email = (candidate or "").strip()
        if email:
            return email
    return None


def applicant_display_name(application: PartnerApplication) -> str:
    return f"{application.first_name} {application.last_name}".strip()


def _admin_detail_url(application_id: uuid.UUID) -> str | None:
    base = get_settings().effective_public_base_url
    if not base:
        return None
    return f"{base}/admin/partners/{application_id}"


def _representative_signed_at(documents: list[PartnerSignedDocument]) -> str:
    if not documents:
        return "—"
    signed_at = documents[0].signed_at
    if isinstance(signed_at, datetime):
        return signed_at.isoformat()
    return str(signed_at)


def _send_copy_email(
    *,
    to_email: str,
    subject: str,
    body: str,
    attachments: list[EmailAttachment],
    context: str,
) -> EmailSendResult:
    try:
        result = send_email(
            to_email=to_email,
            subject=subject,
            body=body,
            attachments=attachments,
        )
        if result.status == "failed":
            logger.error(
                "Signed partner document email failed (%s): to=%s error=%s",
                context,
                to_email,
                result.error,
            )
        elif result.status == "skipped":
            logger.info(
                "Signed partner document email skipped (%s): to=%s reason=%s",
                context,
                to_email,
                result.error,
            )
        return result
    except Exception:
        logger.exception(
            "Signed partner document email raised (%s): to=%s",
            context,
            to_email,
        )
        return EmailSendResult(status="failed", error="unexpected error")


def send_signed_document_copy_emails(
    *,
    application: PartnerApplication,
    signed_documents: list[PartnerSignedDocument],
) -> None:
    """
    Email signed document copies to the applicant and admin/legal inbox.

    Never raises; signing persistence must not depend on delivery.
    """
    if not signed_documents:
        return

    attachments = build_signed_document_attachments(signed_documents)
    applicant_email = (application.email or "").strip()
    if applicant_email:
        _send_copy_email(
            to_email=applicant_email,
            subject=_PARTNER_SUBJECT,
            body=_PARTNER_BODY,
            attachments=attachments,
            context="partner",
        )
    else:
        logger.warning(
            "Skipping partner signed-document email: application %s has no email",
            application.id,
        )

    admin_email = resolve_partner_docs_admin_email()
    if not admin_email:
        logger.warning(
            "Skipping admin signed-document email: no DEFAULT_SUPPORT_EMAIL or ADMIN_EMAIL",
        )
        return

    name = applicant_display_name(application)
    detail_url = _admin_detail_url(application.id)
    admin_lines = [
        f"Applicant: {name}",
        f"Applicant email: {applicant_email or '—'}",
        f"Application ID: {application.id}",
        f"Signed at: {_representative_signed_at(signed_documents)}",
    ]
    if detail_url:
        admin_lines.append(f"Admin review: {detail_url}")
    admin_body = "\n".join(admin_lines) + "\n\nAttached are plain-text copies of the signed documents."

    _send_copy_email(
        to_email=admin_email,
        subject=f"Partner documents signed: {name}",
        body=admin_body,
        attachments=attachments,
        context="admin",
    )
