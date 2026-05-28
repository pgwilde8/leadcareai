"""Public marketing, legal, and demo intake pages."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services import business_lead_service
from app.services.referral_service import get_referral_from_session, resolve_referral_partner
from app.templates import templates

router = APIRouter(tags=["public"])


def _privacy(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "legal/privacy.html", {})


def _terms(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "legal/terms.html", {})


def _sms(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "legal/sms.html", {})


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
def demo_form(request: Request, db: Annotated[Session, Depends(get_db)]):
    referral_code, _ = get_referral_from_session(request)
    partner = resolve_referral_partner(db, request)
    return templates.TemplateResponse(
        request,
        "public/demo.html",
        {
            "error": None,
            "form": {},
            "referral_code": referral_code,
            "referral_partner_name": partner.display_name if partner else None,
        },
    )


@router.post("/demo", response_model=None)
def demo_submit(
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
            "public/demo.html",
            {
                "error": str(exc),
                "form": form,
                "referral_code": referral_code,
                "referral_partner_name": partner.display_name if partner else None,
            },
            status_code=400,
        )

    return RedirectResponse(url="/demo/success", status_code=303)


@router.get("/demo/success", response_class=HTMLResponse, response_model=None)
def demo_success(request: Request) -> HTMLResponse:
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


@router.get("/legal/privacy", response_class=HTMLResponse, response_model=None)
def legal_privacy(request: Request) -> HTMLResponse:
    return _privacy(request)


@router.get("/legal/terms", response_class=HTMLResponse, response_model=None)
def legal_terms(request: Request) -> HTMLResponse:
    return _terms(request)


@router.get("/legal/sms", response_class=HTMLResponse, response_model=None)
def legal_sms(request: Request) -> HTMLResponse:
    return _sms(request)
