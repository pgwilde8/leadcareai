"""Commission ledger creation, protection, and admin status transitions."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session, joinedload

from app.models.business import Business
from app.models.commission import Commission
from app.models.partner import Partner
from app.models.partner_customer import PartnerCustomer

ACTIVATION_BONUS_CENTS = 10000
MONTHLY_RESIDUAL_CENTS = 2500
RETENTION_BONUS_CENTS = 10000
REFUND_REVIEW_NOTE = "Refund/dispute detected; review for clawback"


@dataclass(frozen=True)
class InvoiceCommissionResult:
    partner_customer: PartnerCustomer | None
    business: Business | None
    created: list[Commission]


@dataclass(frozen=True)
class CommissionProtectionResult:
    partner_customer: PartnerCustomer | None
    business: Business | None
    canceled: list[Commission]
    flagged: list[Commission]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _append_note(row: Commission, note: str) -> None:
    existing = (row.notes or "").strip()
    if note in existing:
        return
    row.notes = f"{existing}\n{note}".strip() if existing else note


def extract_stripe_id(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return str(value.get("id")) if value.get("id") else None
    return str(value)


def resolve_business_and_partner_customer(
    db: Session,
    *,
    customer_id: str | None = None,
    subscription_id: str | None = None,
    business_id: uuid.UUID | None = None,
    partner_customer_id: uuid.UUID | None = None,
    metadata: dict | None = None,
) -> tuple[PartnerCustomer | None, Business | None]:
    metadata = metadata or {}
    if partner_customer_id is None and metadata.get("partner_customer_id"):
        try:
            partner_customer_id = uuid.UUID(str(metadata["partner_customer_id"]))
        except ValueError:
            partner_customer_id = None
    if business_id is None and metadata.get("business_id"):
        try:
            business_id = uuid.UUID(str(metadata["business_id"]))
        except ValueError:
            business_id = None

    if partner_customer_id is not None:
        pc = db.get(PartnerCustomer, partner_customer_id)
        if pc is not None:
            business = db.get(Business, pc.business_id) if pc.business_id else None
            return pc, business

    business: Business | None = None
    if business_id is not None:
        business = db.get(Business, business_id)
    if business is None and customer_id:
        business = db.query(Business).filter(Business.stripe_customer_id == customer_id).one_or_none()
    if business is None and subscription_id:
        business = db.query(Business).filter(Business.stripe_subscription_id == subscription_id).one_or_none()
    if business is None:
        return None, None

    pc = (
        db.query(PartnerCustomer)
        .options(joinedload(PartnerCustomer.partner))
        .filter(PartnerCustomer.business_id == business.id)
        .order_by(PartnerCustomer.created_at.asc())
        .first()
    )
    return pc, business


def _resolve_partner_customer_from_invoice(
    db: Session,
    *,
    invoice_payload: dict,
) -> tuple[PartnerCustomer | None, Business | None]:
    metadata = invoice_payload.get("metadata") or {}
    return resolve_business_and_partner_customer(
        db,
        customer_id=extract_stripe_id(invoice_payload.get("customer")),
        subscription_id=extract_stripe_id(invoice_payload.get("subscription")),
        metadata=metadata,
    )


def _is_monthly_invoice(invoice_payload: dict) -> bool:
    billing_reason = str(invoice_payload.get("billing_reason") or "").strip().lower()
    return billing_reason in {"subscription_cycle", "subscription_create"}


def _commission_exists_for_invoice(
    db: Session,
    *,
    partner_customer_id: uuid.UUID | None,
    commission_type: str,
    stripe_invoice_id: str | None,
) -> bool:
    if partner_customer_id is None or not stripe_invoice_id:
        return False
    return (
        db.query(Commission)
        .filter(
            Commission.partner_customer_id == partner_customer_id,
            Commission.commission_type == commission_type,
            Commission.stripe_invoice_id == stripe_invoice_id,
        )
        .one_or_none()
        is not None
    )


def _activation_exists(db: Session, *, partner_customer_id: uuid.UUID | None, business_id: uuid.UUID) -> bool:
    query = db.query(Commission).filter(
        Commission.business_id == business_id,
        Commission.commission_type == "activation_bonus",
    )
    if partner_customer_id is not None:
        query = query.filter(Commission.partner_customer_id == partner_customer_id)
    return query.one_or_none() is not None


def _retention_exists(db: Session, *, partner_customer_id: uuid.UUID | None, business_id: uuid.UUID) -> bool:
    query = db.query(Commission).filter(
        Commission.business_id == business_id,
        Commission.commission_type == "retention_bonus",
    )
    if partner_customer_id is not None:
        query = query.filter(Commission.partner_customer_id == partner_customer_id)
    return query.one_or_none() is not None


def _create_commission(
    db: Session,
    *,
    partner_id: uuid.UUID,
    business_id: uuid.UUID,
    partner_customer_id: uuid.UUID | None,
    stripe_event_id: str | None,
    stripe_invoice_id: str | None,
    stripe_checkout_session_id: str | None,
    commission_type: str,
    amount_cents: int,
    eligible_at: datetime,
    notes: str | None = None,
) -> Commission:
    row = Commission(
        partner_id=partner_id,
        business_id=business_id,
        partner_customer_id=partner_customer_id,
        stripe_event_id=stripe_event_id,
        stripe_invoice_id=stripe_invoice_id,
        stripe_checkout_session_id=stripe_checkout_session_id,
        commission_type=commission_type,
        amount_cents=amount_cents,
        currency="usd",
        status="pending",
        eligible_at=eligible_at,
        notes=notes,
    )
    db.add(row)
    db.flush()
    return row


def create_commissions_for_paid_invoice(
    db: Session,
    *,
    stripe_event_id: str,
    invoice_payload: dict,
) -> InvoiceCommissionResult:
    partner_customer, business = _resolve_partner_customer_from_invoice(db, invoice_payload=invoice_payload)
    if partner_customer is None or business is None:
        return InvoiceCommissionResult(partner_customer=None, business=business, created=[])
    partner = db.get(Partner, partner_customer.partner_id)
    if partner is None:
        return InvoiceCommissionResult(partner_customer=None, business=business, created=[])

    invoice_id = invoice_payload.get("id")
    invoice_id_v = str(invoice_id) if invoice_id else None
    checkout_session_id = (
        str(invoice_payload.get("checkout_session")) if invoice_payload.get("checkout_session") else None
    )
    eligible_at = _now()
    created: list[Commission] = []

    partner_customer.status = "paying"

    if _is_monthly_invoice(invoice_payload):
        if not _commission_exists_for_invoice(
            db,
            partner_customer_id=partner_customer.id,
            commission_type="monthly_residual",
            stripe_invoice_id=invoice_id_v,
        ):
            created.append(
                _create_commission(
                    db,
                    partner_id=partner.id,
                    business_id=business.id,
                    partner_customer_id=partner_customer.id,
                    stripe_event_id=stripe_event_id,
                    stripe_invoice_id=invoice_id_v,
                    stripe_checkout_session_id=checkout_session_id,
                    commission_type="monthly_residual",
                    amount_cents=MONTHLY_RESIDUAL_CENTS,
                    eligible_at=eligible_at,
                    notes="Created from paid Stripe subscription invoice.",
                )
            )

        monthly_count = (
            db.query(Commission)
            .filter(
                Commission.partner_customer_id == partner_customer.id,
                Commission.business_id == business.id,
                Commission.commission_type == "monthly_residual",
            )
            .count()
        )

        if monthly_count >= 1 and not _activation_exists(
            db, partner_customer_id=partner_customer.id, business_id=business.id
        ):
            created.append(
                _create_commission(
                    db,
                    partner_id=partner.id,
                    business_id=business.id,
                    partner_customer_id=partner_customer.id,
                    stripe_event_id=stripe_event_id,
                    stripe_invoice_id=invoice_id_v,
                    stripe_checkout_session_id=checkout_session_id,
                    commission_type="activation_bonus",
                    amount_cents=ACTIVATION_BONUS_CENTS,
                    eligible_at=eligible_at,
                    notes="Activation bonus after first paid monthly invoice.",
                )
            )

        if monthly_count >= 6 and not _retention_exists(
            db, partner_customer_id=partner_customer.id, business_id=business.id
        ):
            created.append(
                _create_commission(
                    db,
                    partner_id=partner.id,
                    business_id=business.id,
                    partner_customer_id=partner_customer.id,
                    stripe_event_id=stripe_event_id,
                    stripe_invoice_id=invoice_id_v,
                    stripe_checkout_session_id=checkout_session_id,
                    commission_type="retention_bonus",
                    amount_cents=RETENTION_BONUS_CENTS,
                    eligible_at=eligible_at,
                    notes="Retention bonus after six paid monthly invoices.",
                )
            )

    return InvoiceCommissionResult(partner_customer=partner_customer, business=business, created=created)


def cancel_commissions_for_invoice(
    db: Session,
    *,
    stripe_invoice_id: str,
    reason: str,
) -> list[Commission]:
    rows = (
        db.query(Commission)
        .filter(
            Commission.stripe_invoice_id == stripe_invoice_id,
            Commission.status.in_(["pending", "approved"]),
        )
        .all()
    )
    for row in rows:
        row.status = "canceled"
        _append_note(row, reason)
    db.flush()
    return rows


def cancel_unpaid_commissions_for_business(
    db: Session,
    *,
    business_id: uuid.UUID,
    reason: str,
) -> list[Commission]:
    rows = (
        db.query(Commission)
        .filter(
            Commission.business_id == business_id,
            Commission.status.in_(["pending", "approved"]),
        )
        .all()
    )
    for row in rows:
        row.status = "canceled"
        _append_note(row, reason)
    db.flush()
    return rows


def flag_paid_commissions_for_review(
    db: Session,
    *,
    reason: str,
    stripe_invoice_id: str | None = None,
    business_id: uuid.UUID | None = None,
) -> list[Commission]:
    query = db.query(Commission).filter(Commission.status == "paid")
    if stripe_invoice_id:
        query = query.filter(Commission.stripe_invoice_id == stripe_invoice_id)
    elif business_id:
        query = query.filter(Commission.business_id == business_id)
    else:
        return []

    rows = query.all()
    for row in rows:
        _append_note(row, f"{REFUND_REVIEW_NOTE} ({reason})")
    db.flush()
    return rows


def protect_commissions_for_refund_or_dispute(
    db: Session,
    *,
    stripe_invoice_id: str | None,
    business_id: uuid.UUID | None,
    reason: str,
) -> CommissionProtectionResult:
    canceled: list[Commission] = []
    flagged: list[Commission] = []
    if stripe_invoice_id:
        canceled = cancel_commissions_for_invoice(db, stripe_invoice_id=stripe_invoice_id, reason=reason)
        flagged = flag_paid_commissions_for_review(
            db,
            stripe_invoice_id=stripe_invoice_id,
            reason=reason,
        )
    elif business_id:
        canceled = cancel_unpaid_commissions_for_business(db, business_id=business_id, reason=reason)
        flagged = flag_paid_commissions_for_review(db, business_id=business_id, reason=reason)

    pc: PartnerCustomer | None = None
    business: Business | None = None
    if business_id:
        business = db.get(Business, business_id)
        if business is not None:
            pc = (
                db.query(PartnerCustomer)
                .filter(PartnerCustomer.business_id == business.id)
                .order_by(PartnerCustomer.created_at.asc())
                .first()
            )
    return CommissionProtectionResult(
        partner_customer=pc,
        business=business,
        canceled=canceled,
        flagged=flagged,
    )


def list_commissions(
    db: Session,
    *,
    status: str | None = None,
) -> list[tuple[Commission, Partner | None, Business | None]]:
    query = (
        db.query(Commission, Partner, Business)
        .join(Partner, Partner.id == Commission.partner_id)
        .join(Business, Business.id == Commission.business_id)
    )
    status_v = (status or "").strip().lower()
    if status_v:
        query = query.filter(Commission.status == status_v)
    rows = query.order_by(Commission.created_at.desc()).all()
    return rows


def list_commissions_for_partner(db: Session, *, partner_id: uuid.UUID) -> list[Commission]:
    return (
        db.query(Commission)
        .filter(Commission.partner_id == partner_id)
        .order_by(Commission.created_at.desc())
        .all()
    )


def commission_totals_by_status(db: Session, *, partner_id: uuid.UUID) -> dict[str, int]:
    rows = list_commissions_for_partner(db, partner_id=partner_id)
    totals = {"pending": 0, "approved": 0, "paid": 0, "canceled": 0}
    for row in rows:
        if row.status in totals:
            totals[row.status] += 1
    return totals


def update_commission_status(db: Session, *, commission_id: uuid.UUID, action: str) -> Commission:
    row = db.get(Commission, commission_id)
    if row is None:
        raise ValueError("Commission not found")
    now = _now()
    if action == "approve":
        if row.status != "pending":
            raise ValueError("Only pending commissions can be approved")
        row.status = "approved"
        row.approved_at = now
    elif action == "mark_paid":
        if row.status != "approved":
            raise ValueError("Only approved commissions can be marked paid")
        row.status = "paid"
        row.paid_at = now
    elif action == "cancel":
        if row.status not in {"pending", "approved"}:
            raise ValueError("Only pending or approved commissions can be canceled")
        row.status = "canceled"
    elif action == "mark_clawed_back":
        if row.status != "paid":
            raise ValueError("Only paid commissions can be marked clawed back")
        row.status = "clawed_back"
        _append_note(row, "Marked clawed back by admin.")
    else:
        raise ValueError("Unsupported action")
    db.flush()
    return row
