"""Partner W-9 encryption and tax-info collection validation."""

from __future__ import annotations

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.field_encryption import decrypt_field, encrypt_field, mask_tin
from tests.settings_helpers import patch_get_settings
from app.models.partner_application import PartnerApplication
from app.models.partner_tax_info import PartnerTaxInfo
from app.services.partner_document_service import seed_default_document_templates
from app.services.partner_tax_service import validate_partner_tax_info
from app.services import partner_service
from app.services.user_service import create_admin_user
from tests.partner_fixtures import (
    ensure_partner_application_docs_signed,
    partner_onboard_form_data,
    partner_tax_info_form_data,
)


def test_encrypt_decrypt_roundtrip() -> None:
    token = encrypt_field("123456789")
    assert decrypt_field(token) == "123456789"
    assert "123456789" not in token


def test_mask_tin_formats() -> None:
    assert mask_tin("ssn", "123456789") == "***-**-6789"
    assert mask_tin("ein", "123456789") == "**-***6789"


def test_invalid_ein_rejected() -> None:
    with pytest.raises(ValueError, match="9 digits"):
        validate_partner_tax_info(
            legal_name="Acme LLC",
            business_name="Acme LLC",
            address_line1="1 Main",
            address_line2=None,
            city="Austin",
            state="TX",
            postal_code="78701",
            tax_classification="llc_c",
            tin_type="ein",
            tin="12-345",
            tax_certified=True,
        )


def test_invalid_ssn_rejected() -> None:
    with pytest.raises(ValueError, match="9 digits"):
        validate_partner_tax_info(
            legal_name="Pat Ner",
            business_name=None,
            address_line1="1 Main",
            address_line2=None,
            city="Austin",
            state="TX",
            postal_code="78701",
            tax_classification="individual",
            tin_type="ssn",
            tin="12345",
            tax_certified=True,
        )


def test_partner_onboard_post_does_not_accept_tax_fields(
    client: TestClient,
    db_session: Session,
) -> None:
    response = client.post(
        "/partner/onboard",
        data={
            **partner_onboard_form_data(email="tax.reject@example.com"),
            "tax_tin": "987654321",
            "tax_legal_name": "Should Ignore",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    application = (
        db_session.query(PartnerApplication)
        .filter(PartnerApplication.email == "tax.reject@example.com")
        .one()
    )
    assert application.status == "admin_review"
    assert (
        db_session.query(PartnerTaxInfo)
        .filter(PartnerTaxInfo.application_id == application.id)
        .count()
        == 0
    )


def test_tax_info_plaintext_tin_not_in_response(client: TestClient, db_session: Session) -> None:
    client.post("/partner/onboard", data=partner_onboard_form_data(email="tax.tester@example.com"))
    application = (
        db_session.query(PartnerApplication)
        .filter(PartnerApplication.email == "tax.tester@example.com")
        .one()
    )
    tax_token = ensure_partner_application_docs_signed(db_session, application.id)
    assert tax_token is not None
    db_session.commit()

    response = client.post(
        f"/partner/tax-info?token={tax_token}",
        data=partner_tax_info_form_data(tax_tin="987654321"),
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "987654321" not in response.text


def test_admin_detail_shows_masked_tin_only(client: TestClient, db_session: Session) -> None:
    client.post(
        "/partner/onboard",
        data=partner_onboard_form_data(
            first_name="Admin",
            last_name="View",
            email="admin.view@example.com",
        ),
    )
    application = (
        db_session.query(PartnerApplication)
        .filter(PartnerApplication.email == "admin.view@example.com")
        .one()
    )
    ensure_partner_application_docs_signed(db_session, application.id)
    raw, _ = partner_service.issue_tax_info_token(db_session, application.id)
    db_session.commit()
    client.post(
        f"/partner/tax-info?token={raw}",
        data=partner_tax_info_form_data(
            tax_legal_name="Admin View",
            tax_tin_type="ein",
            tax_tin="112233445",
            tax_classification="sole_proprietor",
            tax_city="Dallas",
            tax_postal_code="75201",
            tax_address_line1="300 Pine St",
        ),
    )
    db_session.commit()

    create_admin_user(db_session, email="tax-admin@example.com", password="admin-secret")
    db_session.commit()
    client.post("/login", data={"email": "tax-admin@example.com", "password": "admin-secret"})

    detail = client.get(f"/admin/partners/{application.id}")
    assert detail.status_code == 200
    assert "TIN (masked)" in detail.text
    assert "***" in detail.text or "**-***" in detail.text
    assert "112233445" not in detail.text
    assert "tin_encrypted" not in detail.text.lower()
    assert "Onboarding progress" in detail.text


def test_missing_encryption_key_encrypt_raises_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_get_settings(monkeypatch, app_env="production", partner_tax_encryption_key=None)
    with pytest.raises(ValueError, match="PARTNER_TAX_ENCRYPTION_KEY"):
        encrypt_field("123456789")


def test_production_with_valid_key_encrypt_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    key = Fernet.generate_key().decode()
    patch_get_settings(monkeypatch, app_env="production", partner_tax_encryption_key=key)
    token = encrypt_field("123456789")
    assert decrypt_field(token) == "123456789"
    assert key not in token


@pytest.mark.no_partner_tax_encryption_key
def test_missing_encryption_key_fails_on_tax_info_submit(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_get_settings(monkeypatch, app_env="production", partner_tax_encryption_key=None)
    seed_default_document_templates(db_session)
    db_session.commit()
    client.post("/partner/onboard", data=partner_onboard_form_data(email="prod.fail@example.com"))
    application = (
        db_session.query(PartnerApplication)
        .filter(PartnerApplication.email == "prod.fail@example.com")
        .one()
    )
    tax_token = ensure_partner_application_docs_signed(db_session, application.id)
    db_session.commit()

    response = client.post(
        f"/partner/tax-info?token={tax_token}",
        data=partner_tax_info_form_data(),
    )
    assert response.status_code == 400
    assert "PARTNER_TAX_ENCRYPTION_KEY" in response.text
    assert (
        db_session.query(PartnerTaxInfo)
        .filter(PartnerTaxInfo.application_id == application.id)
        .count()
        == 0
    )
