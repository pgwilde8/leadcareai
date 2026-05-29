"""Commission ledger creation from Stripe paid events."""

from __future__ import annotations

import json
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.commission import Commission
from app.models.partner import Partner
from app.models.partner_customer import PartnerCustomer
from app.services import business_lead_checkout_service, commission_service
from app.services.business_lead_checkout_service import ensure_business_from_lead
from app.services.business_lead_service import create_demo_lead
from app.services.stripe_service import CheckoutSessionResult
from app.services.user_service import create_admin_user, create_user


def _login_admin(client: TestClient, db_session: Session, email: str = "admin@example.com") -> None:
    create_admin_user(db_session, email=email, password="admin-secret")
    db_session.commit()
    client.post("/login", data={"email": email, "password": "admin-secret"})


def _setup_referred_business(
    db_session: Session,
    *,
    email: str = "biz@example.com",
    business_name: str = "Commission Biz",
    partner_email: str = "commission-partner@example.com",
    referral_code: str = "LCCOMM01",
) -> tuple[Partner, PartnerCustomer, Business]:
    partner = Partner(
        display_name="Commission Partner",
        email=partner_email,
        phone="+15557770001",
        referral_code=referral_code,
        status="active",
    )
    db_session.add(partner)
    db_session.flush()
    lead, pc = create_demo_lead(
        db_session,
        business_name=business_name,
        contact_name="Owner One",
        email=email,
        phone="+15557779991",
        city="Austin",
        state="TX",
        partner=partner,
        referral_code=partner.referral_code,
    )
    lead.status = "qualified"
    business = ensure_business_from_lead(db_session, lead)
    business.stripe_customer_id = "cus_comm_1"
    business.stripe_subscription_id = "sub_comm_1"
    pc.business_id = business.id
    db_session.commit()
    return partner, pc, business


def _invoice_event(event_id: str, invoice_id: str, *, customer: str = "cus_comm_1", subscription: str = "sub_comm_1") -> dict:
    return {
        "id": event_id,
        "type": "invoice.paid",
        "data": {
            "object": {
                "id": invoice_id,
                "customer": customer,
                "subscription": subscription,
                "amount_paid": 14700,
                "billing_reason": "subscription_cycle",
            }
        },
    }


def _nested_referral_invoice_payload(
    *,
    invoice_id: str,
    partner: Partner,
    pc: PartnerCustomer,
    business: Business,
    customer: str = "cus_early_1",
    billing_reason: str = "subscription_create",
    amount_paid: int = 34600,
) -> dict:
    """Stripe test-mode shape: empty invoice.metadata, nested subscription_details metadata."""
    return {
        "id": invoice_id,
        "customer": customer,
        "metadata": {},
        "amount_paid": amount_paid,
        "billing_reason": billing_reason,
        "parent": {
            "subscription_details": {
                "subscription": "sub_early_1",
                "metadata": {
                    "partner_id": str(partner.id),
                    "referral_code": partner.referral_code,
                    "partner_customer_id": str(pc.id),
                    "business_lead_id": str(pc.business_lead_id),
                    "business_id": str(business.id),
                },
            },
        },
    }


def _nested_referral_invoice_event(event_id: str, invoice_id: str, invoice_object: dict) -> dict:
    return {"id": event_id, "type": "invoice.paid", "data": {"object": invoice_object}}


def test_invoice_paid_for_referred_business_creates_monthly_residual(client: TestClient, db_session: Session) -> None:
    _setup_referred_business(db_session)
    event = _invoice_event("evt_invoice_monthly_1", "in_monthly_1")
    with patch("app.services.stripe_service.construct_webhook_event", return_value=event):
        response = client.post("/webhooks/stripe", content=json.dumps(event).encode())
    assert response.status_code == 200
    rows = db_session.query(Commission).filter(Commission.commission_type == "monthly_residual").all()
    assert len(rows) == 1
    assert rows[0].amount_cents == 2500


def test_first_paid_invoice_creates_activation_bonus_once(client: TestClient, db_session: Session) -> None:
    _setup_referred_business(db_session, email="activation-biz@example.com")
    first = _invoice_event("evt_invoice_activation_1", "in_activation_1")
    second = _invoice_event("evt_invoice_activation_2", "in_activation_2")
    with patch("app.services.stripe_service.construct_webhook_event", side_effect=[first, second]):
        client.post("/webhooks/stripe", content=json.dumps(first).encode())
        client.post("/webhooks/stripe", content=json.dumps(second).encode())

    rows = db_session.query(Commission).filter(Commission.commission_type == "activation_bonus").all()
    assert len(rows) == 1
    assert rows[0].amount_cents == 10000


def test_duplicate_invoice_paid_event_does_not_duplicate_commissions(client: TestClient, db_session: Session) -> None:
    _setup_referred_business(db_session, email="dup-invoice@example.com")
    event = _invoice_event("evt_invoice_dup", "in_dup_1")
    with patch("app.services.stripe_service.construct_webhook_event", return_value=event):
        r1 = client.post("/webhooks/stripe", content=json.dumps(event).encode())
        r2 = client.post("/webhooks/stripe", content=json.dumps(event).encode())
    assert r1.status_code == 200
    assert r2.status_code == 200
    monthly = db_session.query(Commission).filter(Commission.commission_type == "monthly_residual").all()
    assert len(monthly) == 1


def test_six_paid_invoices_creates_retention_bonus_once(client: TestClient, db_session: Session) -> None:
    _setup_referred_business(db_session, email="retention@example.com")
    events = [_invoice_event(f"evt_ret_{idx}", f"in_ret_{idx}") for idx in range(1, 7)]
    with patch("app.services.stripe_service.construct_webhook_event", side_effect=events):
        for event in events:
            response = client.post("/webhooks/stripe", content=json.dumps(event).encode())
            assert response.status_code == 200
    rows = db_session.query(Commission).filter(Commission.commission_type == "retention_bonus").all()
    assert len(rows) == 1


def test_non_referred_business_creates_no_partner_commission(client: TestClient, db_session: Session) -> None:
    business = Business(name="Direct Biz", status="active", stripe_customer_id="cus_direct_1", stripe_subscription_id="sub_direct_1")
    db_session.add(business)
    db_session.commit()
    event = _invoice_event("evt_direct_1", "in_direct_1", customer="cus_direct_1", subscription="sub_direct_1")
    with patch("app.services.stripe_service.construct_webhook_event", return_value=event):
        response = client.post("/webhooks/stripe", content=json.dumps(event).encode())
    assert response.status_code == 200
    assert db_session.query(Commission).count() == 0


def test_demo_lead_without_payment_creates_no_commission(db_session: Session) -> None:
    partner = Partner(
        display_name="No Pay Partner",
        email="nopay-partner@example.com",
        phone="+15557770011",
        referral_code="LCNOPAY1",
        status="active",
    )
    db_session.add(partner)
    db_session.flush()
    create_demo_lead(
        db_session,
        business_name="No Pay Demo",
        contact_name="Demo Owner",
        email="demo-nopay@example.com",
        phone="+15557779911",
        city="Austin",
        state="TX",
        partner=partner,
        referral_code=partner.referral_code,
    )
    db_session.commit()
    assert db_session.query(Commission).count() == 0


@patch("app.services.business_lead_checkout_service.stripe_service.create_growth_checkout_session")
def test_checkout_link_creation_creates_no_commission(
    mock_checkout: patch,
    client: TestClient,
    db_session: Session,
) -> None:
    mock_checkout.return_value = CheckoutSessionResult(
        session_id="cs_comm_test",
        url="https://checkout.stripe.com/c/pay/cs_comm_test",
        customer_id="cus_comm_test",
    )
    partner = Partner(
        display_name="Link Partner",
        email="link-partner@example.com",
        phone="+15557770021",
        referral_code="LCLINK01",
        status="active",
    )
    db_session.add(partner)
    db_session.flush()
    lead, _pc = create_demo_lead(
        db_session,
        business_name="Checkout Link Biz",
        contact_name="Checkout Owner",
        email="checkout-link@example.com",
        phone="+15557779921",
        city="Austin",
        state="TX",
        partner=partner,
        referral_code=partner.referral_code,
        call_forwarding_terms_acknowledged=True,
    )
    lead.status = "qualified"
    db_session.commit()
    _login_admin(client, db_session)
    response = client.post(f"/admin/business-leads/{lead.id}/create-checkout", follow_redirects=False)
    assert response.status_code == 303
    assert db_session.query(Commission).count() == 0


def _seed_commission_for_admin_actions(db_session: Session) -> Commission:
    partner, pc, business = _setup_referred_business(db_session, email="admin-actions@example.com")
    row = Commission(
        partner_id=partner.id,
        business_id=business.id,
        partner_customer_id=pc.id,
        commission_type="monthly_residual",
        amount_cents=2500,
        currency="usd",
        status="pending",
        eligible_at=business.created_at,
    )
    db_session.add(row)
    db_session.commit()
    return row


def test_admin_can_approve_commission(client: TestClient, db_session: Session) -> None:
    row = _seed_commission_for_admin_actions(db_session)
    _login_admin(client, db_session, email="admin-approve@example.com")
    response = client.post(f"/admin/commissions/{row.id}/approve", follow_redirects=False)
    assert response.status_code == 303
    db_session.refresh(row)
    assert row.status == "approved"
    assert row.approved_at is not None


def test_admin_can_mark_approved_commission_paid(client: TestClient, db_session: Session) -> None:
    row = _seed_commission_for_admin_actions(db_session)
    row.status = "approved"
    db_session.commit()
    _login_admin(client, db_session, email="admin-paid@example.com")
    response = client.post(f"/admin/commissions/{row.id}/mark-paid", follow_redirects=False)
    assert response.status_code == 303
    db_session.refresh(row)
    assert row.status == "paid"
    assert row.paid_at is not None


def test_admin_can_cancel_pending_commission(client: TestClient, db_session: Session) -> None:
    row = _seed_commission_for_admin_actions(db_session)
    _login_admin(client, db_session, email="admin-cancel@example.com")
    response = client.post(f"/admin/commissions/{row.id}/cancel", follow_redirects=False)
    assert response.status_code == 303
    db_session.refresh(row)
    assert row.status == "canceled"


def test_partner_dashboard_shows_own_commissions_only(client: TestClient, db_session: Session) -> None:
    p1, pc1, b1 = _setup_referred_business(
        db_session,
        email="partner1biz@example.com",
        business_name="Partner One Biz",
        partner_email="partner-one@example.com",
        referral_code="LCPART1",
    )
    p2, pc2, b2 = _setup_referred_business(
        db_session,
        email="partner2biz@example.com",
        business_name="Partner Two Biz",
        partner_email="partner-two@example.com",
        referral_code="LCPART2",
    )

    create_user(db_session, email=p1.email, password="partner-secret-1", role="partner")
    create_user(db_session, email=p2.email, password="partner-secret-2", role="partner")
    db_session.flush()
    from app.models.user import User

    p1.user_id = db_session.query(User).filter(User.email == p1.email).one().id
    p2.user_id = db_session.query(User).filter(User.email == p2.email).one().id
    db_session.add_all(
        [
            Commission(
                partner_id=p1.id,
                business_id=b1.id,
                partner_customer_id=pc1.id,
                commission_type="monthly_residual",
                amount_cents=2500,
                currency="usd",
                status="pending",
                eligible_at=b1.created_at,
            ),
            Commission(
                partner_id=p2.id,
                business_id=b2.id,
                partner_customer_id=pc2.id,
                commission_type="monthly_residual",
                amount_cents=2500,
                currency="usd",
                status="paid",
                eligible_at=b2.created_at,
            ),
        ]
    )
    db_session.commit()

    client.post("/login", data={"email": p1.email, "password": "partner-secret-1"})
    response = client.get("/partner/dashboard")
    assert response.status_code == 200
    assert "Commissions" in response.text
    assert "Partner One Biz" in response.text
    assert "Partner Two Biz" not in response.text


def test_extract_invoice_referral_metadata_reads_nested_parent_fields() -> None:
    payload = {
        "metadata": {},
        "parent": {
            "subscription_details": {
                "metadata": {
                    "partner_id": "dda1d0ac-e35a-48f9-8db4-1b3a297b1538",
                    "referral_code": "LC58E04477",
                    "partner_customer_id": "22b8d7ef-47ac-47d8-b43e-041a9cd0bc05",
                    "business_id": "e6142660-e9d4-4464-b18a-29aee7ca8405",
                }
            }
        },
    }
    merged = commission_service.extract_invoice_referral_metadata(payload)
    assert merged["partner_id"] == "dda1d0ac-e35a-48f9-8db4-1b3a297b1538"
    assert merged["referral_code"] == "LC58E04477"
    assert merged["partner_customer_id"] == "22b8d7ef-47ac-47d8-b43e-041a9cd0bc05"
    assert merged["business_id"] == "e6142660-e9d4-4464-b18a-29aee7ca8405"


def test_invoice_paid_with_nested_metadata_creates_commissions(
    client: TestClient,
    db_session: Session,
) -> None:
    partner, pc, business = _setup_referred_business(db_session, email="nested-meta@example.com")
    business.stripe_customer_id = None
    business.stripe_subscription_id = None
    pc.status = "referred"
    db_session.commit()

    invoice = _nested_referral_invoice_payload(
        invoice_id="in_nested_1",
        partner=partner,
        pc=pc,
        business=business,
    )
    event = _nested_referral_invoice_event("evt_nested_1", "in_nested_1", invoice)
    with patch("app.services.stripe_service.construct_webhook_event", return_value=event):
        response = client.post("/webhooks/stripe", content=json.dumps(event).encode())
    assert response.status_code == 200

    db_session.refresh(pc)
    assert pc.status == "paying"
    assert pc.business_id == business.id

    rows = (
        db_session.query(Commission)
        .filter(Commission.partner_customer_id == pc.id)
        .order_by(Commission.commission_type)
        .all()
    )
    types = {row.commission_type: row for row in rows}
    assert types["monthly_residual"].amount_cents == 2500
    assert types["monthly_residual"].status == "pending"
    assert types["activation_bonus"].amount_cents == 10000
    assert types["activation_bonus"].status == "pending"


def test_invoice_paid_before_checkout_completed_creates_commissions_from_metadata(
    db_session: Session,
) -> None:
    partner = Partner(
        display_name="Race Partner",
        email="race-partner@example.com",
        phone="+15557770099",
        referral_code="LCRACE01",
        status="active",
    )
    db_session.add(partner)
    db_session.flush()
    lead, pc = create_demo_lead(
        db_session,
        business_name="Race Biz",
        contact_name="Race Owner",
        email="race-biz@example.com",
        phone="+15557779999",
        city="Austin",
        state="TX",
        partner=partner,
        referral_code=partner.referral_code,
    )
    lead.status = "qualified"
    business = ensure_business_from_lead(db_session, lead)
    pc.business_id = business.id
    pc.status = "referred"
    db_session.commit()

    invoice = _nested_referral_invoice_payload(
        invoice_id="in_race_1",
        partner=partner,
        pc=pc,
        business=business,
        customer="cus_race_unlinked",
    )
    business_lead_checkout_service.handle_invoice_paid(
        db_session,
        stripe_event_id="evt_race_invoice",
        invoice_payload=invoice,
    )
    db_session.commit()

    assert db_session.query(Commission).filter(Commission.partner_customer_id == pc.id).count() == 2

    session_payload = {
        "id": "cs_race_1",
        "customer": "cus_race_unlinked",
        "subscription": "sub_early_1",
        "amount_total": 34600,
        "metadata": {
            "business_lead_id": str(lead.id),
            "business_id": str(business.id),
            "partner_customer_id": str(pc.id),
            "partner_id": str(partner.id),
            "referral_code": partner.referral_code,
        },
    }
    business_lead_checkout_service.handle_checkout_session_completed(
        db_session,
        stripe_event_id="evt_race_checkout",
        session_payload=session_payload,
    )
    db_session.commit()

    monthly = db_session.query(Commission).filter(Commission.commission_type == "monthly_residual").all()
    activation = db_session.query(Commission).filter(Commission.commission_type == "activation_bonus").all()
    assert len(monthly) == 1
    assert len(activation) == 1


def test_invoice_paid_replay_backfills_commissions_without_duplicates(
    client: TestClient,
    db_session: Session,
) -> None:
    partner, pc, business = _setup_referred_business(db_session, email="replay@example.com")
    business.stripe_customer_id = None
    business.stripe_subscription_id = None
    db_session.commit()

    invoice = _nested_referral_invoice_payload(
        invoice_id="in_replay_1",
        partner=partner,
        pc=pc,
        business=business,
    )
    event = _nested_referral_invoice_event("evt_replay_1", "in_replay_1", invoice)
    payload = json.dumps(event).encode()

    with patch("app.services.stripe_service.construct_webhook_event", return_value=event):
        first = client.post("/webhooks/stripe", content=payload)
        second = client.post("/webhooks/stripe", content=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert db_session.query(Commission).filter(Commission.partner_customer_id == pc.id).count() == 2


def test_webhook_duplicate_event_ignored(client: TestClient, db_session: Session) -> None:
    _setup_referred_business(db_session, email="dup-event@example.com")
    event = _invoice_event("evt_dup_event", "in_dup_event")
    payload = json.dumps(event).encode()
    with patch("app.services.stripe_service.construct_webhook_event", return_value=event):
        r1 = client.post("/webhooks/stripe", content=payload)
        r2 = client.post("/webhooks/stripe", content=payload)
    assert r1.status_code == 200
    assert r2.status_code == 200
    from app.models.payment_event import PaymentEvent

    rows = db_session.query(PaymentEvent).filter(PaymentEvent.stripe_event_id == "evt_dup_event").all()
    assert len(rows) == 1
