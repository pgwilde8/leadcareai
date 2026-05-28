"""Business dashboard lead inbox tests (SQLite)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services import lead_service, message_service
from app.services.business_service import create_business, link_user_to_business
from app.services.user_service import create_user

DASHBOARD_URL = "/business/dashboard"
LEADS_URL = "/business/leads"


def _create_business_user(
    db_session: Session,
    *,
    email: str,
    password: str,
    business_name: str,
) -> tuple:
    business = create_business(db_session, name=business_name)
    user = create_user(
        db_session,
        email=email,
        password=password,
        role="business_user",
    )
    link_user_to_business(db_session, user.id, business.id)
    db_session.commit()
    return user, business


def _login(client: TestClient, email: str, password: str) -> None:
    response = client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/business/dashboard"


def test_business_dashboard_requires_auth(client: TestClient) -> None:
    response = client.get(DASHBOARD_URL, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_business_user_sees_own_dashboard_and_counts(
    client: TestClient,
    db_session: Session,
) -> None:
    _user, business = _create_business_user(
        db_session,
        email="owner-a@example.com",
        password="biz-a-secret",
        business_name="Business A",
    )
    lead_service.create_lead(
        db_session,
        business.id,
        phone="+15551110001",
        source="sms",
        summary="Need HVAC",
    )
    lead_service.create_lead(
        db_session,
        business.id,
        phone="+15551110002",
        source="missed_call",
        summary="Missed call",
    )
    db_session.commit()

    _login(client, "owner-a@example.com", "biz-a-secret")
    response = client.get(DASHBOARD_URL)
    assert response.status_code == 200
    assert "Business A" in response.text
    assert "Total leads" in response.text
    assert "<td>2</td>" in response.text.replace(" ", "")


def test_business_user_sees_own_leads_list(
    client: TestClient,
    db_session: Session,
) -> None:
    _user, business = _create_business_user(
        db_session,
        email="inbox@example.com",
        password="inbox-secret",
        business_name="Inbox Co",
    )
    lead = lead_service.create_lead(
        db_session,
        business.id,
        phone="+15552223333",
        source="sms",
        summary="Roof repair inquiry",
        urgency="Today",
    )
    message_service.create_message(
        db_session,
        business.id,
        lead.id,
        body="Latest inbound text",
        direction="inbound",
        channel="sms",
        status="received",
    )
    db_session.commit()

    _login(client, "inbox@example.com", "inbox-secret")
    response = client.get(LEADS_URL)
    assert response.status_code == 200
    assert "+15552223333" in response.text
    assert "Roof repair inquiry" in response.text
    assert "Latest inbound text" in response.text
    assert "SMS" in response.text


def test_business_user_cannot_view_other_business_lead(
    client: TestClient,
    db_session: Session,
) -> None:
    _user_a, business_a = _create_business_user(
        db_session,
        email="user-a@example.com",
        password="a-secret",
        business_name="Company A",
    )
    _user_b, _business_b = _create_business_user(
        db_session,
        email="user-b@example.com",
        password="b-secret",
        business_name="Company B",
    )
    lead_b = lead_service.create_lead(
        db_session,
        _business_b.id,
        phone="+15559998888",
        source="sms",
        summary="Secret lead",
    )
    db_session.commit()

    _login(client, "user-a@example.com", "a-secret")
    response = client.get(f"/business/leads/{lead_b.id}", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/business/leads"


def test_partner_user_cannot_access_business_dashboard(
    client: TestClient,
    db_session: Session,
) -> None:
    from app.models.partner import Partner

    user = create_user(
        db_session,
        email="partner-bd@example.com",
        password="partner-bd-secret",
        role="partner",
    )
    db_session.add(
        Partner(
            user_id=user.id,
            display_name="Partner BD",
            email=user.email,
            phone="+15551239999",
            referral_code="REFBD001",
            status="active",
        )
    )
    db_session.commit()

    client.post(
        "/login",
        data={"email": "partner-bd@example.com", "password": "partner-bd-secret"},
    )
    response = client.get(DASHBOARD_URL, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_lead_detail_shows_ai_fields_and_messages(
    client: TestClient,
    db_session: Session,
) -> None:
    _user, business = _create_business_user(
        db_session,
        email="detail@example.com",
        password="detail-secret",
        business_name="Detail Co",
    )
    lead = lead_service.create_lead(
        db_session,
        business.id,
        phone="+15553334444",
        source="missed_call",
        summary="Inbound call summary",
    )
    lead.ai_temperature = "hot"
    lead.ai_next_question = "What service do you need?"
    lead.ai_confidence = 0.82
    lead.service_needed = "Plumbing"
    lead.location = "Brick, NJ"
    message_service.create_voice_message(
        db_session,
        business.id,
        lead.id,
        body="Inbound call from +15553334444",
        from_phone="+15553334444",
        to_phone="+15559876543",
        provider_sid="CA_TEST_DETAIL",
        status="ringing",
    )
    message_service.create_message(
        db_session,
        business.id,
        lead.id,
        body="Sorry we missed your call",
        direction="outbound",
        channel="sms",
        status="sent",
    )
    db_session.commit()

    _login(client, "detail@example.com", "detail-secret")
    response = client.get(f"/business/leads/{lead.id}")
    assert response.status_code == 200
    assert "Plumbing" in response.text
    assert "Brick, NJ" in response.text
    assert "hot" in response.text
    assert "What service do you need?" in response.text
    assert "Voice call" in response.text
    assert "Outbound SMS" in response.text


def test_status_update_changes_lead_status(
    client: TestClient,
    db_session: Session,
) -> None:
    _user, business = _create_business_user(
        db_session,
        email="status@example.com",
        password="status-secret",
        business_name="Status Co",
    )
    lead = lead_service.create_lead(
        db_session,
        business.id,
        phone="+15554445555",
        source="sms",
        summary="Status test",
    )
    db_session.commit()

    _login(client, "status@example.com", "status-secret")
    update = client.post(
        f"/business/leads/{lead.id}/status",
        data={"status": "contacted"},
        follow_redirects=False,
    )
    assert update.status_code == 303

    db_session.expire_all()
    refreshed = lead_service.get_lead(db_session, lead.id)
    assert refreshed.status == "contacted"

    detail = client.get(f"/business/leads/{lead.id}")
    assert "contacted" in detail.text


def test_invalid_status_shows_error(
    client: TestClient,
    db_session: Session,
) -> None:
    _user, business = _create_business_user(
        db_session,
        email="badstatus@example.com",
        password="badstatus-secret",
        business_name="Bad Status Co",
    )
    lead = lead_service.create_lead(
        db_session,
        business.id,
        phone="+15556667777",
        source="sms",
        summary="Bad status",
    )
    db_session.commit()

    _login(client, "badstatus@example.com", "badstatus-secret")
    response = client.post(
        f"/business/leads/{lead.id}/status",
        data={"status": "not-a-real-status"},
    )
    assert response.status_code == 400
    assert "Invalid lead status" in response.text


def test_dashboard_counts_leads_correctly(
    client: TestClient,
    db_session: Session,
) -> None:
    _user, business = _create_business_user(
        db_session,
        email="counts@example.com",
        password="counts-secret",
        business_name="Counts Co",
    )
    lead_service.create_lead(
        db_session,
        business.id,
        phone="+15550000001",
        source="sms",
        summary="New one",
    )
    qualifying = lead_service.create_lead(
        db_session,
        business.id,
        phone="+15550000002",
        source="sms",
        summary="Qualifying one",
    )
    qualifying.status = "qualifying"
    hot = lead_service.create_lead(
        db_session,
        business.id,
        phone="+15550000003",
        source="sms",
        summary="Hot one",
        urgency="urgent",
    )
    hot.ai_temperature = "hot"
    db_session.commit()

    counts = lead_service.dashboard_lead_counts(db_session, business.id)
    assert counts["total"] == 3
    assert counts["new"] == 2
    assert counts["qualifying"] == 1
    assert counts["urgent_hot"] == 1

    _login(client, "counts@example.com", "counts-secret")
    page = client.get(DASHBOARD_URL)
    assert page.status_code == 200
    assert "Counts Co" in page.text
