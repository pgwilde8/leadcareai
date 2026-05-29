"""Public SEO: meta tags, robots.txt, sitemap.xml."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.services.public_seo_service import PUBLIC_SITEMAP_PATHS, absolute_public_url


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
    assert "Disallow: /admin/" in text
    assert "Sitemap:" in text
    assert "/sitemap.xml" in text


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


def test_footer_links_sitemap(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert 'href="/sitemap.xml"' in response.text


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
