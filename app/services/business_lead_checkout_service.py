"""Convert BusinessLead prospects to paying Business customers via Stripe Checkout."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.models.business import Business
from app.models.business_lead import PAYMENT_STATUSES, BusinessLead
from app.models.partner_customer import PartnerCustomer
from app.models.payment_event import PaymentEvent
from app.services import stripe_service
from app.services.business_lead_service import get_business_lead
from app.services.business_service import create_business

CHECKOUT_ALLOWED_STATUSES = frozenset({"contacted", "qualified"})
PAYMENT_STATUS_NONE = "none"
PAYMENT_STATUS_CHECKOUT_CREATED = "checkout_created"
PAYMENT_STATUS_PAID = "paid"


@dataclass
class LeadCheckoutResult:
    lead: BusinessLead
    business: Business
    checkout_url: str
    checkout_session_id: str
    reused_existing: bool = False


def get_partner_customer_for_lead(db: Session, lead_id: uuid.UUID) -> PartnerCustomer | None:
    return (
        db.query(PartnerCustomer)
        .filter(PartnerCustomer.business_lead_id == lead_id)
        .order_by(PartnerCustomer.created_at)
        .first()
    )


def ensure_business_from_lead(db: Session, lead: BusinessLead) -> Business:
    if lead.converted_business_id is not None:
        business = db.get(Business, lead.converted_business_id)
        if business is not None:
            return business

    business = create_business(
        db,
        name=lead.business_name,
        industry=lead.industry,
        main_phone=lead.phone,
    )
    business.status = "pending"
    lead.converted_business_id = business.id
    db.flush()

    partner_customer = get_partner_customer_for_lead(db, lead.id)
    if partner_customer is not None and partner_customer.business_id is None:
        partner_customer.business_id = business.id
        db.flush()

    return business


def _build_checkout_metadata(
    *,
    lead: BusinessLead,
    business: Business,
    partner_customer: PartnerCustomer | None,
) -> dict[str, str]:
    metadata: dict[str, str] = {
        "business_lead_id": str(lead.id),
        "business_id": str(business.id),
    }
    if lead.partner_id is not None:
        metadata["partner_id"] = str(lead.partner_id)
    if lead.referral_code:
        metadata["referral_code"] = lead.referral_code
    if partner_customer is not None:
        metadata["partner_customer_id"] = str(partner_customer.id)
    return metadata


def create_checkout_for_lead(db: Session, lead_id: uuid.UUID) -> LeadCheckoutResult:
    lead = (
        db.query(BusinessLead)
        .options(joinedload(BusinessLead.partner))
        .filter(BusinessLead.id == lead_id)
        .one_or_none()
    )
    if lead is None:
        raise ValueError("Business lead not found")

    if lead.status == "rejected":
        raise ValueError("Cannot create checkout for a rejected lead")
    if lead.status not in CHECKOUT_ALLOWED_STATUSES and lead.status != "converted":
        raise ValueError("Lead must be contacted or qualified before checkout")
    if lead.payment_status == PAYMENT_STATUS_PAID:
        raise ValueError("Lead is already paid")
    if lead.status == "converted" and lead.payment_status == PAYMENT_STATUS_PAID:
        raise ValueError("Lead is already converted and paid")

    business = ensure_business_from_lead(db, lead)
    partner_customer = get_partner_customer_for_lead(db, lead.id)

    if (
        lead.payment_status == PAYMENT_STATUS_CHECKOUT_CREATED
        and lead.stripe_checkout_url
        and lead.stripe_checkout_session_id
    ):
        return LeadCheckoutResult(
            lead=lead,
            business=business,
            checkout_url=lead.stripe_checkout_url,
            checkout_session_id=lead.stripe_checkout_session_id,
            reused_existing=True,
        )

    settings = get_settings()
    base_url = settings.effective_public_base_url or settings.app_base_url.rstrip("/")
    success_url = f"{base_url}/billing/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{base_url}/demo?checkout=cancelled"

    metadata = _build_checkout_metadata(
        lead=lead,
        business=business,
        partner_customer=partner_customer,
    )
    session = stripe_service.create_growth_checkout_session(
        customer_email=lead.email,
        metadata=metadata,
        success_url=success_url,
        cancel_url=cancel_url,
    )

    lead.stripe_checkout_session_id = session.session_id
    lead.stripe_checkout_url = session.url
    lead.payment_status = PAYMENT_STATUS_CHECKOUT_CREATED
    if session.customer_id:
        lead.stripe_customer_id = session.customer_id
        business.stripe_customer_id = session.customer_id

    db.flush()
    return LeadCheckoutResult(
        lead=lead,
        business=business,
        checkout_url=session.url,
        checkout_session_id=session.session_id,
        reused_existing=False,
    )


def _payment_event_exists(db: Session, stripe_event_id: str) -> bool:
    return (
        db.query(PaymentEvent)
        .filter(PaymentEvent.stripe_event_id == stripe_event_id)
        .one_or_none()
        is not None
    )


def handle_checkout_session_completed(
    db: Session,
    *,
    stripe_event_id: str,
    session_payload: dict,
) -> PaymentEvent | None:
    """Idempotent webhook handler for checkout.session.completed."""
    if _payment_event_exists(db, stripe_event_id):
        return (
            db.query(PaymentEvent)
            .filter(PaymentEvent.stripe_event_id == stripe_event_id)
            .one()
        )

    metadata = session_payload.get("metadata") or {}
    lead_id_raw = metadata.get("business_lead_id")
    business_id_raw = metadata.get("business_id")

    if not lead_id_raw:
        raise ValueError("checkout.session.completed missing business_lead_id metadata")

    lead_id = uuid.UUID(str(lead_id_raw))
    lead = get_business_lead(db, lead_id)

    business: Business | None = None
    if business_id_raw:
        business = db.get(Business, uuid.UUID(str(business_id_raw)))
    if business is None and lead.converted_business_id:
        business = db.get(Business, lead.converted_business_id)
    if business is None:
        business = ensure_business_from_lead(db, lead)

    customer_id = session_payload.get("customer")
    subscription_id = session_payload.get("subscription")
    if isinstance(customer_id, dict):
        customer_id = customer_id.get("id")
    if isinstance(subscription_id, dict):
        subscription_id = subscription_id.get("id")

    now = datetime.now(timezone.utc)
    lead.payment_status = PAYMENT_STATUS_PAID
    lead.status = "converted"
    lead.converted_at = now
    lead.converted_business_id = business.id
    if customer_id:
        lead.stripe_customer_id = str(customer_id)
        business.stripe_customer_id = str(customer_id)
    if subscription_id:
        business.stripe_subscription_id = str(subscription_id)
    business.status = "active"

    partner_customer = get_partner_customer_for_lead(db, lead.id)
    if partner_customer is not None:
        partner_customer.business_id = business.id
        partner_customer.status = "paying"

    amount_total = session_payload.get("amount_total")
    event = PaymentEvent(
        stripe_event_id=stripe_event_id,
        event_type="checkout.session.completed",
        business_id=business.id,
        business_lead_id=lead.id,
        stripe_customer_id=str(customer_id) if customer_id else None,
        stripe_subscription_id=str(subscription_id) if subscription_id else None,
        amount_paid_cents=int(amount_total) if amount_total is not None else None,
        raw_json=json.dumps(session_payload),
        processed_at=now,
    )
    db.add(event)
    db.flush()
    return event
