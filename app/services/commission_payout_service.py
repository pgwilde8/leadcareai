"""Manual partner payout batch bookkeeping (no automated transfers)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.models.business import Business
from app.models.commission import Commission
from app.models.commission_payout import CommissionPayout, PAYOUT_STATUSES
from app.models.partner import Partner
@dataclass(frozen=True)
class PartnerApprovedUnpaidSummary:
    partner: Partner
    approved_count: int
    approved_total_cents: int


@dataclass(frozen=True)
class PayoutListRow:
    payout: CommissionPayout
    partner: Partner
    commission_count: int


@dataclass(frozen=True)
class PartnerPayoutSummary:
    payout: CommissionPayout
    commission_count: int
    commission_summaries: list[tuple[str, int, int]]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _validate_commissions_for_draft(
    db: Session,
    *,
    partner_id: uuid.UUID,
    commission_ids: list[uuid.UUID],
) -> list[Commission]:
    if not commission_ids:
        raise ValueError("Select at least one approved commission for the payout batch.")

    rows = (
        db.query(Commission)
        .filter(Commission.id.in_(commission_ids))
        .all()
    )
    if len(rows) != len(set(commission_ids)):
        raise ValueError("One or more selected commissions were not found.")

    currencies: set[str] = set()
    for row in rows:
        if row.partner_id != partner_id:
            raise ValueError("All commissions must belong to the selected partner.")
        if row.status != "approved":
            raise ValueError("Only approved commissions can be added to a payout batch.")
        if row.payout_id is not None:
            raise ValueError("One or more commissions are already assigned to a payout batch.")
        currencies.add(row.currency.lower())

    if len(currencies) > 1:
        raise ValueError("All commissions in a payout must use the same currency.")

    return rows


def list_payouts(db: Session) -> list[PayoutListRow]:
    payouts = (
        db.query(CommissionPayout)
        .options(joinedload(CommissionPayout.partner))
        .order_by(CommissionPayout.created_at.desc())
        .all()
    )
    if not payouts:
        return []

    counts = dict(
        db.query(Commission.payout_id, func.count(Commission.id))
        .filter(Commission.payout_id.in_([p.id for p in payouts]))
        .group_by(Commission.payout_id)
        .all()
    )
    return [
        PayoutListRow(
            payout=payout,
            partner=payout.partner,
            commission_count=counts.get(payout.id, 0),
        )
        for payout in payouts
    ]


def get_payout(db: Session, payout_id: uuid.UUID) -> CommissionPayout | None:
    return (
        db.query(CommissionPayout)
        .options(
            joinedload(CommissionPayout.partner),
            joinedload(CommissionPayout.commissions),
        )
        .filter(CommissionPayout.id == payout_id)
        .one_or_none()
    )


def get_partners_with_approved_unpaid_commissions(db: Session) -> list[PartnerApprovedUnpaidSummary]:
    rows = (
        db.query(
            Partner,
            func.count(Commission.id),
            func.coalesce(func.sum(Commission.amount_cents), 0),
        )
        .join(Commission, Commission.partner_id == Partner.id)
        .filter(
            Commission.status == "approved",
            Commission.payout_id.is_(None),
        )
        .group_by(Partner.id)
        .order_by(Partner.display_name.asc())
        .all()
    )
    return [
        PartnerApprovedUnpaidSummary(
            partner=partner,
            approved_count=int(count),
            approved_total_cents=int(total),
        )
        for partner, count, total in rows
    ]


def list_approved_unpaid_commissions_for_partner(
    db: Session,
    *,
    partner_id: uuid.UUID,
) -> list[tuple[Commission, Business | None]]:
    return (
        db.query(Commission, Business)
        .outerjoin(Business, Business.id == Commission.business_id)
        .filter(
            Commission.partner_id == partner_id,
            Commission.status == "approved",
            Commission.payout_id.is_(None),
        )
        .order_by(Commission.created_at.asc())
        .all()
    )


def create_draft_payout(
    db: Session,
    *,
    partner_id: uuid.UUID,
    commission_ids: list[uuid.UUID],
    created_by_user_id: uuid.UUID | None = None,
    notes: str | None = None,
) -> CommissionPayout:
    partner = db.get(Partner, partner_id)
    if partner is None:
        raise ValueError("Partner not found.")

    commissions = _validate_commissions_for_draft(db, partner_id=partner_id, commission_ids=commission_ids)
    total = sum(row.amount_cents for row in commissions)
    currency = commissions[0].currency

    payout = CommissionPayout(
        partner_id=partner_id,
        status="draft",
        total_amount_cents=total,
        currency=currency,
        notes=(notes or "").strip() or None,
        created_by_user_id=created_by_user_id,
    )
    db.add(payout)
    db.flush()

    for row in commissions:
        row.payout_id = payout.id

    db.flush()
    return payout


def mark_payout_paid(
    db: Session,
    *,
    payout_id: uuid.UUID,
    external_reference: str | None = None,
    payment_method_note: str | None = None,
) -> CommissionPayout:
    payout = get_payout(db, payout_id)
    if payout is None:
        raise ValueError("Payout batch not found.")
    if payout.status != "draft":
        raise ValueError("Only draft payout batches can be marked paid.")

    ref = (external_reference or "").strip()
    note = (payment_method_note or "").strip()
    if not ref and not note:
        raise ValueError("Provide a payment reference or payment method note when marking paid.")

    payout.external_reference = ref or None
    payout.payment_method_note = note or None
    payout.status = "paid"
    payout.paid_at = _now()

    commissions = (
        db.query(Commission)
        .filter(Commission.payout_id == payout.id)
        .all()
    )
    if not commissions:
        raise ValueError("Payout batch has no commissions.")

    recalculated = sum(row.amount_cents for row in commissions)
    if recalculated != payout.total_amount_cents:
        payout.total_amount_cents = recalculated

    now = _now()
    for row in commissions:
        if row.status != "approved":
            raise ValueError("All commissions in a payout must be approved before marking paid.")
        row.status = "paid"
        row.paid_at = now

    db.flush()
    return payout


def cancel_draft_payout(db: Session, *, payout_id: uuid.UUID) -> CommissionPayout:
    payout = get_payout(db, payout_id)
    if payout is None:
        raise ValueError("Payout batch not found.")
    if payout.status != "draft":
        raise ValueError("Only draft payout batches can be canceled.")

    (
        db.query(Commission)
        .filter(Commission.payout_id == payout.id)
        .update({Commission.payout_id: None}, synchronize_session=False)
    )
    payout.status = "canceled"
    payout.canceled_at = _now()
    db.flush()
    return payout


def list_payouts_for_partner(db: Session, *, partner_id: uuid.UUID) -> list[PartnerPayoutSummary]:
    payouts = (
        db.query(CommissionPayout)
        .filter(CommissionPayout.partner_id == partner_id)
        .order_by(CommissionPayout.created_at.desc())
        .all()
    )
    if not payouts:
        return []

    payout_ids = [p.id for p in payouts]
    commission_rows = (
        db.query(Commission)
        .filter(Commission.payout_id.in_(payout_ids))
        .all()
    )
    by_payout: dict[uuid.UUID, list[Commission]] = {}
    for row in commission_rows:
        if row.payout_id is not None:
            by_payout.setdefault(row.payout_id, []).append(row)

    summaries: list[PartnerPayoutSummary] = []
    for payout in payouts:
        rows = by_payout.get(payout.id, [])
        type_totals: dict[str, int] = {}
        for row in rows:
            type_totals[row.commission_type] = type_totals.get(row.commission_type, 0) + row.amount_cents
        commission_summaries = [
            (commission_type, type_totals[commission_type], len([r for r in rows if r.commission_type == commission_type]))
            for commission_type in sorted(type_totals.keys())
        ]
        summaries.append(
            PartnerPayoutSummary(
                payout=payout,
                commission_count=len(rows),
                commission_summaries=commission_summaries,
            )
        )
    return summaries


def get_payout_for_partner(
    db: Session,
    *,
    payout_id: uuid.UUID,
    partner_id: uuid.UUID,
) -> CommissionPayout | None:
    return (
        db.query(CommissionPayout)
        .filter(
            CommissionPayout.id == payout_id,
            CommissionPayout.partner_id == partner_id,
        )
        .one_or_none()
    )


def commission_in_draft_payout(db: Session, *, commission: Commission) -> CommissionPayout | None:
    if commission.payout_id is None:
        return None
    payout = db.get(CommissionPayout, commission.payout_id)
    if payout is not None and payout.status == "draft":
        return payout
    return None
