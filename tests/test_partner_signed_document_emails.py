"""Signed partner document copy emails after IC signing."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.partner_application import PartnerApplication
from app.models.partner_signed_document import PartnerSignedDocument
from app.services import partner_service
from app.services.email_service import EmailSendResult
from app.services.partner_signed_document_copy_service import (
    format_signed_document_copy_text,
    send_signed_document_copy_emails,
)
from tests.partner_fixtures import partner_sign_documents_form_data


def _signed_doc(**overrides) -> PartnerSignedDocument:
    defaults = {
        "id": uuid.uuid4(),
        "application_id": uuid.uuid4(),
        "document_template_id": uuid.uuid4(),
        "document_code": "independent_contractor_agreement",
        "document_title": "Independent Contractor Agreement",
        "document_version": "1.2",
        "signer_name": "Pat Ner",
        "signer_email": "pat@example.com",
        "signed_at": datetime(2026, 5, 28, 22, 8, 5, tzinfo=timezone.utc),
        "ip_address": "127.0.0.1",
        "user_agent": "pytest",
        "consent_text": "I agree to electronic signatures.",
        "signature_text": "Pat Ner",
        "document_snapshot": "Agreement body text here.",
    }
    defaults.update(overrides)
    return PartnerSignedDocument(**defaults)


def test_format_signed_document_copy_text_includes_metadata_and_snapshot() -> None:
    doc = _signed_doc()
    text = format_signed_document_copy_text(doc)
    assert "LeadCareAI Signed Partner Document" in text
    assert "Document title: Independent Contractor Agreement" in text
    assert "Document code: independent_contractor_agreement" in text
    assert "Signed by: Pat Ner" in text
    assert "Signer email: pat@example.com" in text
    assert "Typed signature: Pat Ner" in text
    assert "Signed at: 2026-05-28T22:08:05+00:00" in text
    assert "IP address: 127.0.0.1" in text
    assert "User agent: pytest" in text
    assert "Agreement body text here." in text


def test_send_signed_document_copy_emails_uses_attachments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[dict] = []

    def fake_send_email(**kwargs):
        calls.append(kwargs)
        return EmailSendResult(status="sent")

    monkeypatch.setattr(
        "app.services.partner_signed_document_copy_service.send_email",
        fake_send_email,
    )
    monkeypatch.setattr(
        "app.services.partner_signed_document_copy_service.resolve_partner_docs_admin_email",
        lambda: "legal@example.com",
    )

    application = PartnerApplication(
        id=uuid.uuid4(),
        first_name="Pat",
        last_name="Ner",
        email="pat@example.com",
        phone="+15551230001",
        city="Austin",
        state="TX",
        status="docs_signed",
    )
    docs = [_signed_doc(), _signed_doc(document_code="acceptable_marketing_policy", document_title="Marketing")]

    send_signed_document_copy_emails(application=application, signed_documents=docs)

    assert len(calls) == 2
    assert calls[0]["to_email"] == "pat@example.com"
    assert calls[0]["subject"] == "Your signed LeadCareAI partner documents"
    assert len(calls[0]["attachments"]) == 2
    assert calls[0]["attachments"][0].filename == "independent_contractor_agreement-signed.txt"
    assert calls[1]["to_email"] == "legal@example.com"
    assert "Partner documents signed: Pat Ner" in calls[1]["subject"]
    assert "pat@example.com" in calls[1]["body"]


def test_send_skips_admin_when_no_legal_inbox(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fake_send_email(**kwargs):
        calls.append(kwargs["to_email"])
        return EmailSendResult(status="sent")

    monkeypatch.setattr(
        "app.services.partner_signed_document_copy_service.send_email",
        fake_send_email,
    )
    monkeypatch.setattr(
        "app.services.partner_signed_document_copy_service.resolve_partner_docs_admin_email",
        lambda: None,
    )

    application = PartnerApplication(
        id=uuid.uuid4(),
        first_name="Pat",
        last_name="Ner",
        email="pat@example.com",
        phone="+15551230001",
        city="Austin",
        state="TX",
        status="docs_signed",
    )
    send_signed_document_copy_emails(
        application=application,
        signed_documents=[_signed_doc()],
    )
    assert calls == ["pat@example.com"]


def test_sign_documents_stores_rows_and_attempts_copy_emails(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    email_calls: list[str] = []

    def fake_send_email(**kwargs):
        email_calls.append(kwargs["to_email"])
        return EmailSendResult(status="sent")

    monkeypatch.setattr(
        "app.services.partner_signed_document_copy_service.send_email",
        fake_send_email,
    )

    client.post(
        "/partner/onboard",
        data={
            "full_name": "Email Test",
            "email": "email-copy@example.com",
            "phone": "+15551230002",
            "market_area": "Austin, TX",
            "sales_experience": "B2B",
            "target_industries": "HVAC",
            "why_interested": "Commission work",
            "ic_understanding": "on",
        },
    )
    application = (
        db_session.query(PartnerApplication)
        .filter(PartnerApplication.email == "email-copy@example.com")
        .one()
    )
    raw, _ = partner_service.issue_docs_signing_invite(db_session, application.id)
    db_session.commit()

    response = client.post(
        f"/partner/sign-documents?token={raw}",
        data=partner_sign_documents_form_data(signature_text="Email Test"),
        follow_redirects=False,
    )
    assert response.status_code == 303

    signed_count = (
        db_session.query(PartnerSignedDocument)
        .filter(PartnerSignedDocument.application_id == application.id)
        .count()
    )
    assert signed_count == 5
    assert "email-copy@example.com" in email_calls


def test_sign_documents_succeeds_when_copy_email_raises(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failing_send_email(**kwargs):
        raise RuntimeError("SMTP down")

    monkeypatch.setattr(
        "app.services.partner_signed_document_copy_service.send_email",
        failing_send_email,
    )

    client.post(
        "/partner/onboard",
        data={
            "full_name": "Fail Email",
            "email": "fail-email@example.com",
            "phone": "+15551230003",
            "market_area": "Austin, TX",
            "sales_experience": "B2B",
            "target_industries": "HVAC",
            "why_interested": "Commission work",
            "ic_understanding": "on",
        },
    )
    application = (
        db_session.query(PartnerApplication)
        .filter(PartnerApplication.email == "fail-email@example.com")
        .one()
    )
    raw, _ = partner_service.issue_docs_signing_invite(db_session, application.id)
    db_session.commit()

    response = client.post(
        f"/partner/sign-documents?token={raw}",
        data=partner_sign_documents_form_data(signature_text="Fail Email"),
        follow_redirects=False,
    )
    assert response.status_code == 303
    db_session.refresh(application)
    assert application.status == "docs_signed"
    assert (
        db_session.query(PartnerSignedDocument)
        .filter(PartnerSignedDocument.application_id == application.id)
        .count()
        == 5
    )


def test_sign_documents_success_page_does_not_guarantee_email(client: TestClient) -> None:
    response = client.get("/partner/sign-documents/success")
    assert response.status_code == 200
    assert "If email delivery is available" in response.text
    assert "will be sent" in response.text
    assert "have been saved" in response.text
    assert "guaranteed" not in response.text.lower()
