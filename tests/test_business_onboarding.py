"""Admin business onboarding checklist (Phase 3E)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.business import Business
from app.services import business_onboarding_service
from app.services.business_service import create_business, link_user_to_business
from app.services.business_lead_service import create_demo_lead
from app.services.lead_service import create_lead
from app.services.phone_number_service import create_phone_number, list_phone_numbers_for_business
from app.services.user_service import create_admin_user, create_user


def _login_admin(client: TestClient, db_session: Session) -> None:
    create_admin_user(db_session, email="admin@example.com", password="admin-secret")
    db_session.commit()
    client.post(
        "/login",
        data={"email": "admin@example.com", "password": "admin-secret"},
    )


def _launch_ready_business(db_session: Session) -> Business:
    business = create_business(db_session, name="Launch Ready Co")
    business.status = "active"
    business.notification_email = "alerts@launchready.example"
    business.customer_phone_carrier = "verizon"
    business.customer_phone_is_mobile = True
    business.customer_phone_forwarding_status = "test_passed"
    create_phone_number(
        db_session,
        business.id,
        "+15551112233",
        status="active",
    )
    user = create_user(
        db_session,
        email="owner@launchready.example",
        password="owner-secret",
        role="business_user",
    )
    link_user_to_business(db_session, user.id, business.id)
    lead, _ = create_demo_lead(
        db_session,
        business_name="Launch Ready Co",
        contact_name="Owner",
        email="owner@launchready.example",
        phone="+15551112233",
        city="Austin",
        state="TX",
        call_forwarding_terms_acknowledged=True,
    )
    lead.converted_business_id = business.id
    lead.payment_status = "paid"
    db_session.flush()
    return business


def test_checklist_shows_missing_twilio_when_none_assigned(db_session: Session) -> None:
    business = create_business(db_session, name="No Phone Co")
    checklist = business_onboarding_service.build_business_onboarding_checklist(db_session, business)
    item = next(i for i in checklist.items if i.key == "twilio_number_assigned")
    assert item.status == "missing"


def test_checklist_shows_twilio_assigned_when_active_number_exists(db_session: Session) -> None:
    business = create_business(db_session, name="Has Phone Co")
    create_phone_number(db_session, business.id, "+15559998877", status="active")
    db_session.flush()
    checklist = business_onboarding_service.build_business_onboarding_checklist(db_session, business)
    item = next(i for i in checklist.items if i.key == "twilio_number_assigned")
    assert item.status == "complete"


def test_checklist_shows_forwarding_incomplete_until_test_passed(db_session: Session) -> None:
    business = create_business(db_session, name="Fwd Co")
    business.customer_phone_forwarding_status = "instructions_sent"
    checklist = business_onboarding_service.build_business_onboarding_checklist(db_session, business)
    item = next(i for i in checklist.items if i.key == "forwarding_test_passed")
    assert item.status == "manual"
    assert not checklist.ready_for_launch


def test_checklist_ready_only_when_required_items_complete(db_session: Session) -> None:
    business = _launch_ready_business(db_session)
    db_session.commit()
    checklist = business_onboarding_service.build_business_onboarding_checklist(db_session, business)
    assert checklist.ready_for_launch is True
    assert checklist.launch_missing_labels == ()


def test_checklist_not_ready_when_notification_missing(db_session: Session) -> None:
    business = _launch_ready_business(db_session)
    business.notification_email = None
    business.notification_phone = None
    db_session.flush()
    checklist = business_onboarding_service.build_business_onboarding_checklist(db_session, business)
    assert not checklist.ready_for_launch
    assert any("Notification" in label for label in checklist.launch_missing_labels)


def test_first_lead_captured_complete_when_lead_exists(db_session: Session) -> None:
    business = create_business(db_session, name="Lead Co")
    create_lead(db_session, business.id, phone="+15550001234", source="sms")
    checklist = business_onboarding_service.build_business_onboarding_checklist(db_session, business)
    item = next(i for i in checklist.items if i.key == "first_lead_captured")
    assert item.status == "complete"
    assert item.is_post_launch is True


def test_admin_business_detail_renders_checklist(
    client: TestClient,
    db_session: Session,
) -> None:
    business = create_business(db_session, name="Checklist UI Co")
    db_session.commit()
    _login_admin(client, db_session)
    response = client.get(f"/admin/businesses/{business.id}")
    assert response.status_code == 200
    assert "Customer onboarding checklist" in response.text
    assert "Ready for launch" in response.text


def test_admin_can_mark_forwarding_test_passed(
    client: TestClient,
    db_session: Session,
) -> None:
    business = create_business(db_session, name="Mark Test Co")
    business.customer_phone_forwarding_status = "customer_attempted"
    db_session.commit()
    _login_admin(client, db_session)

    response = client.post(
        f"/admin/businesses/{business.id}/mark-forwarding-test-passed",
        follow_redirects=False,
    )
    assert response.status_code == 303

    db_session.refresh(business)
    assert business.customer_phone_forwarding_status == "test_passed"
    assert business.call_forwarding_tested_at is not None


def test_non_admin_cannot_access_onboarding_actions(
    client: TestClient,
    db_session: Session,
) -> None:
    business = create_business(db_session, name="Secure Co")
    user = create_user(
        db_session,
        email="biz@secure.example",
        password="biz-secret",
        role="business_user",
    )
    link_user_to_business(db_session, user.id, business.id)
    db_session.commit()
    client.post("/login", data={"email": "biz@secure.example", "password": "biz-secret"})

    detail = client.get(f"/admin/businesses/{business.id}", follow_redirects=False)
    assert detail.status_code == 303
    assert detail.headers["location"] == "/login"

    mark = client.post(
        f"/admin/businesses/{business.id}/mark-forwarding-test-passed",
        follow_redirects=False,
    )
    assert mark.status_code == 303
    assert mark.headers["location"] == "/login"


def test_admin_business_detail_shows_live_launch_section(
    client: TestClient,
    db_session: Session,
) -> None:
    business = create_business(db_session, name="Launch UI Co")
    db_session.commit()
    _login_admin(client, db_session)
    response = client.get(f"/admin/businesses/{business.id}")
    assert response.status_code == 200
    assert "Live launch test" in response.text
    assert "I need help with a leak." in response.text
    assert "Mark launch verified" in response.text


def test_cannot_mark_launch_verified_without_active_twilio(
    client: TestClient,
    db_session: Session,
) -> None:
    business = _launch_ready_business(db_session)
    for pn in list_phone_numbers_for_business(db_session, business.id):
        pn.status = "released"
    db_session.commit()
    _login_admin(client, db_session)

    response = client.post(
        f"/admin/businesses/{business.id}/mark-launch-verified",
        data={"launch_verification_notes": "should fail"},
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert business_onboarding_service.LAUNCH_MARK_REQUIRED_MESSAGES["twilio_number_assigned"] in response.text

    db_session.refresh(business)
    assert business.launch_verified_at is None


def test_cannot_mark_launch_verified_without_forwarding_test_passed(
    client: TestClient,
    db_session: Session,
) -> None:
    business = _launch_ready_business(db_session)
    business.customer_phone_forwarding_status = "instructions_sent"
    db_session.commit()
    _login_admin(client, db_session)

    response = client.post(
        f"/admin/businesses/{business.id}/mark-launch-verified",
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert business_onboarding_service.LAUNCH_MARK_REQUIRED_MESSAGES["forwarding_test_passed"] in response.text


def test_cannot_mark_launch_verified_without_notification_contact(
    client: TestClient,
    db_session: Session,
) -> None:
    business = _launch_ready_business(db_session)
    business.notification_email = None
    business.notification_phone = None
    db_session.commit()
    _login_admin(client, db_session)

    response = client.post(
        f"/admin/businesses/{business.id}/mark-launch-verified",
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert business_onboarding_service.LAUNCH_MARK_REQUIRED_MESSAGES["notification_contact_set"] in response.text


def test_can_mark_launch_verified_when_preconditions_complete(
    client: TestClient,
    db_session: Session,
) -> None:
    business = _launch_ready_business(db_session)
    db_session.commit()
    _login_admin(client, db_session)

    response = client.post(
        f"/admin/businesses/{business.id}/mark-launch-verified",
        data={"launch_verification_notes": "Smoke test OK"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith(f"/admin/businesses/{business.id}#live-launch-test")

    db_session.refresh(business)
    assert business.launch_verified_at is not None
    assert business.launch_verification_notes == "Smoke test OK"
    assert business.launch_verified_by_user_id is not None

    checklist = business_onboarding_service.build_business_onboarding_checklist(db_session, business)
    assert checklist.launch_verified is True
    item = next(i for i in checklist.items if i.key == "live_launch_verified")
    assert item.status == "complete"


def test_non_admin_cannot_mark_launch_verified(
    client: TestClient,
    db_session: Session,
) -> None:
    business = _launch_ready_business(db_session)
    user = create_user(
        db_session,
        email="owner2@launchready.example",
        password="owner-secret",
        role="business_user",
    )
    link_user_to_business(db_session, user.id, business.id)
    db_session.commit()
    client.post(
        "/login",
        data={"email": "owner2@launchready.example", "password": "owner-secret"},
    )

    response = client.post(
        f"/admin/businesses/{business.id}/mark-launch-verified",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/login"

    db_session.refresh(business)
    assert business.launch_verified_at is None
