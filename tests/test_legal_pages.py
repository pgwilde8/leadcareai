"""Public legal and compliance pages (Phase 3G)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import get_settings

LEGAL_ROUTES = (
    "/privacy",
    "/terms",
    "/sms-terms",
    "/refund-policy",
)

SMS_ALIASES = ("/sms", "/legal/sms", "/legal/sms-terms")


def test_legal_pages_return_200(client: TestClient) -> None:
    for path in LEGAL_ROUTES:
        response = client.get(path)
        assert response.status_code == 200, path


def test_sms_route_aliases_return_200(client: TestClient) -> None:
    for path in SMS_ALIASES:
        response = client.get(path)
        assert response.status_code == 200, path


def test_legal_pages_include_required_compliance_phrases(client: TestClient) -> None:
    privacy = client.get("/privacy").text
    terms = client.get("/terms").text
    sms = client.get("/sms-terms").text

    assert "not sold" in privacy.lower() and "third parties" in privacy.lower()
    assert "marketing" in privacy.lower() or "promotional" in privacy.lower()

    assert "STOP" in sms
    assert "HELP" in sms
    assert "message and data rates" in sms.lower()

    assert "911" in terms or "emergency" in terms.lower()
    assert "carrier compatibility is not guaranteed" in terms.lower() or "not guaranteed" in terms.lower()


def test_footer_includes_legal_links(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    text = response.text
    settings = get_settings()
    assert 'href="/privacy"' in text
    assert 'href="/terms"' in text
    assert 'href="/sms-terms"' in text
    assert 'href="/refund-policy"' in text
    assert 'href="/contact"' in text
    assert settings.legal_contact_email in client.get("/privacy").text


def test_legal_pages_show_draft_notice(client: TestClient) -> None:
    for path in LEGAL_ROUTES:
        assert "Draft policies" in client.get(path).text
