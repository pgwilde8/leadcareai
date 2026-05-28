"""Convert BusinessLead prospects to paying Business customers via Stripe Checkout."""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.models.business import Business
from app.models.business_lead import PAYMENT_STATUSES, BusinessLead
from app.models.partner_customer import PartnerCustomer
from app.models.payment_event import PaymentEvent
from app.services import commission_service, stripe_service
from app.services.business_lead_service import get_business_lead
from app.services.business_service import create_business
from app.services.user_invite_service import create_or_invite_business_user_for_business

logger = logging.getLogger(__name__)

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


def _record_payment_event(
    db: Session,
    *,
    stripe_event_id: str,
    event_type: str,
    payload: dict,
    business_id: uuid.UUID | None = None,
    business_lead_id: uuid.UUID | None = None,
    stripe_customer_id: str | None = None,
    stripe_subscription_id: str | None = None,
    stripe_invoice_id: str | None = None,
    amount_paid_cents: int | None = None,
) -> PaymentEvent:
    event = PaymentEvent(
        stripe_event_id=stripe_event_id,
        event_type=event_type,
        business_id=business_id,
        business_lead_id=business_lead_id,
        stripe_customer_id=stripe_customer_id,
        stripe_subscription_id=stripe_subscription_id,
        stripe_invoice_id=stripe_invoice_id,
        amount_paid_cents=amount_paid_cents,
        raw_json=json.dumps(payload),
        processed_at=datetime.now(timezone.utc),
    )
    db.add(event)
    db.flush()
    return event


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

    try:
        create_or_invite_business_user_for_business(
            db,
            business=business,
            email=lead.email,
            full_name=lead.contact_name,
            resend=False,
        )
    except Exception:
        logger.exception(
            "Business user invite provisioning failed after checkout completion",
            extra={"business_id": str(business.id), "business_lead_id": str(lead.id)},
        )

    amount_total = session_payload.get("amount_total")
    return _record_payment_event(
        db,
        stripe_event_id=stripe_event_id,
        event_type="checkout.session.completed",
        payload=session_payload,
        business_id=business.id,
        business_lead_id=lead.id,
        stripe_customer_id=str(customer_id) if customer_id else None,
        stripe_subscription_id=str(subscription_id) if subscription_id else None,
        amount_paid_cents=int(amount_total) if amount_total is not None else None,
    )


def handle_invoice_paid(
    db: Session,
    *,
    stripe_event_id: str,
    invoice_payload: dict,
) -> PaymentEvent:
    """Idempotent webhook handler for invoice.paid."""
    if _payment_event_exists(db, stripe_event_id):
        return db.query(PaymentEvent).filter(PaymentEvent.stripe_event_id == stripe_event_id).one()

    customer_id = invoice_payload.get("customer")
    subscription_id = invoice_payload.get("subscription")
    invoice_id = invoice_payload.get("id")
    amount_paid = invoice_payload.get("amount_paid")
    if isinstance(customer_id, dict):
        customer_id = customer_id.get("id")
    if isinstance(subscription_id, dict):
        subscription_id = subscription_id.get("id")

    result = commission_service.create_commissions_for_paid_invoice(
        db,
        stripe_event_id=stripe_event_id,
        invoice_payload=invoice_payload,
    )
    business_id = result.business.id if result.business is not None else None

    return _record_payment_event(
        db,
        stripe_event_id=stripe_event_id,
        event_type="invoice.paid",
        payload=invoice_payload,
        business_id=business_id,
        business_lead_id=result.partner_customer.business_lead_id if result.partner_customer else None,
        stripe_customer_id=str(customer_id) if customer_id else None,
        stripe_subscription_id=str(subscription_id) if subscription_id else None,
        stripe_invoice_id=str(invoice_id) if invoice_id else None,
        amount_paid_cents=int(amount_paid) if amount_paid is not None else None,
    )


def _sync_lead_payment_status_for_business(db: Session, *, business: Business, payment_status: str) -> None:
    lead = (
        db.query(BusinessLead)
        .filter(BusinessLead.converted_business_id == business.id)
        .order_by(BusinessLead.created_at.desc())
        .first()
    )
    if lead is not None and payment_status in PAYMENT_STATUSES:
        lead.payment_status = payment_status


def handle_invoice_payment_failed(
    db: Session,
    *,
    stripe_event_id: str,
    invoice_payload: dict,
) -> PaymentEvent:
    if _payment_event_exists(db, stripe_event_id):
        return db.query(PaymentEvent).filter(PaymentEvent.stripe_event_id == stripe_event_id).one()

    partner_customer, business = commission_service.resolve_business_and_partner_customer(
        db,
        customer_id=commission_service.extract_stripe_id(invoice_payload.get("customer")),
        subscription_id=commission_service.extract_stripe_id(invoice_payload.get("subscription")),
        metadata=invoice_payload.get("metadata") or {},
    )
    if business is not None:
        business.status = "past_due"
        _sync_lead_payment_status_for_business(db, business=business, payment_status="failed")
    if partner_customer is not None:
        if partner_customer.status == "paying":
            partner_customer.status = "payment_failed"
        elif partner_customer.status in {"referred", "signed_up"}:
            partner_customer.status = "signed_up"

    return _record_payment_event(
        db,
        stripe_event_id=stripe_event_id,
        event_type="invoice.payment_failed",
        payload=invoice_payload,
        business_id=business.id if business else None,
        business_lead_id=partner_customer.business_lead_id if partner_customer else None,
        stripe_customer_id=commission_service.extract_stripe_id(invoice_payload.get("customer")),
        stripe_subscription_id=commission_service.extract_stripe_id(invoice_payload.get("subscription")),
        stripe_invoice_id=commission_service.extract_stripe_id(invoice_payload.get("id")),
    )


def handle_subscription_deleted(
    db: Session,
    *,
    stripe_event_id: str,
    subscription_payload: dict,
) -> PaymentEvent:
    if _payment_event_exists(db, stripe_event_id):
        return db.query(PaymentEvent).filter(PaymentEvent.stripe_event_id == stripe_event_id).one()

    partner_customer, business = commission_service.resolve_business_and_partner_customer(
        db,
        customer_id=commission_service.extract_stripe_id(subscription_payload.get("customer")),
        subscription_id=commission_service.extract_stripe_id(subscription_payload.get("id")),
        metadata=subscription_payload.get("metadata") or {},
    )
    if business is not None:
        business.status = "canceled"
        _sync_lead_payment_status_for_business(db, business=business, payment_status="canceled")
        commission_service.cancel_unpaid_commissions_for_business(
            db,
            business_id=business.id,
            reason="Subscription canceled; unpaid commissions canceled.",
        )
    if partner_customer is not None:
        partner_customer.status = "canceled"

    return _record_payment_event(
        db,
        stripe_event_id=stripe_event_id,
        event_type="customer.subscription.deleted",
        payload=subscription_payload,
        business_id=business.id if business else None,
        business_lead_id=partner_customer.business_lead_id if partner_customer else None,
        stripe_customer_id=commission_service.extract_stripe_id(subscription_payload.get("customer")),
        stripe_subscription_id=commission_service.extract_stripe_id(subscription_payload.get("id")),
    )


def handle_subscription_updated(
    db: Session,
    *,
    stripe_event_id: str,
    subscription_payload: dict,
) -> PaymentEvent:
    if _payment_event_exists(db, stripe_event_id):
        return db.query(PaymentEvent).filter(PaymentEvent.stripe_event_id == stripe_event_id).one()

    status = str(subscription_payload.get("status") or "").strip().lower()
    partner_customer, business = commission_service.resolve_business_and_partner_customer(
        db,
        customer_id=commission_service.extract_stripe_id(subscription_payload.get("customer")),
        subscription_id=commission_service.extract_stripe_id(subscription_payload.get("id")),
        metadata=subscription_payload.get("metadata") or {},
    )
    if business is not None:
        if status in {"canceled", "unpaid"}:
            business.status = "canceled"
            _sync_lead_payment_status_for_business(db, business=business, payment_status="canceled")
            commission_service.cancel_unpaid_commissions_for_business(
                db,
                business_id=business.id,
                reason=f"Subscription status {status}; unpaid commissions canceled.",
            )
            if partner_customer is not None:
                partner_customer.status = "canceled"
        elif status == "past_due":
            business.status = "past_due"
            _sync_lead_payment_status_for_business(db, business=business, payment_status="failed")
            if partner_customer is not None and partner_customer.status == "paying":
                partner_customer.status = "payment_failed"

    return _record_payment_event(
        db,
        stripe_event_id=stripe_event_id,
        event_type="customer.subscription.updated",
        payload=subscription_payload,
        business_id=business.id if business else None,
        business_lead_id=partner_customer.business_lead_id if partner_customer else None,
        stripe_customer_id=commission_service.extract_stripe_id(subscription_payload.get("customer")),
        stripe_subscription_id=commission_service.extract_stripe_id(subscription_payload.get("id")),
    )


def handle_charge_refunded(
    db: Session,
    *,
    stripe_event_id: str,
    charge_payload: dict,
) -> PaymentEvent:
    if _payment_event_exists(db, stripe_event_id):
        return db.query(PaymentEvent).filter(PaymentEvent.stripe_event_id == stripe_event_id).one()

    invoice_id = commission_service.extract_stripe_id(charge_payload.get("invoice"))
    customer_id = commission_service.extract_stripe_id(charge_payload.get("customer"))
    metadata = charge_payload.get("metadata") or {}
    partner_customer, business = commission_service.resolve_business_and_partner_customer(
        db,
        customer_id=customer_id,
        metadata=metadata,
    )
    business_id = business.id if business else None
    if invoice_id:
        commission_service.protect_commissions_for_refund_or_dispute(
            db,
            stripe_invoice_id=invoice_id,
            business_id=None,
            reason="Stripe charge refunded.",
        )
    elif business_id:
        commission_service.protect_commissions_for_refund_or_dispute(
            db,
            stripe_invoice_id=None,
            business_id=business_id,
            reason="Stripe charge refunded.",
        )
    if business is not None:
        business.status = "canceled"
        _sync_lead_payment_status_for_business(db, business=business, payment_status="failed")
    if partner_customer is not None and partner_customer.status == "paying":
        partner_customer.status = "canceled"

    return _record_payment_event(
        db,
        stripe_event_id=stripe_event_id,
        event_type="charge.refunded",
        payload=charge_payload,
        business_id=business_id,
        business_lead_id=partner_customer.business_lead_id if partner_customer else None,
        stripe_customer_id=customer_id,
        stripe_invoice_id=invoice_id,
    )


def handle_charge_dispute_created(
    db: Session,
    *,
    stripe_event_id: str,
    dispute_payload: dict,
) -> PaymentEvent:
    if _payment_event_exists(db, stripe_event_id):
        return db.query(PaymentEvent).filter(PaymentEvent.stripe_event_id == stripe_event_id).one()

    # Dispute payload may not include invoice; protect by charge metadata if present.
    metadata = dispute_payload.get("metadata") or {}
    partner_customer, business = commission_service.resolve_business_and_partner_customer(
        db,
        metadata=metadata,
    )
    business_id = business.id if business else None
    if business_id:
        commission_service.protect_commissions_for_refund_or_dispute(
            db,
            stripe_invoice_id=None,
            business_id=business_id,
            reason="Stripe dispute created.",
        )
    if partner_customer is not None and partner_customer.status == "paying":
        partner_customer.status = "payment_failed"

    return _record_payment_event(
        db,
        stripe_event_id=stripe_event_id,
        event_type="charge.dispute.created",
        payload=dispute_payload,
        business_id=business_id,
        business_lead_id=partner_customer.business_lead_id if partner_customer else None,
    )


def handle_checkout_session_expired(
    db: Session,
    *,
    stripe_event_id: str,
    session_payload: dict,
) -> PaymentEvent:
    if _payment_event_exists(db, stripe_event_id):
        return db.query(PaymentEvent).filter(PaymentEvent.stripe_event_id == stripe_event_id).one()

    session_id = commission_service.extract_stripe_id(session_payload.get("id"))
    metadata = session_payload.get("metadata") or {}
    lead_id_raw = metadata.get("business_lead_id")
    business_id_raw = metadata.get("business_id")
    lead: BusinessLead | None = None
    business: Business | None = None

    if lead_id_raw:
        try:
            lead = get_business_lead(db, uuid.UUID(str(lead_id_raw)))
        except ValueError:
            lead = None
    if business_id_raw:
        try:
            business = db.get(Business, uuid.UUID(str(business_id_raw)))
        except ValueError:
            business = None
    if lead is None and session_id:
        lead = (
            db.query(BusinessLead)
            .filter(BusinessLead.stripe_checkout_session_id == session_id)
            .one_or_none()
        )
    if lead is not None and lead.payment_status == PAYMENT_STATUS_CHECKOUT_CREATED:
        lead.payment_status = "canceled"
    if business is None and lead is not None and lead.converted_business_id:
        business = db.get(Business, lead.converted_business_id)

    partner_customer = get_partner_customer_for_lead(db, lead.id) if lead else None

    return _record_payment_event(
        db,
        stripe_event_id=stripe_event_id,
        event_type="checkout.session.expired",
        payload=session_payload,
        business_id=business.id if business else None,
        business_lead_id=lead.id if lead else None,
        stripe_customer_id=commission_service.extract_stripe_id(session_payload.get("customer")),
    )
