"""Public partner onboarding (application + e-sign)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.partner_signed_document import ELECTRONIC_CONSENT_TEXT
from app.services import partner_document_service, partner_service
from app.templates import templates

router = APIRouter(prefix="/partner", tags=["partner"])


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


@router.get("/onboard", response_class=HTMLResponse, response_model=None)
def partner_onboard_form(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    partner_document_service.seed_default_document_templates(db)
    db.commit()
    documents = partner_document_service.list_active_document_templates(db)
    return templates.TemplateResponse(
        request,
        "partner/onboard/index.html",
        {
            "error": None,
            "documents": documents,
            "consent_text": ELECTRONIC_CONSENT_TEXT,
            "form": {},
        },
    )


@router.post("/onboard", response_model=None)
def partner_onboard_submit(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    first_name: str = Form(""),
    last_name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    city: str = Form(""),
    state: str = Form(""),
    company_name: str = Form(""),
    experience_summary: str = Form(""),
    why_interested: str = Form(""),
    signature_text: str = Form(""),
    electronic_consent: str = Form(""),
):
    partner_document_service.seed_default_document_templates(db)
    documents = partner_document_service.list_active_document_templates(db)

    form = {
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "phone": phone,
        "city": city,
        "state": state,
        "company_name": company_name,
        "experience_summary": experience_summary,
        "why_interested": why_interested,
        "signature_text": signature_text,
    }

    if electronic_consent != "on":
        return templates.TemplateResponse(
            request,
            "partner/onboard/index.html",
            {
                "error": "You must agree to electronic records and signatures to apply.",
                "documents": documents,
                "consent_text": ELECTRONIC_CONSENT_TEXT,
                "form": form,
            },
            status_code=400,
        )

    if not documents:
        return templates.TemplateResponse(
            request,
            "partner/onboard/index.html",
            {
                "error": "Partner documents are not configured. Please contact support.",
                "documents": [],
                "consent_text": ELECTRONIC_CONSENT_TEXT,
                "form": form,
            },
            status_code=503,
        )

    try:
        application = partner_service.create_application(
            db,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            city=city,
            state=state,
            company_name=company_name or None,
            experience_summary=experience_summary or None,
            why_interested=why_interested or None,
        )
        signer_name = f"{application.first_name} {application.last_name}"
        partner_document_service.sign_documents_for_application(
            db,
            application_id=application.id,
            templates=documents,
            signer_name=signer_name,
            signer_email=application.email,
            signature_text=signature_text,
            ip_address=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
        partner_service.mark_application_admin_review(db, application.id)
        db.commit()
    except ValueError as exc:
        db.rollback()
        return templates.TemplateResponse(
            request,
            "partner/onboard/index.html",
            {
                "error": str(exc),
                "documents": documents,
                "consent_text": ELECTRONIC_CONSENT_TEXT,
                "form": form,
            },
            status_code=400,
        )

    return RedirectResponse(url="/partner/onboard/success", status_code=303)


@router.get("/onboard/success", response_class=HTMLResponse, response_model=None)
def partner_onboard_success(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "partner/onboard/success.html", {})
