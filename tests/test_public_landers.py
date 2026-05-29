"""Public vertical lander pages."""

from __future__ import annotations

from fastapi.testclient import TestClient

LANDER_ROUTES = (
    ("/for/plumbers", "Plumbers"),
    ("/for/roofers", "Roofers"),
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
    assert "Answering Service Alternative for Plumbers" in text
    assert "plumbing contractors" in text.lower() or "plumbing contractor" in text.lower()
    assert 'meta name="description"' in text
    assert 'name="keywords"' in text
    assert "plumber answering service" in text.lower()
    assert "Joe’s Plumbing" in text or "Joe's Plumbing" in text
    assert "/for/roofers" in text
    assert "/backup-mode" in text
