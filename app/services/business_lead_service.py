"""Business lead / demo intake and partner attribution."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session, joinedload

from app.models.business_lead import BUSINESS_LEAD_STATUSES, BusinessLead
from app.models.partner import Partner
from app.models.partner_customer import PartnerCustomer


def _normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if not normalized:
        raise ValueError("Email is required")
    return normalized


def _normalize_phone(phone: str) -> str:
    normalized = phone.strip()
    if not normalized:
        raise ValueError("Phone is required")
    return normalized


def list_business_leads(db: Session) -> list[BusinessLead]:
    return (
        db.query(BusinessLead)
        .options(joinedload(BusinessLead.partner))
        .order_by(BusinessLead.created_at.desc())
        .all()
    )


def list_business_leads_for_partner(db: Session, partner_id: uuid.UUID) -> list[BusinessLead]:
    return (
        db.query(BusinessLead)
        .filter(BusinessLead.partner_id == partner_id)
        .order_by(BusinessLead.created_at.desc())
        .all()
    )


def get_business_lead(db: Session, lead_id: uuid.UUID) -> BusinessLead:
    lead = (
        db.query(BusinessLead)
        .options(joinedload(BusinessLead.partner))
        .filter(BusinessLead.id == lead_id)
        .one_or_none()
    )
    if lead is None:
        raise ValueError("Business lead not found")
    return lead


def find_recent_lead_by_email_and_phone(
    db: Session,
    *,
    email: str,
    phone: str,
) -> BusinessLead | None:
    return (
        db.query(BusinessLead)
        .filter(
            BusinessLead.email == _normalize_email(email),
            BusinessLead.phone == _normalize_phone(phone),
        )
        .order_by(BusinessLead.created_at.desc())
        .first()
    )


def count_referred_leads_for_partner(db: Session, partner_id: uuid.UUID) -> int:
    return (
        db.query(BusinessLead)
        .filter(BusinessLead.partner_id == partner_id)
        .count()
    )


def create_demo_lead(
    db: Session,
    *,
    business_name: str,
    contact_name: str,
    email: str,
    phone: str,
    city: str,
    state: str,
    industry: str | None = None,
    notes: str | None = None,
    partner: Partner | None = None,
    referral_code: str | None = None,
) -> tuple[BusinessLead, PartnerCustomer | None]:
    if not business_name.strip():
        raise ValueError("Business name is required")
    if not contact_name.strip():
        raise ValueError("Contact name is required")
    if not city.strip():
        raise ValueError("City is required")
    if not state.strip():
        raise ValueError("State is required")

    normalized_email = _normalize_email(email)
    normalized_phone = _normalize_phone(phone)

    existing = find_recent_lead_by_email_and_phone(
        db,
        email=normalized_email,
        phone=normalized_phone,
    )
    if existing is not None:
        lead = existing
        lead.business_name = business_name.strip()
        lead.contact_name = contact_name.strip()
        lead.industry = industry.strip() if industry and industry.strip() else lead.industry
        lead.city = city.strip()
        lead.state = state.strip()
        if notes and notes.strip():
            lead.notes = notes.strip()
        if partner is not None:
            lead.partner_id = partner.id
            lead.referral_code = partner.referral_code
    else:
        lead = BusinessLead(
            business_name=business_name.strip(),
            contact_name=contact_name.strip(),
            email=normalized_email,
            phone=normalized_phone,
            industry=industry.strip() if industry and industry.strip() else None,
            city=city.strip(),
            state=state.strip(),
            notes=notes.strip() if notes and notes.strip() else None,
            source="demo_form",
            referral_code=referral_code,
            partner_id=partner.id if partner else None,
            status="new",
        )
        db.add(lead)
        db.flush()

    partner_customer: PartnerCustomer | None = None
    if partner is not None:
        partner_customer = _get_or_create_partner_customer(
            db,
            partner=partner,
            business_lead=lead,
            referral_code=partner.referral_code,
        )

    db.flush()
    return lead, partner_customer


def create_website_checkout_lead(
    db: Session,
    *,
    partner: Partner | None = None,
    referral_code: str | None = None,
) -> tuple[BusinessLead, PartnerCustomer | None]:
    """Placeholder lead for public pricing checkout; Stripe collects real contact info."""
    lead_id = uuid.uuid4()
    lead = BusinessLead(
        business_name="Website checkout (pending)",
        contact_name="Website checkout",
        email=f"checkout.{lead_id.hex}@pending.leadcareai.com",
        phone="+10000000001",
        city="Online",
        state="—",
        source="website_checkout",
        referral_code=referral_code,
        partner_id=partner.id if partner else None,
        status="qualified",
        notes="Created from public pricing page; contact details pending Stripe Checkout.",
    )
    db.add(lead)
    db.flush()

    partner_customer: PartnerCustomer | None = None
    if partner is not None:
        partner_customer = _get_or_create_partner_customer(
            db,
            partner=partner,
            business_lead=lead,
            referral_code=partner.referral_code,
        )
    db.flush()
    return lead, partner_customer


def _get_or_create_partner_customer(
    db: Session,
    *,
    partner: Partner,
    business_lead: BusinessLead,
    referral_code: str,
) -> PartnerCustomer:
    existing = (
        db.query(PartnerCustomer)
        .filter(
            PartnerCustomer.partner_id == partner.id,
            PartnerCustomer.business_lead_id == business_lead.id,
        )
        .one_or_none()
    )
    if existing is not None:
        return existing

    record = PartnerCustomer(
        partner_id=partner.id,
        business_lead_id=business_lead.id,
        referral_code=referral_code,
        status="referred",
    )
    db.add(record)
    db.flush()
    return record


def update_business_lead_status(db: Session, lead_id: uuid.UUID, status: str) -> BusinessLead:
    if status not in BUSINESS_LEAD_STATUSES:
        raise ValueError(f"Invalid business lead status: {status!r}")
    lead = get_business_lead(db, lead_id)
    lead.status = status
    db.flush()
    return lead
