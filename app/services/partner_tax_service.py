"""Partner W-9 / tax information validation and encrypted storage."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.field_encryption import encrypt_field, mask_tin
from app.models.partner_tax_info import PartnerTaxInfo, TIN_TYPES

_NON_DIGIT = re.compile(r"\D+")

TAX_CLASSIFICATIONS = frozenset(
    {
        "individual",
        "sole_proprietor",
        "single_member_llc",
        "c_corporation",
        "s_corporation",
        "partnership",
        "trust_estate",
        "llc_c",
        "llc_s",
        "other",
    }
)


@dataclass(frozen=True)
class PartnerTaxInfoInput:
    legal_name: str
    business_name: str | None
    address_line1: str
    address_line2: str | None
    city: str
    state: str
    postal_code: str
    tax_classification: str
    tin_type: str
    tin: str


@dataclass(frozen=True)
class PartnerTaxInfoMasked:
    legal_name: str
    business_name: str | None
    address_line1: str
    address_line2: str | None
    city: str
    state: str
    postal_code: str
    tax_classification: str
    tin_type: str
    tin_masked: str
    certified_at: datetime


def _strip(value: str | None, *, max_len: int) -> str:
    return (value or "").strip()[:max_len]


def _normalize_tin_digits(tin: str) -> str:
    digits = _NON_DIGIT.sub("", tin.strip())
    return digits


def validate_partner_tax_info(
    *,
    legal_name: str,
    business_name: str | None,
    address_line1: str,
    address_line2: str | None,
    city: str,
    state: str,
    postal_code: str,
    tax_classification: str,
    tin_type: str,
    tin: str,
    tax_certified: bool,
) -> PartnerTaxInfoInput:
    if not tax_certified:
        raise ValueError("You must certify that the tax information provided is accurate.")

    clean_legal = _strip(legal_name, max_len=255)
    if len(clean_legal) < 2:
        raise ValueError("Legal name is required for tax information.")

    clean_address1 = _strip(address_line1, max_len=255)
    clean_city = _strip(city, max_len=120)
    clean_state = _strip(state, max_len=64)
    clean_postal = _strip(postal_code, max_len=20)
    if not clean_address1 or not clean_city or not clean_state or not clean_postal:
        raise ValueError("Complete mailing address is required for tax information.")

    classification = _strip(tax_classification, max_len=80).lower().replace(" ", "_")
    if classification not in TAX_CLASSIFICATIONS:
        raise ValueError("Please select a valid tax classification.")

    tin_type_clean = _strip(tin_type, max_len=10).lower()
    if tin_type_clean not in TIN_TYPES:
        raise ValueError("TIN type must be SSN or EIN.")

    digits = _normalize_tin_digits(tin)
    if len(digits) != 9:
        raise ValueError("Tax ID must be exactly 9 digits.")

    return PartnerTaxInfoInput(
        legal_name=clean_legal,
        business_name=_strip(business_name, max_len=255) or None,
        address_line1=clean_address1,
        address_line2=_strip(address_line2, max_len=255) or None,
        city=clean_city,
        state=clean_state,
        postal_code=clean_postal,
        tax_classification=classification,
        tin_type=tin_type_clean,
        tin=digits,
    )


def create_partner_tax_info_for_application(
    db: Session,
    *,
    application_id,
    data: PartnerTaxInfoInput,
) -> PartnerTaxInfo:
    encrypted = encrypt_field(data.tin)
    record = PartnerTaxInfo(
        application_id=application_id,
        legal_name=data.legal_name,
        business_name=data.business_name,
        address_line1=data.address_line1,
        address_line2=data.address_line2,
        city=data.city,
        state=data.state,
        postal_code=data.postal_code,
        tax_classification=data.tax_classification,
        tin_type=data.tin_type,
        tin_encrypted=encrypted,
        certified_at=datetime.now(timezone.utc),
    )
    db.add(record)
    db.flush()
    return record


def get_partner_tax_info_for_partner(db: Session, partner) -> PartnerTaxInfo | None:
    """Load tax info for an approved partner via linked application."""
    application_id = getattr(partner, "application_id", None)
    if application_id is None:
        return None
    return get_partner_tax_info_for_application(db, application_id)


def get_partner_tax_info_for_application(
    db: Session,
    application_id,
) -> PartnerTaxInfo | None:
    return (
        db.query(PartnerTaxInfo)
        .filter(PartnerTaxInfo.application_id == application_id)
        .one_or_none()
    )


def mask_partner_tax_info(record: PartnerTaxInfo) -> PartnerTaxInfoMasked:
    """Build admin-safe view without decrypting or exposing full TIN in templates."""
    tin_for_mask = "000000000"
    if record.tin_encrypted:
        try:
            from app.core.field_encryption import decrypt_field

            digits = _normalize_tin_digits(decrypt_field(record.tin_encrypted))
            if len(digits) == 9:
                tin_for_mask = digits
        except ValueError:
            tin_for_mask = "000000000"

    return PartnerTaxInfoMasked(
        legal_name=record.legal_name,
        business_name=record.business_name,
        address_line1=record.address_line1,
        address_line2=record.address_line2,
        city=record.city,
        state=record.state,
        postal_code=record.postal_code,
        tax_classification=record.tax_classification,
        tin_type=record.tin_type,
        tin_masked=mask_tin(record.tin_type, tin_for_mask),
        certified_at=record.certified_at,
    )
