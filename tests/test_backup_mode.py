"""Backup Mode business page (call-forwarding UX, V1)."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services import call_forwarding_service
from app.services.business_service import create_business, link_user_to_business
from app.services.phone_number_service import create_phone_number
from app.services.user_service import create_admin_user, create_user

BACKUP_MODE_URL = "/business/backup-mode"
LEGACY_URL = "/business/call-forwarding"
DASHBOARD_URL = "/business/dashboard"
BANNER_SNIPPET = call_forwarding_service.INCOMPLETE_BANNER_MESSAGE


def _create_business_user(
    db_session: Session,
    *,
    email: str,
    password: str,
    business_name: str,
):
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
    client.post("/login", data={"email": email, "password": password})


def _seed_business_with_number(
    db_session: Session,
    *,
    email: str = "backup@example.com",
    carrier: str = "verizon",
    phone: str = "+18336691335",
) -> tuple:
    _user, business = _create_business_user(
        db_session,
        email=email,
        password="backup-secret",
        business_name="Backup Mode Co",
    )
    create_phone_number(
        db_session,
        business.id,
        phone,
        provider="twilio",
        status="active",
    )
    business.customer_phone_carrier = carrier
    business.customer_phone_is_mobile = True
    db_session.commit()
    return business


def test_business_user_can_view_backup_mode_page(
    client: TestClient,
    db_session: Session,
) -> None:
    _seed_business_with_number(db_session)
    _login(client, "backup@example.com", "backup-secret")

    response = client.get(BACKUP_MODE_URL)
    assert response.status_code == 200
    assert "Backup Mode" in response.text
    assert "catch missed calls with LeadCareAI" in response.text


def test_backup_mode_page_shows_plain_language_explanation(
    client: TestClient,
    db_session: Session,
) -> None:
    _seed_business_with_number(db_session)
    _login(client, "backup@example.com", "backup-secret")

    response = client.get(BACKUP_MODE_URL)
    assert "Your phone still rings like normal" in response.text
    assert "captures the job details" in response.text


def test_backup_mode_page_shows_assigned_leadcare_number(
    client: TestClient,
    db_session: Session,
) -> None:
    _seed_business_with_number(db_session, phone="+15559876543")
    _login(client, "backup@example.com", "backup-secret")

    response = client.get(BACKUP_MODE_URL)
    assert response.status_code == 200
    assert "Forward calls to" in response.text
    assert "+1 555 987 6543" in response.text
    assert "+15559876543" in response.text


def test_tmobile_page_shows_conditional_forwarding_codes(
    client: TestClient,
    db_session: Session,
) -> None:
    _seed_business_with_number(
        db_session,
        email="tmobile@example.com",
        carrier="t_mobile",
        phone="+18336691335",
    )
    _login(client, "tmobile@example.com", "backup-secret")

    response = client.get(BACKUP_MODE_URL)
    assert "T-Mobile" in response.text
    assert "**61*18336691335#" in response.text
    assert "**67*18336691335#" in response.text
    assert "**62*18336691335#" in response.text
    assert "**21*18336691335#" in response.text
    assert "##61#" in response.text
    assert "##004#" in response.text
    assert "Conditional forwarding" in response.text
    assert call_forwarding_service.TMOBILE_METRO_CAVEAT in response.text
    assert "every call to go to LeadCareAI before your phone rings" in response.text
    assert re.search(r"(?<!\*)\*61\*18336691335#", response.text) is None


def test_metro_page_shows_conditional_codes(
    client: TestClient,
    db_session: Session,
) -> None:
    _seed_business_with_number(
        db_session,
        email="metro@example.com",
        carrier="metro_tmobile",
        phone="+18336691335",
    )
    _login(client, "metro@example.com", "backup-secret")

    response = client.get(BACKUP_MODE_URL)
    assert "Metro by T-Mobile" in response.text
    assert "**61*18336691335#" in response.text
    assert call_forwarding_service.TMOBILE_METRO_CAVEAT in response.text
    assert re.search(r"(?<!\*)\*61\*18336691335#", response.text) is None


def test_verizon_page_shows_verified_codes_and_warning(
    client: TestClient,
    db_session: Session,
) -> None:
    _seed_business_with_number(
        db_session,
        email="verizon@example.com",
        carrier="verizon",
        phone="+18336691335",
    )
    _login(client, "verizon@example.com", "backup-secret")

    response = client.get(BACKUP_MODE_URL)
    assert "Verizon" in response.text
    assert "*718336691335" in response.text
    assert "*72" in response.text
    assert "*73" in response.text
    assert "every call to go to LeadCareAI before your phone rings" in response.text
    assert "lc-confidence--verified" in response.text
    assert call_forwarding_service.NO_UNIVERSAL_COMPATIBILITY in response.text


def test_att_page_uses_cautious_carrier_language(
    client: TestClient,
    db_session: Session,
) -> None:
    _seed_business_with_number(
        db_session,
        email="att@example.com",
        carrier="att",
    )
    _login(client, "att@example.com", "backup-secret")

    response = client.get(BACKUP_MODE_URL)
    assert "AT&amp;T" in response.text or "AT&T" in response.text
    assert "Settings → Phone → Call Forwarding" in response.text
    assert "call forwarding settings first" in response.text
    assert "I do not want to forward all calls unless I ask for that" in response.text
    assert call_forwarding_service.NO_UNIVERSAL_COMPATIBILITY in response.text
    assert "Conditional forwarding (recommended)" not in response.text


def test_cricket_page_uses_contact_carrier_guidance_with_caution(
    client: TestClient,
    db_session: Session,
) -> None:
    _seed_business_with_number(
        db_session,
        email="cricket@example.com",
        carrier="cricket",
        phone="+18336691335",
    )
    _login(client, "cricket@example.com", "backup-secret")

    response = client.get(BACKUP_MODE_URL)
    assert "Cricket" in response.text
    assert call_forwarding_service.COMMON_EXAMPLES_DISCLAIMER in response.text
    assert "confirm with your carrier" in response.text.lower()
    assert "not verified for Cricket" in response.text
    assert "Conditional forwarding (recommended)" not in response.text
    assert call_forwarding_service.NO_UNIVERSAL_COMPATIBILITY in response.text


def test_boost_page_uses_contact_carrier_guidance_with_caution(
    client: TestClient,
    db_session: Session,
) -> None:
    _seed_business_with_number(
        db_session,
        email="boost@example.com",
        carrier="boost",
        phone="+18336691335",
    )
    _login(client, "boost@example.com", "backup-secret")

    response = client.get(BACKUP_MODE_URL)
    assert "Boost" in response.text
    assert call_forwarding_service.COMMON_EXAMPLES_DISCLAIMER in response.text
    assert "not verified for Boost" in response.text
    assert "Conditional forwarding (recommended)" not in response.text


def test_other_carrier_shows_contact_carrier_script(
    client: TestClient,
    db_session: Session,
) -> None:
    _seed_business_with_number(
        db_session,
        email="other@example.com",
        carrier="other",
        phone="+18336691335",
    )
    _login(client, "other@example.com", "backup-secret")

    response = client.get(BACKUP_MODE_URL)
    assert "Other" in response.text or "Not sure" in response.text
    assert "I do not want to forward all calls unless I ask for that" in response.text
    assert call_forwarding_service.NO_UNIVERSAL_COMPATIBILITY in response.text


def test_tmobile_shows_verified_confidence_label(
    client: TestClient,
    db_session: Session,
) -> None:
    _seed_business_with_number(
        db_session,
        email="tmobile-conf@example.com",
        carrier="t_mobile",
    )
    _login(client, "tmobile-conf@example.com", "backup-secret")

    response = client.get(BACKUP_MODE_URL)
    assert "lc-confidence--verified" in response.text
    assert "**61*" in response.text


def test_backup_mode_page_shows_carrier_caveat(
    client: TestClient,
    db_session: Session,
) -> None:
    _seed_business_with_number(db_session)
    _login(client, "backup@example.com", "backup-secret")

    response = client.get(BACKUP_MODE_URL)
    assert call_forwarding_service.CARRIER_CAVEAT in response.text


def test_backup_mode_page_includes_full_setup_checklist(
    client: TestClient,
    db_session: Session,
) -> None:
    _seed_business_with_number(db_session)
    _login(client, "backup@example.com", "backup-secret")

    response = client.get(BACKUP_MODE_URL)
    assert "Setup checklist" in response.text
    assert "My customer-facing line is mobile" in response.text
    assert "I did not answer" in response.text
    assert "Admin marked my test passed" in response.text


def test_dashboard_banner_uses_backup_mode_call_forwarding_language(
    client: TestClient,
    db_session: Session,
) -> None:
    _user, business = _create_business_user(
        db_session,
        email="banner@example.com",
        password="banner-secret",
        business_name="Banner Co",
    )
    business.customer_phone_forwarding_status = "instructions_sent"
    db_session.commit()

    _login(client, "banner@example.com", "banner-secret")
    response = client.get(DASHBOARD_URL)
    assert BANNER_SNIPPET in response.text
    assert "call-forwarding test" in response.text


def test_backup_mode_page_explains_carrier_controlled_forwarding(
    client: TestClient,
    db_session: Session,
) -> None:
    _seed_business_with_number(db_session)
    _login(client, "backup@example.com", "backup-secret")

    response = client.get(BACKUP_MODE_URL)
    assert "your carrier" in response.text.lower()
    assert "cannot turn" in response.text.lower()
    assert "forwarding on or off" in response.text.lower()


def test_unauthenticated_user_blocked_from_backup_mode(
    client: TestClient,
) -> None:
    response = client.get(BACKUP_MODE_URL, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_admin_cannot_access_backup_mode_page(
    client: TestClient,
    db_session: Session,
) -> None:
    create_admin_user(db_session, email="admin@example.com", password="admin-secret")
    db_session.commit()
    client.post(
        "/login",
        data={"email": "admin@example.com", "password": "admin-secret"},
    )

    response = client.get(BACKUP_MODE_URL, follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/login"


def test_legacy_call_forwarding_route_still_works(
    client: TestClient,
    db_session: Session,
) -> None:
    _seed_business_with_number(db_session, phone="+15559876543")
    _login(client, "backup@example.com", "backup-secret")

    response = client.get(LEGACY_URL)
    assert response.status_code == 200
    assert "Backup Mode" in response.text
    assert "+1 555 987 6543" in response.text
