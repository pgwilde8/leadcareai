"""Admin compliance routes (SQLite)."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services.business_service import create_business
from app.services.user_service import create_admin_user


def _login_admin(client: TestClient, db_session: Session) -> None:
    create_admin_user(db_session, email="admin@example.com", password="admin-secret")
    db_session.commit()
    client.post(
        "/login",
        data={"email": "admin@example.com", "password": "admin-secret"},
    )


def _compliance_form_data(**overrides: str) -> dict[str, str]:
    data = {
        "legal_business_name": "",
        "dba_name": "",
        "business_type": "",
        "ein": "",
        "website_url": "",
        "business_phone": "",
        "business_email": "",
        "address_line1": "",
        "address_line2": "",
        "city": "",
        "state": "",
        "postal_code": "",
        "country": "US",
        "authorized_rep_name": "",
        "authorized_rep_title": "",
        "authorized_rep_email": "",
        "sms_use_case": "",
        "opt_in_description": "",
        "sample_message_1": "",
        "sample_message_2": "",
        "privacy_policy_url": "",
        "terms_url": "",
        "twilio_brand_sid": "",
        "twilio_campaign_sid": "",
    }
    data.update(overrides)
    return data


def test_admin_can_view_compliance_page(
    client: TestClient,
    db_session: Session,
) -> None:
    _login_admin(client, db_session)
    business = create_business(db_session, name="Compliance View Co")
    db_session.commit()

    response = client.get(f"/admin/businesses/{business.id}/compliance")
    assert response.status_code == 200
    assert "SMS compliance" in response.text
    assert "A2P 10DLC submission coming later" in response.text


def test_compliance_page_creates_or_loads_profile(
    client: TestClient,
    db_session: Session,
) -> None:
    _login_admin(client, db_session)
    business = create_business(db_session, name="Auto Profile Co")
    db_session.commit()

    response = client.get(f"/admin/businesses/{business.id}/compliance")
    assert response.status_code == 200
    assert "not_started" in response.text


def test_admin_can_save_compliance_fields(
    client: TestClient,
    db_session: Session,
) -> None:
    _login_admin(client, db_session)
    business = create_business(db_session, name="Save Compliance Co")
    db_session.commit()

    response = client.post(
        f"/admin/businesses/{business.id}/compliance",
        data=_compliance_form_data(
            legal_business_name="Save Compliance LLC",
            twilio_brand_sid="BN123",
            twilio_campaign_sid="CM456",
        ),
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == f"/admin/businesses/{business.id}"

    detail = client.get(response.headers["location"])
    assert detail.status_code == 200
    assert "Save Compliance LLC" in detail.text
    assert "BN123" in detail.text
    assert "CM456" in detail.text


def test_business_detail_shows_compliance_status(
    client: TestClient,
    db_session: Session,
) -> None:
    _login_admin(client, db_session)
    business = create_business(db_session, name="Detail Status Co")
    db_session.commit()

    client.get(f"/admin/businesses/{business.id}/compliance")

    detail = client.get(f"/admin/businesses/{business.id}")
    assert detail.status_code == 200
    assert "SMS compliance" in detail.text
    assert "not_started" in detail.text


@pytest.mark.parametrize(
    "status",
    ["needs_review", "submitted", "approved", "rejected"],
)
def test_admin_can_update_compliance_status(
    client: TestClient,
    db_session: Session,
    status: str,
) -> None:
    _login_admin(client, db_session)
    business = create_business(db_session, name=f"Status {status} Co")
    db_session.commit()

    client.get(f"/admin/businesses/{business.id}/compliance")

    data: dict[str, str] = {"status": status}
    if status == "rejected":
        data["rejection_reason"] = "Missing opt-in proof"

    response = client.post(
        f"/admin/businesses/{business.id}/compliance/status",
        data=data,
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == f"/admin/businesses/{business.id}/compliance"

    page = client.get(response.headers["location"])
    assert page.status_code == 200
    assert status in page.text
    if status == "rejected":
        assert "Missing opt-in proof" in page.text


def test_invalid_compliance_status_is_handled_cleanly(
    client: TestClient,
    db_session: Session,
) -> None:
    _login_admin(client, db_session)
    business = create_business(db_session, name="Invalid Status Co")
    db_session.commit()

    client.get(f"/admin/businesses/{business.id}/compliance")

    response = client.post(
        f"/admin/businesses/{business.id}/compliance/status",
        data={"status": "not_a_real_status", "rejection_reason": ""},
    )
    assert response.status_code == 400
    assert "Invalid compliance status" in response.text


def test_unauthenticated_user_cannot_access_compliance_page(
    client: TestClient,
    db_session: Session,
) -> None:
    business = create_business(db_session, name="Auth Gate Co")
    db_session.commit()

    response = client.get(
        f"/admin/businesses/{business.id}/compliance",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_compliance_page_for_missing_business_redirects(
    client: TestClient,
    db_session: Session,
) -> None:
    _login_admin(client, db_session)

    response = client.get(
        f"/admin/businesses/{uuid.uuid4()}/compliance",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/admin/businesses"
