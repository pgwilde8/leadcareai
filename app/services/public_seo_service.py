"""Public marketing SEO helpers: canonical URLs, sitemap, robots.txt."""

from __future__ import annotations

from datetime import date
from xml.sax.saxutils import escape

from app.core.config import get_settings

DEFAULT_OG_IMAGE = (
    "https://our-cloud-storage.sfo3.cdn.digitaloceanspaces.com/"
    "leadcareai/logo%20images/leadcareai-logo.png"
)

# Indexable public marketing and legal pages (no auth, no webhooks).
PUBLIC_SITEMAP_PATHS: tuple[str, ...] = (
    "/",
    "/about",
    "/faq",
    "/backup-mode",
    "/for/plumbers",
    "/for/roofers",
    "/answering-service-alternative",
    "/demo",
    "/demo/book",
    "/partners",
    "/contact",
    "/privacy",
    "/terms",
    "/sms-terms",
    "/refund-policy",
)


def public_site_base_url() -> str:
    settings = get_settings()
    raw = settings.effective_public_base_url or settings.app_base_url or "http://localhost:8788"
    return raw.rstrip("/")


def absolute_public_url(path: str) -> str:
    base = public_site_base_url()
    if not path.startswith("/"):
        path = f"/{path}"
    return f"{base}{path}"


def robots_txt_body() -> str:
    base = public_site_base_url()
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /admin/",
        "Disallow: /business/",
        "Disallow: /partner/",
        "Disallow: /login",
        "Disallow: /auth/",
        "Disallow: /checkout/",
        "Disallow: /billing/",
        "Disallow: /webhooks/",
        f"Sitemap: {base}/sitemap.xml",
        "",
    ]
    return "\n".join(lines)


def sitemap_xml_body() -> str:
    """XML sitemap for Google Search Console and other crawlers."""
    lastmod = date.today().isoformat()
    entries = []
    for path in PUBLIC_SITEMAP_PATHS:
        loc = escape(absolute_public_url(path))
        priority = "1.0" if path == "/" else "0.8"
        changefreq = "weekly" if path in {
            "/",
            "/for/plumbers",
            "/for/roofers",
            "/answering-service-alternative",
            "/backup-mode",
        } else "monthly"
        entries.append(
            f"  <url>\n"
            f"    <loc>{loc}</loc>\n"
            f"    <lastmod>{lastmod}</lastmod>\n"
            f"    <changefreq>{changefreq}</changefreq>\n"
            f"    <priority>{priority}</priority>\n"
            f"  </url>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{chr(10).join(entries)}\n"
        "</urlset>\n"
    )


def sitemap_index_url() -> str:
    return absolute_public_url("/sitemap.xml")
