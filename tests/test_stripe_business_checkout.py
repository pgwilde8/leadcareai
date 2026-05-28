"""Stripe business lead checkout and webhooks (Phase 2D)."""

from __future__ import annotations

import json
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.business import Business
from app.models.business_lead import BusinessLead
from app.models.partner import Partner
from app.models.partner_customer import PartnerCustomer
from app.services import business_lead_checkout_service
from app.services.business_lead_service import create_demo_lead
from app.services.partner_document_service import seed_default_document_templates
from app.services.partner_service import approve_application
from app.services.stripe_service import CheckoutSessionResult
from app.services.user_service import create_admin_user


def _login_admin(client: TestClient, db_session: Session) -> None:
    create_admin_user(db_session, email="admin@example.com", password="admin-secret")
    db_session.commit()
    client.post(
        "/login",
        data={"email": "admin@example.com", "password": "admin-secret"},
    )


def _qualified_lead(db_session: Session, **kwargs) -> BusinessLead:
    defaults = {
        "business_name": "Acme HVAC",
        "contact_name": "Jane Owner",
        "email": "checkout@acme.example",
        "phone": "+15551234999",
        "city": "Austin",
        "state": "TX",
    }
    defaults.update(kwargs)
    lead, _ = create_demo_lead(db_session, **defaults)
    lead.status = "qualified"
    db_session.flush()
    return lead


def _referred_lead(db_session: Session) -> tuple[BusinessLead, Partner, PartnerCustomer]:
    seed_default_document_templates(db_session)
    partner = Partner(
        display_name="Ref Partner",
        email="partner-checkout@example.com",
        phone="+15559998888",
        referral_code="LCTESTCODE",
        status="active",
    )
    db_session.add(partner)
    db_session.flush()
    lead, pc = create_demo_lead(
        db_session,
        business_name="Referred Co",
        contact_name="Bob",
        email="referred-co@example.com",
        phone="+15551234888",
        city="Dallas",
        state="TX",
        partner=partner,
        referral_code=partner.referral_code,
    )
    lead.status = "qualified"
    db_session.flush()
    return lead, partner, pc


@patch("app.services.business_lead_checkout_service.stripe_service.create_growth_checkout_session")
def test_admin_can_create_checkout_for_qualified_lead(
    mock_checkout: patch,
    client: TestClient,
    db_session: Session,
) -> None:
    mock_checkout.return_value = CheckoutSessionResult(
        session_id="cs_test_123",
        url="https://checkout.stripe.com/c/pay/cs_test_123",
        customer_id="cus_test_1",
    )
    lead = _qualified_lead(db_session)
    db_session.commit()
    _login_admin(client, db_session)

    response = client.post(
        f"/admin/business-leads/{lead.id}/create-checkout",
        follow_redirects=False,
    )
    assert response.status_code == 303

    db_session.expire_all()
    db_session.refresh(lead)
    assert lead.payment_status == "checkout_created"
    assert lead.stripe_checkout_session_id == "cs_test_123"
    assert lead.stripe_checkout_url.startswith("https://checkout.stripe.com")
    assert lead.converted_business_id is not None


@patch("app.services.business_lead_checkout_service.stripe_service.create_growth_checkout_session")
def test_checkout_creates_business_from_lead(
    mock_checkout: patch,
    client: TestClient,
    db_session: Session,
) -> None:
    mock_checkout.return_value = CheckoutSessionResult(
        session_id="cs_test_456",
        url="https://checkout.stripe.com/c/pay/cs_test_456",
        customer_id="cus_test_2",
    )
    lead = _qualified_lead(db_session, email="biz-from-lead@example.com")
    db_session.commit()
    _login_admin(client, db_session)
    client.post(f"/admin/business-leads/{lead.id}/create-checkout")

    db_session.expire_all()
    lead = db_session.get(BusinessLead, lead.id)
    business = db_session.get(Business, lead.converted_business_id)
    assert business is not None
    assert business.name == "Acme HVAC"
    assert business.status == "pending"
    assert business.main_phone == "+15551234999"


@patch("app.services.business_lead_checkout_service.stripe_service.create_growth_checkout_session")
def test_checkout_metadata_includes_referral_info(
    mock_checkout: patch,
    client: TestClient,
    db_session: Session,
) -> None:
    mock_checkout.return_value = CheckoutSessionResult(
        session_id="cs_test_meta",
        url="https://checkout.stripe.com/c/pay/cs_test_meta",
    )
    lead, partner, pc = _referred_lead(db_session)
    db_session.commit()
    _login_admin(client, db_session)
    client.post(f"/admin/business-leads/{lead.id}/create-checkout")

    assert mock_checkout.called
    metadata = mock_checkout.call_args.kwargs["metadata"]
    assert metadata["business_lead_id"] == str(lead.id)
    assert metadata["partner_id"] == str(partner.id)
    assert metadata["referral_code"] == partner.referral_code
    assert metadata["partner_customer_id"] == str(pc.id)


@patch("app.services.business_lead_checkout_service.stripe_service.create_growth_checkout_session")
def test_referred_lead_links_partner_customer_to_business(
    mock_checkout: patch,
    client: TestClient,
    db_session: Session,
) -> None:
    mock_checkout.return_value = CheckoutSessionResult(
        session_id="cs_test_pc",
        url="https://checkout.stripe.com/c/pay/cs_test_pc",
    )
    lead, _, pc = _referred_lead(db_session)
    db_session.commit()
    _login_admin(client, db_session)
    client.post(f"/admin/business-leads/{lead.id}/create-checkout")

    db_session.expire_all()
    pc = db_session.get(PartnerCustomer, pc.id)
    assert pc.business_id is not None


@patch("app.services.business_lead_checkout_service.stripe_service.create_growth_checkout_session")
def test_duplicate_checkout_does_not_create_duplicate_business(
    mock_checkout: patch,
    client: TestClient,
    db_session: Session,
) -> None:
    mock_checkout.return_value = CheckoutSessionResult(
        session_id="cs_test_dup",
        url="https://checkout.stripe.com/c/pay/cs_test_dup",
    )
    lead = _qualified_lead(db_session, email="dup-biz@example.com")
    db_session.commit()
    _login_admin(client, db_session)

    client.post(f"/admin/business-leads/{lead.id}/create-checkout")
    client.post(f"/admin/business-leads/{lead.id}/create-checkout")

    businesses = db_session.query(Business).filter(Business.name == "Acme HVAC").all()
    assert len(businesses) == 1
    assert mock_checkout.call_count == 1


def test_rejected_lead_cannot_create_checkout(
    client: TestClient,
    db_session: Session,
) -> None:
    lead = _qualified_lead(db_session, email="rejected@example.com")
    lead.status = "rejected"
    db_session.commit()
    _login_admin(client, db_session)

    response = client.post(f"/admin/business-leads/{lead.id}/create-checkout")
    assert response.status_code == 400
    assert "rejected" in response.text.lower()


def test_new_lead_cannot_create_checkout(
    client: TestClient,
    db_session: Session,
) -> None:
    lead = _qualified_lead(db_session, email="newonly@example.com")
    lead.status = "new"
    db_session.commit()
    _login_admin(client, db_session)

    response = client.post(f"/admin/business-leads/{lead.id}/create-checkout")
    assert response.status_code == 400


def test_checkout_session_completed_marks_lead_paid_and_converted(
    db_session: Session,
) -> None:
    lead = _qualified_lead(db_session, email="paid@example.com")
    business = business_lead_checkout_service.ensure_business_from_lead(db_session, lead)
    lead.stripe_checkout_session_id = "cs_paid_1"
    lead.payment_status = "checkout_created"
    db_session.commit()

    session_payload = {
        "id": "cs_paid_1",
        "customer": "cus_paid_1",
        "subscription": "sub_paid_1",
        "amount_total": 34600,
        "metadata": {
            "business_lead_id": str(lead.id),
            "business_id": str(business.id),
        },
    }
    business_lead_checkout_service.handle_checkout_session_completed(
        db_session,
        stripe_event_id="evt_test_checkout_1",
        session_payload=session_payload,
    )
    db_session.commit()

    db_session.refresh(lead)
    db_session.refresh(business)
    assert lead.payment_status == "paid"
    assert lead.status == "converted"
    assert lead.converted_at is not None
    assert business.status == "active"
    assert business.stripe_customer_id == "cus_paid_1"
    assert business.stripe_subscription_id == "sub_paid_1"


def test_checkout_session_completed_updates_partner_customer(
    db_session: Session,
) -> None:
    lead, _, pc = _referred_lead(db_session)
    business = business_lead_checkout_service.ensure_business_from_lead(db_session, lead)
    pc.business_id = business.id
    db_session.commit()

    session_payload = {
        "metadata": {
            "business_lead_id": str(lead.id),
            "business_id": str(business.id),
            "partner_customer_id": str(pc.id),
        },
        "customer": "cus_pc",
        "subscription": "sub_pc",
    }
    business_lead_checkout_service.handle_checkout_session_completed(
        db_session,
        stripe_event_id="evt_test_checkout_2",
        session_payload=session_payload,
    )
    db_session.commit()

    db_session.refresh(pc)
    assert pc.status == "paying"
    assert pc.business_id == business.id


def test_webhook_checkout_completed_idempotent(
    client: TestClient,
    db_session: Session,
) -> None:
    lead = _qualified_lead(db_session, email="webhook@example.com")
    business = business_lead_checkout_service.ensure_business_from_lead(db_session, lead)
    db_session.commit()

    event = {
        "id": "evt_webhook_idem",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "metadata": {
                    "business_lead_id": str(lead.id),
                    "business_id": str(business.id),
                },
                "customer": "cus_wh",
                "subscription": "sub_wh",
            }
        },
    }
    payload = json.dumps(event).encode()

    with patch("app.services.stripe_service.construct_webhook_event", return_value=event):
        r1 = client.post("/webhooks/stripe", content=payload)
        r2 = client.post("/webhooks/stripe", content=payload)

    assert r1.status_code == 200
    assert r2.status_code == 200

    from app.models.payment_event import PaymentEvent

    events = (
        db_session.query(PaymentEvent)
        .filter(PaymentEvent.stripe_event_id == "evt_webhook_idem")
        .all()
    )
    assert len(events) == 1
