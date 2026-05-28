"""Manual partner payout batch workflow (Phase 2J)."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.field_encryption import encrypt_field
from app.models.commission import Commission
from app.models.commission_payout import CommissionPayout
from app.models.partner import Partner
from app.models.partner_application import PartnerApplication
from app.models.partner_tax_info import PartnerTaxInfo
from app.services import commission_payout_service, commission_service
from app.services.user_service import create_admin_user, create_user
from tests.test_commission_ledger import _setup_referred_business


def _login_admin(client: TestClient, db_session: Session, email: str = "admin@example.com") -> None:
    create_admin_user(db_session, email=email, password="admin-secret")
    db_session.commit()
    client.post("/login", data={"email": email, "password": "admin-secret"})


def _approved_commissions(
    db_session: Session,
    *,
    partner: Partner,
    business_id: uuid.UUID,
    partner_customer_id: uuid.UUID,
    count: int = 2,
) -> list[Commission]:
    rows: list[Commission] = []
    for idx in range(count):
        row = Commission(
            partner_id=partner.id,
            business_id=business_id,
            partner_customer_id=partner_customer_id,
            commission_type="monthly_residual",
            amount_cents=2500 + idx * 100,
            currency="usd",
            status="approved",
            eligible_at=partner.created_at,
        )
        db_session.add(row)
        rows.append(row)
    db_session.commit()
    return rows


def test_admin_can_create_draft_payout_from_approved_commissions(
    client: TestClient,
    db_session: Session,
) -> None:
    partner, pc, business = _setup_referred_business(db_session, email="payout-create@example.com")
    commissions = _approved_commissions(db_session, partner=partner, business_id=business.id, partner_customer_id=pc.id)
    _login_admin(client, db_session, email="admin-payout-create@example.com")

    response = client.post(
        "/admin/payouts",
        data={
            "partner_id": str(partner.id),
            "commission_ids": [str(commissions[0].id), str(commissions[1].id)],
            "notes": "January manual ACH",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "/admin/payouts/" in response.headers["location"]

    payout = db_session.query(CommissionPayout).one()
    assert payout.status == "draft"
    assert payout.total_amount_cents == 5100
    assert payout.notes == "January manual ACH"
    for row in commissions:
        db_session.refresh(row)
        assert row.payout_id == payout.id


def test_pending_commission_cannot_be_included(client: TestClient, db_session: Session) -> None:
    partner, pc, business = _setup_referred_business(db_session, email="payout-pending@example.com")
    pending = Commission(
        partner_id=partner.id,
        business_id=business.id,
        partner_customer_id=pc.id,
        commission_type="monthly_residual",
        amount_cents=2500,
        currency="usd",
        status="pending",
        eligible_at=partner.created_at,
    )
    db_session.add(pending)
    db_session.commit()
    _login_admin(client, db_session, email="admin-payout-pending@example.com")

    response = client.post(
        "/admin/payouts",
        data={"partner_id": str(partner.id), "commission_ids": [str(pending.id)]},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "error=" in response.headers["location"]
    assert db_session.query(CommissionPayout).count() == 0


def test_paid_commission_cannot_be_included(client: TestClient, db_session: Session) -> None:
    partner, pc, business = _setup_referred_business(db_session, email="payout-paid@example.com")
    paid = Commission(
        partner_id=partner.id,
        business_id=business.id,
        partner_customer_id=pc.id,
        commission_type="monthly_residual",
        amount_cents=2500,
        currency="usd",
        status="paid",
        eligible_at=partner.created_at,
    )
    db_session.add(paid)
    db_session.commit()
    _login_admin(client, db_session, email="admin-payout-paid@example.com")

    response = client.post(
        "/admin/payouts",
        data={"partner_id": str(partner.id), "commission_ids": [str(paid.id)]},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert db_session.query(CommissionPayout).count() == 0


def test_mark_payout_paid_updates_commissions(client: TestClient, db_session: Session) -> None:
    partner, pc, business = _setup_referred_business(db_session, email="payout-mark@example.com")
    commissions = _approved_commissions(db_session, partner=partner, business_id=business.id, partner_customer_id=pc.id, count=1)
    payout = commission_payout_service.create_draft_payout(
        db_session,
        partner_id=partner.id,
        commission_ids=[commissions[0].id],
    )
    db_session.commit()
    _login_admin(client, db_session, email="admin-payout-mark@example.com")

    response = client.post(
        f"/admin/payouts/{payout.id}/mark-paid",
        data={"external_reference": "ACH-12345", "payment_method_note": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303
    db_session.refresh(payout)
    db_session.refresh(commissions[0])
    assert payout.status == "paid"
    assert payout.paid_at is not None
    assert commissions[0].status == "paid"
    assert commissions[0].paid_at is not None


def test_cancel_draft_payout_detaches_commissions(client: TestClient, db_session: Session) -> None:
    partner, pc, business = _setup_referred_business(db_session, email="payout-cancel@example.com")
    commissions = _approved_commissions(db_session, partner=partner, business_id=business.id, partner_customer_id=pc.id, count=1)
    payout = commission_payout_service.create_draft_payout(
        db_session,
        partner_id=partner.id,
        commission_ids=[commissions[0].id],
    )
    db_session.commit()
    _login_admin(client, db_session, email="admin-payout-cancel@example.com")

    response = client.post(f"/admin/payouts/{payout.id}/cancel", follow_redirects=False)
    assert response.status_code == 303
    db_session.refresh(payout)
    db_session.refresh(commissions[0])
    assert payout.status == "canceled"
    assert commissions[0].payout_id is None
    assert commissions[0].status == "approved"


def test_commission_in_draft_payout_cannot_mark_paid_individually(db_session: Session) -> None:
    partner, pc, business = _setup_referred_business(db_session, email="payout-block@example.com")
    commissions = _approved_commissions(db_session, partner=partner, business_id=business.id, partner_customer_id=pc.id, count=1)
    commission_payout_service.create_draft_payout(
        db_session,
        partner_id=partner.id,
        commission_ids=[commissions[0].id],
    )
    db_session.commit()
    with pytest.raises(ValueError, match="draft payout batch"):
        commission_service.update_commission_status(
            db_session,
            commission_id=commissions[0].id,
            action="mark_paid",
        )


def test_commission_cannot_join_two_payouts(db_session: Session) -> None:
    partner, pc, business = _setup_referred_business(db_session, email="payout-dup@example.com")
    commissions = _approved_commissions(db_session, partner=partner, business_id=business.id, partner_customer_id=pc.id, count=1)
    commission_payout_service.create_draft_payout(
        db_session,
        partner_id=partner.id,
        commission_ids=[commissions[0].id],
    )
    db_session.commit()
    with pytest.raises(ValueError, match="already assigned"):
        commission_payout_service.create_draft_payout(
            db_session,
            partner_id=partner.id,
            commission_ids=[commissions[0].id],
        )


def test_individual_mark_paid_still_works_without_payout(client: TestClient, db_session: Session) -> None:
    partner, pc, business = _setup_referred_business(db_session, email="payout-fallback@example.com")
    row = _approved_commissions(db_session, partner=partner, business_id=business.id, partner_customer_id=pc.id, count=1)[0]
    _login_admin(client, db_session, email="admin-payout-fallback@example.com")
    response = client.post(f"/admin/commissions/{row.id}/mark-paid", follow_redirects=False)
    assert response.status_code == 303
    db_session.refresh(row)
    assert row.status == "paid"


def test_partner_payouts_shows_own_history_only(client: TestClient, db_session: Session) -> None:
    p1, pc1, b1 = _setup_referred_business(
        db_session,
        email="payout-p1@example.com",
        partner_email="partner-payout-one@example.com",
        referral_code="LCPAY1",
    )
    p2, pc2, b2 = _setup_referred_business(
        db_session,
        email="payout-p2@example.com",
        partner_email="partner-payout-two@example.com",
        referral_code="LCPAY2",
    )
    c1 = _approved_commissions(db_session, partner=p1, business_id=b1.id, partner_customer_id=pc1.id, count=1)[0]
    commission_payout_service.create_draft_payout(db_session, partner_id=p1.id, commission_ids=[c1.id])
    commission_payout_service.mark_payout_paid(
        db_session,
        payout_id=db_session.query(CommissionPayout).filter_by(partner_id=p1.id).one().id,
        external_reference="REF-1",
    )
    db_session.commit()

    create_user(db_session, email=p1.email, password="partner-secret", role="partner")
    db_session.flush()
    from app.models.user import User

    p1.user_id = db_session.query(User).filter(User.email == p1.email).one().id
    db_session.commit()

    client.post("/login", data={"email": p1.email, "password": "partner-secret"})
    response = client.get("/partner/payouts")
    assert response.status_code == 200
    assert "paid" in response.text
    assert p2.display_name not in response.text
    assert "tin_encrypted" not in response.text.lower()


def test_non_admin_cannot_access_admin_payouts(client: TestClient, db_session: Session) -> None:
    create_user(db_session, email="biz-user@example.com", password="secret", role="business_user")
    db_session.commit()
    client.post("/login", data={"email": "biz-user@example.com", "password": "secret"})
    response = client.get("/admin/payouts", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_admin_payout_detail_shows_masked_tin_only(client: TestClient, db_session: Session) -> None:
    partner, pc, business = _setup_referred_business(db_session, email="payout-tax@example.com")
    application = PartnerApplication(
        first_name="Tax",
        last_name="Partner",
        email=partner.email,
        phone=partner.phone,
        city="Austin",
        state="TX",
        status="approved",
    )
    db_session.add(application)
    db_session.flush()
    partner.application_id = application.id
    db_session.add(
        PartnerTaxInfo(
            application_id=application.id,
            legal_name="Tax Partner LLC",
            business_name=None,
            address_line1="1 Main",
            address_line2=None,
            city="Austin",
            state="TX",
            postal_code="78701",
            tax_classification="individual",
            tin_type="ssn",
            tin_encrypted=encrypt_field("123456789"),
            certified_at=partner.created_at,
        )
    )
    commissions = _approved_commissions(db_session, partner=partner, business_id=business.id, partner_customer_id=pc.id, count=1)
    payout = commission_payout_service.create_draft_payout(
        db_session,
        partner_id=partner.id,
        commission_ids=[commissions[0].id],
    )
    db_session.commit()
    _login_admin(client, db_session, email="admin-payout-tax@example.com")

    detail = client.get(f"/admin/payouts/{payout.id}")
    assert detail.status_code == 200
    assert "TIN (masked)" in detail.text
    assert "***" in detail.text
    assert "123456789" not in detail.text
    assert "tin_encrypted" not in detail.text.lower()
