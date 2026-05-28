"""Stripe refund, cancellation, and payment-failure protection for commissions."""

from __future__ import annotations

import json
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.commission import Commission
from app.models.partner import Partner
from app.models.partner_customer import PartnerCustomer
from app.services.business_lead_checkout_service import ensure_business_from_lead
from app.services.business_lead_service import create_demo_lead
from app.services.commission_service import REFUND_REVIEW_NOTE
from app.services.user_service import create_admin_user


def _setup_referred_paying(
    db_session: Session,
    *,
    email: str = "paying@example.com",
) -> tuple[Partner, PartnerCustomer, Business]:
    partner = Partner(
        display_name="Refund Partner",
        email="refund-partner@example.com",
        phone="+15558880001",
        referral_code="LCREFUND1",
        status="active",
    )
    db_session.add(partner)
    db_session.flush()
    lead, pc = create_demo_lead(
        db_session,
        business_name="Refund Biz",
        contact_name="Owner",
        email=email,
        phone="+15558889991",
        city="Austin",
        state="TX",
        partner=partner,
        referral_code=partner.referral_code,
    )
    lead.status = "qualified"
    lead.payment_status = "paid"
    business = ensure_business_from_lead(db_session, lead)
    business.status = "active"
    business.stripe_customer_id = "cus_refund_1"
    business.stripe_subscription_id = "sub_refund_1"
    pc.business_id = business.id
    pc.status = "paying"
    db_session.commit()
    return partner, pc, business


def _paid_invoice_event(event_id: str, invoice_id: str) -> dict:
    return {
        "id": event_id,
        "type": "invoice.paid",
        "data": {
            "object": {
                "id": invoice_id,
                "customer": "cus_refund_1",
                "subscription": "sub_refund_1",
                "amount_paid": 14700,
                "billing_reason": "subscription_cycle",
            }
        },
    }


def _payment_failed_event(event_id: str, invoice_id: str = "in_failed_1") -> dict:
    return {
        "id": event_id,
        "type": "invoice.payment_failed",
        "data": {
            "object": {
                "id": invoice_id,
                "customer": "cus_refund_1",
                "subscription": "sub_refund_1",
            }
        },
    }


def _subscription_deleted_event(event_id: str) -> dict:
    return {
        "id": event_id,
        "type": "customer.subscription.deleted",
        "data": {
            "object": {
                "id": "sub_refund_1",
                "customer": "cus_refund_1",
                "status": "canceled",
            }
        },
    }


def _charge_refunded_event(event_id: str, invoice_id: str) -> dict:
    return {
        "id": event_id,
        "type": "charge.refunded",
        "data": {
            "object": {
                "id": "ch_refund_1",
                "customer": "cus_refund_1",
                "invoice": invoice_id,
            }
        },
    }


def test_invoice_payment_failed_does_not_create_commission(client: TestClient, db_session: Session) -> None:
    _setup_referred_paying(db_session)
    event = _payment_failed_event("evt_pay_fail_1")
    with patch("app.services.stripe_service.construct_webhook_event", return_value=event):
        response = client.post("/webhooks/stripe", content=json.dumps(event).encode())
    assert response.status_code == 200
    assert db_session.query(Commission).count() == 0


def test_invoice_payment_failed_updates_business_and_partner_customer(
    client: TestClient,
    db_session: Session,
) -> None:
    _partner, pc, business = _setup_referred_paying(db_session)
    event = _payment_failed_event("evt_pay_fail_status")
    with patch("app.services.stripe_service.construct_webhook_event", return_value=event):
        client.post("/webhooks/stripe", content=json.dumps(event).encode())
    db_session.refresh(business)
    db_session.refresh(pc)
    assert business.status == "past_due"
    assert pc.status == "payment_failed"


def test_subscription_deleted_marks_business_and_customer_canceled(
    client: TestClient,
    db_session: Session,
) -> None:
    _partner, pc, business = _setup_referred_paying(db_session)
    event = _subscription_deleted_event("evt_sub_del_1")
    with patch("app.services.stripe_service.construct_webhook_event", return_value=event):
        response = client.post("/webhooks/stripe", content=json.dumps(event).encode())
    assert response.status_code == 200
    db_session.refresh(business)
    db_session.refresh(pc)
    assert business.status == "canceled"
    assert pc.status == "canceled"


def test_charge_refunded_cancels_pending_commission(client: TestClient, db_session: Session) -> None:
    partner, pc, business = _setup_referred_paying(db_session, email="pending-refund@example.com")
    paid = _paid_invoice_event("evt_paid_pending", "in_pending_refund")
    with patch("app.services.stripe_service.construct_webhook_event", return_value=paid):
        client.post("/webhooks/stripe", content=json.dumps(paid).encode())
    row = db_session.query(Commission).filter(Commission.commission_type == "monthly_residual").one()
    assert row.status == "pending"

    refund = _charge_refunded_event("evt_refund_pending", "in_pending_refund")
    with patch("app.services.stripe_service.construct_webhook_event", return_value=refund):
        client.post("/webhooks/stripe", content=json.dumps(refund).encode())
    db_session.refresh(row)
    assert row.status == "canceled"


def test_charge_refunded_cancels_approved_commission(client: TestClient, db_session: Session) -> None:
    _setup_referred_paying(db_session, email="approved-refund@example.com")
    paid = _paid_invoice_event("evt_paid_approved", "in_approved_refund")
    with patch("app.services.stripe_service.construct_webhook_event", return_value=paid):
        client.post("/webhooks/stripe", content=json.dumps(paid).encode())
    row = db_session.query(Commission).filter(Commission.commission_type == "monthly_residual").one()
    row.status = "approved"
    db_session.commit()

    refund = _charge_refunded_event("evt_refund_approved", "in_approved_refund")
    with patch("app.services.stripe_service.construct_webhook_event", return_value=refund):
        client.post("/webhooks/stripe", content=json.dumps(refund).encode())
    db_session.refresh(row)
    assert row.status == "canceled"


def test_charge_refunded_flags_paid_commission_for_review(client: TestClient, db_session: Session) -> None:
    _setup_referred_paying(db_session, email="paid-refund@example.com")
    paid = _paid_invoice_event("evt_paid_flag", "in_paid_refund")
    with patch("app.services.stripe_service.construct_webhook_event", return_value=paid):
        client.post("/webhooks/stripe", content=json.dumps(paid).encode())
    row = db_session.query(Commission).filter(Commission.commission_type == "monthly_residual").one()
    row.status = "paid"
    db_session.commit()

    refund = _charge_refunded_event("evt_refund_paid", "in_paid_refund")
    with patch("app.services.stripe_service.construct_webhook_event", return_value=refund):
        client.post("/webhooks/stripe", content=json.dumps(refund).encode())
    db_session.refresh(row)
    assert row.status == "paid"
    assert REFUND_REVIEW_NOTE in (row.notes or "")


def test_duplicate_refund_event_does_not_double_process(client: TestClient, db_session: Session) -> None:
    _setup_referred_paying(db_session, email="dup-refund@example.com")
    paid = _paid_invoice_event("evt_paid_dup_ref", "in_dup_refund")
    with patch("app.services.stripe_service.construct_webhook_event", return_value=paid):
        client.post("/webhooks/stripe", content=json.dumps(paid).encode())
    refund = _charge_refunded_event("evt_refund_dup", "in_dup_refund")
    payload = json.dumps(refund).encode()
    with patch("app.services.stripe_service.construct_webhook_event", return_value=refund):
        r1 = client.post("/webhooks/stripe", content=payload)
        r2 = client.post("/webhooks/stripe", content=payload)
    assert r1.status_code == 200
    assert r2.status_code == 200
    from app.models.payment_event import PaymentEvent

    events = db_session.query(PaymentEvent).filter(PaymentEvent.stripe_event_id == "evt_refund_dup").all()
    assert len(events) == 1


def test_non_referred_business_refund_does_not_crash(client: TestClient, db_session: Session) -> None:
    business = Business(
        name="Direct Refund Biz",
        status="active",
        stripe_customer_id="cus_direct_refund",
    )
    db_session.add(business)
    db_session.commit()
    refund = {
        "id": "evt_direct_refund",
        "type": "charge.refunded",
        "data": {"object": {"id": "ch_direct", "customer": "cus_direct_refund", "invoice": "in_direct"}},
    }
    with patch("app.services.stripe_service.construct_webhook_event", return_value=refund):
        response = client.post("/webhooks/stripe", content=json.dumps(refund).encode())
    assert response.status_code == 200
    assert db_session.query(Commission).count() == 0


def test_partner_dashboard_shows_canceled_status_clearly(
    client: TestClient,
    db_session: Session,
) -> None:
    from app.services.user_service import create_user

    partner, pc, business = _setup_referred_paying(db_session, email="partner-cancel@example.com")
    user = create_user(db_session, email=partner.email, password="partner-secret", role="partner")
    partner.user_id = user.id
    row = Commission(
        partner_id=partner.id,
        business_id=business.id,
        partner_customer_id=pc.id,
        commission_type="monthly_residual",
        amount_cents=2500,
        currency="usd",
        status="canceled",
        eligible_at=business.created_at,
        notes="Subscription canceled; unpaid commissions canceled.",
    )
    db_session.add(row)
    db_session.commit()
    client.post("/login", data={"email": partner.email, "password": "partner-secret"})
    response = client.get("/partner/dashboard")
    assert response.status_code == 200
    assert "canceled" in response.text
    assert "Not payable" in response.text


def test_admin_commissions_page_shows_refund_review_notes(
    client: TestClient,
    db_session: Session,
) -> None:
    partner, pc, business = _setup_referred_paying(db_session, email="admin-notes@example.com")
    row = Commission(
        partner_id=partner.id,
        business_id=business.id,
        partner_customer_id=pc.id,
        commission_type="monthly_residual",
        amount_cents=2500,
        currency="usd",
        status="paid",
        eligible_at=business.created_at,
        notes=f"{REFUND_REVIEW_NOTE} (Stripe charge refunded.)",
    )
    db_session.add(row)
    db_session.commit()
    create_admin_user(db_session, email="admin-refund@example.com", password="admin-secret")
    db_session.commit()
    client.post("/login", data={"email": "admin-refund@example.com", "password": "admin-secret"})
    response = client.get("/admin/commissions")
    assert response.status_code == 200
    assert "Review for clawback" in response.text
    assert REFUND_REVIEW_NOTE in response.text
