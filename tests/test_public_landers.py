"""Public vertical lander pages."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.services.public_seo_service import PUBLIC_SITEMAP_PATHS, absolute_public_url

MISSED_CALL_SAFETY_NET_VIDEO = (
    "https://our-cloud-storage.sfo3.cdn.digitaloceanspaces.com/"
    "leadcareai/marketing/video/Missed-Call_Safety_Net.mp4"
)

PHASE_C_PRIORITY_LANDERS = (
    "/answering-service",
    "/answering-service-alternative",
    "/business-answering-service-alternative",
    "/after-hours-answering-service-alternative",
    "/contractors-answering-service-alternative",
    "/for/plumbers",
    "/for/roofers",
)

LANDER_ROUTES = (
    ("/for/plumbers", "Plumbers"),
    ("/for/roofers", "Roofers"),
    ("/answering-service", "Answering service"),
    ("/answering-service-alternative", "Answering service alternative"),
    ("/phone-answering-service", "Phone answering service"),
    ("/247-answering-service-alternative", "24/7 answering service"),
    ("/business-answering-service-alternative", "Business answering service"),
    ("/virtual-answering-service-alternative", "Virtual answering service"),
    ("/responsive-answering-service-alternative", "Responsive answering service"),
    ("/contractors-answering-service-alternative", "Contractors answering service"),
    ("/automated-answering-service-alternative", "Automated answering service"),
    ("/after-hours-answering-service-alternative", "After-hours answering service"),
    ("/answering-call-service-alternative", "Answering call service"),
    ("/telephone-answering-service-alternative", "Telephone answering service"),
    ("/small-business-phone-answering-service-alternative", "Small business phone answering"),
    ("/small-business-answering-service-alternative", "Small business answering"),
)


def test_public_lander_pages_return_200(client: TestClient) -> None:
    for path, _label in LANDER_ROUTES:
        response = client.get(path)
        assert response.status_code == 200, path


def test_roofers_lander_includes_headline(client: TestClient) -> None:
    response = client.get("/for/roofers")
    assert response.status_code == 200
    text = response.text
    assert "answering service for roofers" in text.lower()
    assert "Answering Service for Roofers" in text
    assert "Looking for an answering service for roofers" in text
    assert "LeadCareAI_for_Roofers.mp4" in text
    assert "/backup-mode" in text
    assert "/demo" in text
    assert 'name="keywords"' in text
    assert "/for/plumbers" in text
    assert "/contractors-answering-service-alternative" in text
    assert "/answering-service" in text
    assert "application/ld+json" in text
    assert '"@type": "WebPage"' in text or '"@type":"WebPage"' in text
    assert '"@type": "Service"' in text or '"@type":"Service"' in text
    assert '"@type": "BreadcrumbList"' in text or '"@type":"BreadcrumbList"' in text
    assert '"@type": "FAQPage"' in text or '"@type":"FAQPage"' in text
    assert "an answering service for roofers?</dt>" in text
    assert text.index("an answering service for roofers?</dt>") > 0


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
    assert '"@type": "BreadcrumbList"' in text or '"@type":"BreadcrumbList"' in text
    assert '"@type": "FAQPage"' in text or '"@type":"FAQPage"' in text
    assert "Joe’s Plumbing" in text or "Joe's Plumbing" in text
    assert "/for/roofers" in text
    assert "/contractors-answering-service-alternative" in text
    assert "/answering-service" in text
    assert "/backup-mode" in text
    assert "How is this different from an answering service for plumbers" in text


def test_answering_service_lander_seo(client: TestClient) -> None:
    response = client.get("/answering-service")
    assert response.status_code == 200
    text = response.text
    assert "Looking for an Answering Service" in text
    assert "answering service" in text.lower()
    assert "Looking for an answering service" in text
    assert "searching for an answering service" in text.lower()
    assert "traditional answering service makes sense" in text.lower()
    assert "missed-call recovery alternative" in text.lower()
    assert "live human operators" in text.lower() or "live operators" in text.lower()
    assert absolute_public_url("/answering-service") in text
    assert "application/ld+json" in text
    assert '"@type": "WebPage"' in text or '"@type":"WebPage"' in text
    assert '"@type": "Service"' in text or '"@type":"Service"' in text
    assert '"@type": "BreadcrumbList"' in text or '"@type":"BreadcrumbList"' in text
    assert '"@type": "FAQPage"' in text or '"@type":"FAQPage"' in text
    assert "Missed-Call_Safety_Net.mp4" in text
    assert "Answering Service vs" in text
    assert "Find the Right Answering Service Option" in text
    assert "/answering-service-alternative" in text
    assert "/phone-answering-service" in text
    assert "/backup-mode" in text


def test_answering_service_alternative_lander_seo(client: TestClient) -> None:
    response = client.get("/answering-service-alternative")
    assert response.status_code == 200
    text = response.text
    assert "answering service alternative" in text.lower()
    assert "Answering Service Alternative for Small Service Businesses" in text
    assert "comparing alternatives to traditional answering services" in text.lower()
    assert "broader answering service guide" in text.lower()
    assert "Catch Missed Calls Without Hiring a Full Answering Service" in text
    assert 'meta name="description"' in text
    assert "Looking for an answering service" in text
    assert 'property="og:title"' in text
    assert "A Simpler Answering Service Alternative for Service Businesses" in text
    assert 'name="twitter:title"' in text
    assert "Catch missed calls before they become lost jobs" in text
    assert absolute_public_url("/answering-service-alternative") in text
    assert "application/ld+json" in text
    assert '"@type": "WebPage"' in text or '"@type":"WebPage"' in text
    assert '"@type": "Service"' in text or '"@type":"Service"' in text
    assert '"@type": "BreadcrumbList"' in text or '"@type":"BreadcrumbList"' in text
    assert '"@type": "FAQPage"' in text or '"@type":"FAQPage"' in text
    assert "best answering service" not in text.lower() or "not claiming to be" in text.lower()
    assert "/for/plumbers" in text
    assert "/for/roofers" in text
    assert "/answering-service" in text
    assert "/backup-mode" in text
    assert "Missed-Call_Safety_Net.mp4" in text


def test_hub_and_alternative_cross_link_each_other(client: TestClient) -> None:
    hub = client.get("/answering-service").text
    alt = client.get("/answering-service-alternative").text
    assert 'href="/answering-service-alternative"' in hub
    assert "missed-call recovery alternative" in hub.lower()
    assert 'href="/answering-service"' in alt
    assert "broader answering service guide" in alt.lower()


def test_phone_answering_service_lander_seo(client: TestClient) -> None:
    response = client.get("/phone-answering-service")
    assert response.status_code == 200
    text = response.text
    assert "phone answering service alternative" in text.lower()
    assert "A Simpler Phone Answering Service Alternative" in text
    assert "Looking for a phone answering service" in text
    assert 'meta name="description"' in text
    assert absolute_public_url("/phone-answering-service") in text
    assert "application/ld+json" in text
    assert '"@type": "Service"' in text or '"@type":"Service"' in text
    assert "/answering-service-alternative" in text
    assert "/backup-mode" in text
    assert "/for/plumbers" in text
    assert MISSED_CALL_SAFETY_NET_VIDEO in text


def test_247_answering_service_alternative_lander_seo(client: TestClient) -> None:
    response = client.get("/247-answering-service-alternative")
    assert response.status_code == 200
    text = response.text
    assert "24/7 Answering Service Alternative" in text
    assert "24/7 answering service alternative" in text.lower()
    assert "247 answering service" in text.lower()
    assert "Not a Live 24/7 Call Center" in text
    assert "Need 24/7 call coverage" in text
    assert absolute_public_url("/247-answering-service-alternative") in text
    assert "application/ld+json" in text
    assert "/backup-mode" in text
    assert "/phone-answering-service" in text
    assert "Missed-Call_Safety_Net.mp4" in text


def test_business_answering_service_alternative_lander_seo(client: TestClient) -> None:
    response = client.get("/business-answering-service-alternative")
    assert response.status_code == 200
    text = response.text
    assert "business answering service alternative" in text.lower()
    assert "A Simpler Business Answering Service Alternative" in text
    assert "Need a business answering service" in text
    assert absolute_public_url("/business-answering-service-alternative") in text
    assert MISSED_CALL_SAFETY_NET_VIDEO in text
    assert "Business Answering Service vs" in text
    assert "/phone-answering-service" in text
    assert "/for/plumbers" in text


def test_virtual_answering_service_alternative_lander_seo(client: TestClient) -> None:
    response = client.get("/virtual-answering-service-alternative")
    assert response.status_code == 200
    text = response.text
    assert "virtual answering service alternative" in text.lower()
    assert "A Simpler Virtual Answering Service Alternative" in text
    assert "Looking for a virtual answering service" in text
    assert "virtual receptionist" in text.lower()
    assert absolute_public_url("/virtual-answering-service-alternative") in text
    assert MISSED_CALL_SAFETY_NET_VIDEO in text
    assert "Virtual Answering Service vs" in text
    assert "/business-answering-service-alternative" in text
    assert "/backup-mode" in text


def test_responsive_answering_service_alternative_lander_seo(client: TestClient) -> None:
    response = client.get("/responsive-answering-service-alternative")
    assert response.status_code == 200
    text = response.text
    assert "responsive answering service alternative" in text.lower()
    assert "A More Responsive Answering Service Alternative" in text
    assert "Need a more responsive answering service" in text
    assert "The Real Problem Is Response Time" in text
    assert absolute_public_url("/responsive-answering-service-alternative") in text
    assert "Missed-Call_Safety_Net.mp4" in text
    assert "Responsive Answering Service vs" in text
    assert "/backup-mode" in text
    assert "/for/plumbers" in text


def test_contractors_answering_service_alternative_lander_seo(client: TestClient) -> None:
    response = client.get("/contractors-answering-service-alternative")
    assert response.status_code == 200
    text = response.text
    assert "contractors answering service" in text.lower()
    assert "answering service for contractors" in text.lower()
    assert "A Simpler Answering Service Alternative for Contractors" in text
    assert "Need an answering service for contractors" in text
    assert absolute_public_url("/contractors-answering-service-alternative") in text
    assert "application/ld+json" in text
    assert '"@type": "WebPage"' in text or '"@type":"WebPage"' in text
    assert '"@type": "Service"' in text or '"@type":"Service"' in text
    assert '"@type": "BreadcrumbList"' in text or '"@type":"BreadcrumbList"' in text
    assert '"@type": "FAQPage"' in text or '"@type":"FAQPage"' in text
    assert "Missed-Call_Safety_Net.mp4" in text
    assert "Contractors Answering Service vs" in text
    assert "/for/plumbers" in text
    assert "/for/roofers" in text
    assert 'href="/answering-service"' in text
    assert "/backup-mode" in text


def test_automated_answering_service_alternative_lander_seo(client: TestClient) -> None:
    response = client.get("/automated-answering-service-alternative")
    assert response.status_code == 200
    text = response.text
    assert "automated answering service alternative" in text.lower()
    assert "An Automated Answering Service Alternative for Missed Calls" in text
    assert "Need an automated answering service" in text
    assert "Automation Without the Complexity" in text
    assert absolute_public_url("/automated-answering-service-alternative") in text
    assert "Missed-Call_Safety_Net.mp4" in text
    assert "Automated Answering Service vs" in text
    assert "voice bot" in text.lower()
    assert "/backup-mode" in text


def test_after_hours_answering_service_alternative_lander_seo(client: TestClient) -> None:
    response = client.get("/after-hours-answering-service-alternative")
    assert response.status_code == 200
    text = response.text
    assert "after-hours answering service alternative" in text.lower() or "after hours answering service" in text.lower()
    assert "A Simpler After-Hours Answering Service Alternative" in text
    assert "Need an after-hours answering service" in text
    assert "Your business can be closed" in text
    assert absolute_public_url("/after-hours-answering-service-alternative") in text
    assert "Missed-Call_Safety_Net.mp4" in text
    assert "After-Hours Answering Service vs" in text
    assert "/247-answering-service-alternative" in text
    assert "/backup-mode" in text


def test_answering_call_service_alternative_lander_seo(client: TestClient) -> None:
    response = client.get("/answering-call-service-alternative")
    assert response.status_code == 200
    text = response.text
    assert "answering call service alternative" in text.lower()
    assert "call answering service" in text.lower()
    assert "A Simpler Answering Call Service Alternative" in text
    assert "Looking for an answering call service" in text
    assert "An Answering Call Service for the Calls You Miss" in text
    assert absolute_public_url("/answering-call-service-alternative") in text
    assert "Missed-Call_Safety_Net.mp4" in text
    assert "Answering Call Service vs" in text
    assert "/phone-answering-service" in text
    assert "/backup-mode" in text


def test_telephone_answering_service_alternative_lander_seo(client: TestClient) -> None:
    response = client.get("/telephone-answering-service-alternative")
    assert response.status_code == 200
    text = response.text
    assert "telephone answering service alternative" in text.lower()
    assert "telephone answering service" in text.lower()
    assert "A Modern Telephone Answering Service Alternative" in text
    assert "Need a telephone answering service" in text
    assert absolute_public_url("/telephone-answering-service-alternative") in text
    assert "Missed-Call_Safety_Net.mp4" in text
    assert "Telephone Answering Service vs" in text
    assert "/phone-answering-service" in text
    assert "/answering-service" in text
    assert "/backup-mode" in text


def test_small_business_phone_answering_service_alternative_lander_seo(client: TestClient) -> None:
    response = client.get("/small-business-phone-answering-service-alternative")
    assert response.status_code == 200
    text = response.text
    assert "small business phone answering service" in text.lower()
    assert "phone answering service for small business" in text.lower()
    assert "A Simpler Phone Answering Service Alternative for Small Businesses" in text
    assert "Need a small business phone answering service" in text
    assert "chained to the phone" in text.lower()
    assert absolute_public_url("/small-business-phone-answering-service-alternative") in text
    assert "Missed-Call_Safety_Net.mp4" in text
    assert "Small Business Phone Answering Service vs" in text
    assert "/phone-answering-service" in text
    assert "/backup-mode" in text


def test_small_business_answering_service_alternative_lander_seo(client: TestClient) -> None:
    response = client.get("/small-business-answering-service-alternative")
    assert response.status_code == 200
    text = response.text
    assert "small business answering service alternative" in text.lower()
    assert "small business answering service" in text.lower()
    assert "A Simpler Answering Service Alternative for Small Businesses" in text
    assert "Need a small business answering service" in text
    assert "wearing too many hats" in text.lower()
    assert absolute_public_url("/small-business-answering-service-alternative") in text
    assert "Missed-Call_Safety_Net.mp4" in text
    assert "Small Business Answering Service vs" in text
    assert "/small-business-phone-answering-service-alternative" in text
    assert "/backup-mode" in text


def test_answering_service_alternative_legacy_redirect(client: TestClient) -> None:
    response = client.get("/for/answering-service-alternative", follow_redirects=False)
    assert response.status_code == 301
    assert response.headers["location"] == "/answering-service-alternative"


def test_lander_guides_block_on_sample_pages(client: TestClient) -> None:
    for path in ("/answering-service", "/for/plumbers", "/phone-answering-service"):
        response = client.get(path)
        assert response.status_code == 200, path
        text = response.text
        assert "More answering service guides" in text
        assert "/answering-service-alternative" in text
        assert "/contractors-answering-service-alternative" in text


def test_industry_landers_link_to_hub(client: TestClient) -> None:
    for path in ("/for/plumbers", "/for/roofers", "/contractors-answering-service-alternative"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert 'href="/answering-service"' in response.text, path


def test_lander_routes_in_public_sitemap_paths() -> None:
    sitemap = set(PUBLIC_SITEMAP_PATHS)
    for path, _label in LANDER_ROUTES:
        assert path in sitemap, path


def test_priority_landers_include_missed_call_flow(client: TestClient) -> None:
    for path in PHASE_C_PRIORITY_LANDERS:
        response = client.get(path)
        assert response.status_code == 200, path
        text = response.text
        assert "catches the calls that slip through" in text, path
        assert "Missed call" in text, path
        assert "Instant text-back" in text, path
        assert "Job details captured" in text, path
        assert "Owner/team alerted" in text, path


def test_priority_landers_include_shared_cta(client: TestClient) -> None:
    for path in PHASE_C_PRIORITY_LANDERS:
        response = client.get(path)
        assert response.status_code == 200, path
        text = response.text
        assert "Stop letting missed calls become lost jobs" in text, path
        assert "Try the interactive demo" in text, path


def test_priority_landers_cta_has_analytics_attributes(client: TestClient) -> None:
    for path in PHASE_C_PRIORITY_LANDERS:
        response = client.get(path)
        assert response.status_code == 200, path
        text = response.text
        assert 'data-analytics="lander_cta"' in text, path
        assert f'data-lander="{path}"' in text, path
        assert 'data-cta="interactive_demo"' in text, path
        assert "leadcareai:lander_cta_click" in text


def test_lander_video_framing_on_sample_pages(client: TestClient) -> None:
    for path in ("/answering-service", "/business-answering-service-alternative", "/for/roofers"):
        response = client.get(path)
        assert response.status_code == 200, path
        text = response.text
        assert "This short demo shows how a missed call becomes a text conversation" in text, path
