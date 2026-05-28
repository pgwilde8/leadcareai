"""Public marketing, legal, and demo intake pages."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.services import business_lead_service, contact_service, demo_live_service
from app.services.referral_service import (
    capture_referral_code,
    get_active_partner_by_referral_code,
    get_referral_from_session,
    resolve_referral_partner,
)
from app.templates import templates

router = APIRouter(tags=["public"])


def _privacy(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "legal/privacy.html", {})


def _terms(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "legal/terms.html", {})


def _sms(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "legal/sms.html", {})


def _refund_policy(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "legal/refund-policy.html", {})


@router.get("/about", response_class=HTMLResponse, response_model=None)
def about_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "public/about.html", {})


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64] or None
    if request.client:
        return request.client.host
    return None


@router.get("/contact", response_class=HTMLResponse, response_model=None)
def contact_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "public/contact.html",
        {
            "error": None,
            "form": contact_service.contact_form_defaults(),
            "subjects": sorted(contact_service.CONTACT_SUBJECTS),
        },
    )


@router.post("/contact", response_model=None)
def contact_submit(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    subject: str = Form("General inquiry"),
    message: str = Form(""),
    website: str = Form(""),
):
    """Honeypot field `website` must stay empty."""
    form = {
        "name": name,
        "email": email,
        "phone": phone,
        "subject": subject,
        "message": message,
    }
    if website.strip():
        return RedirectResponse(url="/contact/success", status_code=303)

    try:
        contact_service.submit_contact_message(
            db,
            name=name,
            email=email,
            phone=phone or None,
            subject=subject,
            message=message,
            ip_address=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "public/contact.html",
            {
                "error": str(exc),
                "form": form,
                "subjects": sorted(contact_service.CONTACT_SUBJECTS),
            },
            status_code=400,
        )

    return RedirectResponse(url="/contact/success", status_code=303)


@router.get("/contact/success", response_class=HTMLResponse, response_model=None)
def contact_success(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "public/contact_success.html", {})


@router.get("/partners", response_class=HTMLResponse, response_model=None)
def partners_opportunity_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "public/partners.html", {})


@router.get("/r/{referral_code}", response_class=HTMLResponse, response_model=None)
def referral_landing_page(
    request: Request,
    referral_code: str,
    db: Annotated[Session, Depends(get_db)],
):
    partner = get_active_partner_by_referral_code(db, referral_code)
    if partner is None:
        return RedirectResponse(url="/", status_code=302)

    settings = get_settings()
    base = settings.effective_public_base_url or settings.app_base_url.rstrip("/")
    code = partner.referral_code
    response = templates.TemplateResponse(
        request,
        "public/referral_landing.html",
        {
            "partner": partner,
            "referral_code": code,
            "demo_link": f"{base}/demo?ref={code}",
            "demo_book_link": f"{base}/demo/book?ref={code}",
        },
    )
    capture_referral_code(db, request, response, code)
    return response


@router.get("/", response_class=HTMLResponse, response_model=None)
def landing_page(request: Request, db: Annotated[Session, Depends(get_db)]):
    referral_code, _ = get_referral_from_session(request)
    partner = resolve_referral_partner(db, request)
    return templates.TemplateResponse(
        request,
        "public/landing.html",
        {
            "referral_code": referral_code,
            "referral_partner_name": partner.display_name if partner else None,
        },
    )


@router.get("/demo", response_class=HTMLResponse, response_model=None)
def demo_live_page(request: Request):
    return templates.TemplateResponse(
        request,
        "public/demo.html",
        {
            "demo_business_name": demo_live_service.DEMO_BUSINESS_DISPLAY_NAME,
            "demo_phone_display": demo_live_service.DEMO_PHONE_DISPLAY,
        },
    )


@router.get("/demo/dashboard", response_class=HTMLResponse, response_model=None)
def demo_dashboard_page(request: Request, db: Annotated[Session, Depends(get_db)]):
    settings = get_settings()
    rows = demo_live_service.list_public_demo_leads(db) if demo_live_service.is_demo_enabled(settings) else []
    return templates.TemplateResponse(
        request,
        "public/demo_dashboard.html",
        {
            "demo_enabled": demo_live_service.is_demo_enabled(settings),
            "demo_business_name": demo_live_service.DEMO_BUSINESS_DISPLAY_NAME,
            "rows": rows,
        },
    )


@router.get("/demo/book", response_class=HTMLResponse, response_model=None)
def demo_book_form(request: Request, db: Annotated[Session, Depends(get_db)]):
    referral_code, _ = get_referral_from_session(request)
    partner = resolve_referral_partner(db, request)
    return templates.TemplateResponse(
        request,
        "public/demo_book.html",
        {
            "error": None,
            "form": {},
            "referral_code": referral_code,
            "referral_partner_name": partner.display_name if partner else None,
        },
    )


@router.post("/demo/book", response_model=None)
def demo_book_submit(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    business_name: str = Form(""),
    contact_name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    industry: str = Form(""),
    city: str = Form(""),
    state: str = Form(""),
    notes: str = Form(""),
):
    referral_code, _ = get_referral_from_session(request)
    partner = resolve_referral_partner(db, request)

    form = {
        "business_name": business_name,
        "contact_name": contact_name,
        "email": email,
        "phone": phone,
        "industry": industry,
        "city": city,
        "state": state,
        "notes": notes,
    }

    try:
        business_lead_service.create_demo_lead(
            db,
            business_name=business_name,
            contact_name=contact_name,
            email=email,
            phone=phone,
            city=city,
            state=state,
            industry=industry or None,
            notes=notes or None,
            partner=partner,
            referral_code=partner.referral_code if partner else referral_code,
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        return templates.TemplateResponse(
            request,
            "public/demo_book.html",
            {
                "error": str(exc),
                "form": form,
                "referral_code": referral_code,
                "referral_partner_name": partner.display_name if partner else None,
            },
            status_code=400,
        )

    return RedirectResponse(url="/demo/book/success", status_code=303)


@router.get("/demo/book/success", response_class=HTMLResponse, response_model=None)
def demo_book_success(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "public/demo_success.html", {})


@router.get("/billing/success", response_class=HTMLResponse, response_model=None)
def billing_success(request: Request) -> HTMLResponse:
    session_id = request.query_params.get("session_id", "")
    return templates.TemplateResponse(
        request,
        "public/billing_success.html",
        {"session_id": session_id},
    )


@router.get("/privacy", response_class=HTMLResponse, response_model=None)
def privacy(request: Request) -> HTMLResponse:
    return _privacy(request)


@router.get("/terms", response_class=HTMLResponse, response_model=None)
def terms(request: Request) -> HTMLResponse:
    return _terms(request)


@router.get("/sms", response_class=HTMLResponse, response_model=None)
def sms(request: Request) -> HTMLResponse:
    return _sms(request)


@router.get("/refund-policy", response_class=HTMLResponse, response_model=None)
def refund_policy(request: Request) -> HTMLResponse:
    return _refund_policy(request)


@router.get("/legal/privacy", response_class=HTMLResponse, response_model=None)
def legal_privacy(request: Request) -> HTMLResponse:
    return _privacy(request)


@router.get("/legal/terms", response_class=HTMLResponse, response_model=None)
def legal_terms(request: Request) -> HTMLResponse:
    return _terms(request)


@router.get("/legal/sms", response_class=HTMLResponse, response_model=None)
def legal_sms(request: Request) -> HTMLResponse:
    return _sms(request)


@router.get("/legal/refund-policy", response_class=HTMLResponse, response_model=None)
def legal_refund_policy(request: Request) -> HTMLResponse:
    return _refund_policy(request)
