"""Public SEO: meta tags, robots.txt, sitemap.xml."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.services.public_seo_service import PUBLIC_SITEMAP_PATHS, absolute_public_url, robots_txt_body, sitemap_xml_body
from tests.settings_helpers import clear_settings_cache
from tests.test_public_landers import LANDER_ROUTES


def test_landing_page_has_seo_meta(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    text = response.text
    assert '<meta name="description"' in text
    assert "missed call recovery" in text.lower() or "missed-call" in text.lower()
    assert '<link rel="canonical"' in text
    assert absolute_public_url("/") in text
    assert 'property="og:title"' in text
    assert 'property="og:description"' in text
    assert 'name="twitter:card"' in text
    assert "application/ld+json" in text
    assert "WebSite" in text
    assert 'name="keywords"' in text


def test_robots_txt(client: TestClient) -> None:
    response = client.get("/robots.txt")
    assert response.status_code == 200
    text = response.text
    assert "User-agent: *" in text
    assert "Allow: /" in text
    assert "Disallow: /admin/" in text
    assert "Sitemap:" in text
    assert absolute_public_url("/sitemap.xml") in text


def test_robots_txt_sitemap_uses_configured_public_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://leadcareai.example.com")
    clear_settings_cache()
    text = robots_txt_body()
    assert "Sitemap: https://leadcareai.example.com/sitemap.xml" in text
    clear_settings_cache()


def test_sitemap_xml_lists_public_paths(client: TestClient) -> None:
    response = client.get("/sitemap.xml")
    assert response.status_code == 200
    assert "application/xml" in response.headers.get("content-type", "")
    text = response.text
    assert "<urlset" in text
    assert "<lastmod>" in text
    assert "<loc>" in text
    for path in PUBLIC_SITEMAP_PATHS:
        assert absolute_public_url(path) in text, path


def test_sitemap_xml_includes_priority_lander_urls(client: TestClient) -> None:
    response = client.get("/sitemap.xml")
    assert response.status_code == 200
    text = response.text
    assert absolute_public_url("/answering-service") in text
    assert absolute_public_url("/for/plumbers") in text
    assert absolute_public_url("/for/roofers") in text


def test_sitemap_xml_includes_all_lander_routes(client: TestClient) -> None:
    response = client.get("/sitemap.xml")
    assert response.status_code == 200
    text = response.text
    for path, _label in LANDER_ROUTES:
        assert absolute_public_url(path) in text, path


def test_sitemap_xml_uses_configured_public_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PUBLIC_BASE_URL", "https://leadcareai.example.com")
    clear_settings_cache()
    text = sitemap_xml_body()
    assert "<loc>https://leadcareai.example.com/answering-service</loc>" in text
    assert "<loc>https://leadcareai.example.com/for/plumbers</loc>" in text
    clear_settings_cache()


def test_footer_links_sitemap(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert 'href="/sitemap.xml"' in response.text


def test_footer_includes_answering_service_hub_site_wide(client: TestClient) -> None:
    for path in ("/", "/about", "/answering-service"):
        response = client.get(path)
        assert response.status_code == 200, path
        text = response.text
        assert 'href="/answering-service"' in text, path
        assert "Guides" in text or "guides" in text.lower()


def test_footer_includes_top_guide_links(client: TestClient) -> None:
    response = client.get("/faq")
    assert response.status_code == 200
    text = response.text
    for href in (
        "/business-answering-service-alternative",
        "/after-hours-answering-service-alternative",
        "/contractors-answering-service-alternative",
        "/for/plumbers",
        "/for/roofers",
    ):
        assert href in text, href


def test_homepage_includes_recovery_guides_section(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    text = response.text
    assert "Explore missed-call recovery guides" in text
    assert 'href="/answering-service"' in text
    assert 'href="/for/plumbers"' in text
    assert 'href="/for/roofers"' in text


def test_backup_mode_has_canonical(client: TestClient) -> None:
    response = client.get("/backup-mode")
    assert response.status_code == 200
    assert absolute_public_url("/backup-mode") in response.text


def test_plumbers_lander_has_canonical_and_target_keyword(client: TestClient) -> None:
    response = client.get("/for/plumbers")
    assert response.status_code == 200
    text = response.text
    assert absolute_public_url("/for/plumbers") in text
    assert "answering service for plumbers" in text.lower()
