"""Public vertical lander pages."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.services.public_seo_service import absolute_public_url

LANDER_ROUTES = (
    ("/for/plumbers", "Plumbers"),
    ("/for/roofers", "Roofers"),
    ("/answering-service-alternative", "Answering service alternative"),
)


def test_public_lander_pages_return_200(client: TestClient) -> None:
    for path, _label in LANDER_ROUTES:
        response = client.get(path)
        assert response.status_code == 200, path


def test_roofers_lander_includes_headline(client: TestClient) -> None:
    response = client.get("/for/roofers")
    assert response.status_code == 200
    text = response.text
    assert "Answering Service Alternative for Roofers" in text
    assert "LeadCareAI_for_Roofers.mp4" in text
    assert "/backup-mode" in text
    assert "/demo" in text
    assert 'name="keywords"' in text
    assert "/for/plumbers" in text


def test_plumbers_lander_includes_headline_and_seo(client: TestClient) -> None:
    response = client.get("/for/plumbers")
    assert response.status_code == 200
    text = response.text
    assert "answering service for plumbers" in text.lower()
    assert "Answering Service for Plumbers" in text
    assert "plumbing contractors" in text.lower() or "plumbing contractor" in text.lower()
    assert 'meta name="description"' in text
    assert "Looking for an answering service for plumbers" in text
    assert 'name="keywords"' in text
    assert "answering service for plumbers" in text.lower()
    assert "application/ld+json" in text
    assert '"@type": "WebPage"' in text or '"@type":"WebPage"' in text
    assert '"@type": "Service"' in text or '"@type":"Service"' in text
    assert "Joe’s Plumbing" in text or "Joe's Plumbing" in text
    assert "/for/roofers" in text
    assert "/backup-mode" in text
    assert "How is this different from an answering service for plumbers" in text


def test_answering_service_alternative_lander_seo(client: TestClient) -> None:
    response = client.get("/answering-service-alternative")
    assert response.status_code == 200
    text = response.text
    assert "answering service alternative" in text.lower()
    assert "Answering Service Alternative for Small Service Businesses" in text
    assert "Catch Missed Calls Without Hiring a Full Answering Service" in text
    assert 'meta name="description"' in text
    assert "Looking for an answering service" in text
    assert 'property="og:title"' in text
    assert "A Simpler Answering Service Alternative for Service Businesses" in text
    assert 'name="twitter:title"' in text
    assert "Catch missed calls before they become lost jobs" in text
    assert absolute_public_url("/answering-service-alternative") in text
    assert "application/ld+json" in text
    assert '"@type": "Service"' in text or '"@type":"Service"' in text
    assert "best answering service" not in text.lower() or "not claiming to be" in text.lower()
    assert "/for/plumbers" in text
    assert "/for/roofers" in text
    assert "/backup-mode" in text


def test_answering_service_alternative_legacy_redirect(client: TestClient) -> None:
    response = client.get("/for/answering-service-alternative", follow_redirects=False)
    assert response.status_code == 301
    assert response.headers["location"] == "/answering-service-alternative"
