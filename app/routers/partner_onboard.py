"""Public partner onboarding (application), IC signing, and W-9 collection."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.partner_signed_document import ELECTRONIC_CONSENT_TEXT
from app.services import (
    partner_document_service,
    partner_service,
    partner_signed_document_copy_service,
    partner_tax_service,
)
from app.templates import templates

router = APIRouter(prefix="/partner", tags=["partner"])


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    if request.client:
        return request.client.host
    return None


def _split_full_name(full_name: str) -> tuple[str, str]:
    parts = full_name.strip().split()
    if not parts:
        raise ValueError("Full name is required.")
    if len(parts) == 1:
        return parts[0], parts[0]
    return parts[0], " ".join(parts[1:])


def _parse_market_area(market_area: str) -> tuple[str, str]:
    text = market_area.strip()
    if not text:
        raise ValueError("Market area is required.")
    if "," in text:
        city_part, state_part = text.rsplit(",", 1)
        city = city_part.strip()
        state = state_part.strip()
        if not city:
            raise ValueError("Market area is required.")
        return city[:120], (state or "—")[:64]
    return text[:120], "—"


def _form_context(
    *,
    full_name: str = "",
    email: str = "",
    phone: str = "",
    market_area: str = "",
    sales_experience: str = "",
    target_industries: str = "",
    why_interested: str = "",
    ic_understanding: bool = False,
) -> dict:
    return {
        "full_name": full_name,
        "email": email,
        "phone": phone,
        "market_area": market_area,
        "sales_experience": sales_experience,
        "target_industries": target_industries,
        "why_interested": why_interested,
        "ic_understanding": ic_understanding,
    }


def _tax_form_context(
    *,
    tax_legal_name: str = "",
    tax_business_name: str = "",
    tax_address_line1: str = "",
    tax_address_line2: str = "",
    tax_city: str = "",
    tax_state: str = "",
    tax_postal_code: str = "",
    tax_classification: str = "",
    tax_tin_type: str = "",
) -> dict:
    return {
        "tax_legal_name": tax_legal_name,
        "tax_business_name": tax_business_name,
        "tax_address_line1": tax_address_line1,
        "tax_address_line2": tax_address_line2,
        "tax_city": tax_city,
        "tax_state": tax_state,
        "tax_postal_code": tax_postal_code,
        "tax_classification": tax_classification,
        "tax_tin_type": tax_tin_type,
    }


def _render_onboard_form(
    request: Request,
    *,
    error: str | None,
    form: dict,
    status_code: int = 200,
):
    return templates.TemplateResponse(
        request,
        "partner/onboard/index.html",
        {"error": error, "form": form},
        status_code=status_code,
    )


@router.get("/onboard", response_class=HTMLResponse, response_model=None)
def partner_onboard_form(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    return _render_onboard_form(request, error=None, form=_form_context())


@router.post("/onboard", response_model=None)
def partner_onboard_submit(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    full_name: str = Form(""),
    email: str = Form(""),
    phone: str = Form(""),
    market_area: str = Form(""),
    sales_experience: str = Form(""),
    target_industries: str = Form(""),
    why_interested: str = Form(""),
    ic_understanding: str = Form(""),
):
    form = _form_context(
        full_name=full_name,
        email=email,
        phone=phone,
        market_area=market_area,
        sales_experience=sales_experience,
        target_industries=target_industries,
        why_interested=why_interested,
        ic_understanding=ic_understanding == "on",
    )

    try:
        if ic_understanding != "on":
            raise ValueError(
                "You must confirm that you understand this is commission-based work "
                "and no income is guaranteed."
            )
        if not sales_experience.strip():
            raise ValueError("Sales experience is required.")
        if not target_industries.strip():
            raise ValueError("Please describe businesses or industries you would contact first.")
        if not why_interested.strip():
            raise ValueError("Please tell us why you are interested.")

        first_name, last_name = _split_full_name(full_name)
        city, state = _parse_market_area(market_area)

        application = partner_service.create_application(
            db,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            city=city,
            state=state,
            company_name=target_industries.strip(),
            experience_summary=sales_experience.strip(),
            why_interested=why_interested.strip(),
        )
        partner_service.mark_application_admin_review(db, application.id)
        db.commit()
    except ValueError as exc:
        db.rollback()
        return _render_onboard_form(
            request,
            error=str(exc),
            form=form,
            status_code=400,
        )

    return RedirectResponse(url="/partner/onboard/success", status_code=303)


@router.get("/onboard/success", response_class=HTMLResponse, response_model=None)
def partner_onboard_success(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "partner/onboard/success.html", {})


def _render_sign_documents(
    request: Request,
    *,
    application,
    documents,
    token: str,
    error: str | None = None,
    signature_text: str = "",
    status_code: int = 200,
):
    return templates.TemplateResponse(
        request,
        "partner/sign_documents/index.html",
        {
            "application": application,
            "documents": documents,
            "token": token,
            "error": error,
            "consent_text": ELECTRONIC_CONSENT_TEXT,
            "signature_text": signature_text,
        },
        status_code=status_code,
    )


def _render_tax_info_form(
    request: Request,
    *,
    application,
    token: str,
    error: str | None = None,
    form: dict | None = None,
    status_code: int = 200,
):
    return templates.TemplateResponse(
        request,
        "partner/tax_info/index.html",
        {
            "application": application,
            "token": token,
            "error": error,
            "form": form or _tax_form_context(),
            "tax_classifications": sorted(partner_tax_service.TAX_CLASSIFICATIONS),
        },
        status_code=status_code,
    )


@router.get("/sign-documents", response_class=HTMLResponse, response_model=None)
def partner_sign_documents_form(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    token: str = Query(""),
):
    application = partner_service.get_application_by_docs_signing_token(db, token)
    if application is None:
        return templates.TemplateResponse(
            request,
            "partner/sign_documents/invalid.html",
            {},
            status_code=404,
        )

    if application.status == partner_service.APPLICATION_STATUS_DOCS_SIGNED:
        if partner_tax_service.get_partner_tax_info_for_application(db, application.id):
            return RedirectResponse(url="/partner/sign-documents/success", status_code=303)
        return templates.TemplateResponse(
            request,
            "partner/sign_documents/invalid.html",
            {
                "error": (
                    "Your documents are already signed. "
                    "Use the W-9 link from your onboarding contact to submit tax information."
                ),
            },
            status_code=404,
        )

    partner_document_service.seed_default_document_templates(db)
    db.commit()
    documents = partner_document_service.list_active_document_templates(db)
    if not documents:
        return templates.TemplateResponse(
            request,
            "partner/sign_documents/invalid.html",
            {"error": "Documents are not configured. Please contact support."},
            status_code=503,
        )

    return _render_sign_documents(
        request,
        application=application,
        documents=documents,
        token=token,
    )


@router.post("/sign-documents", response_model=None)
def partner_sign_documents_submit(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    token: str = Query(""),
    signature_text: str = Form(""),
    electronic_consent: str = Form(""),
):
    application = partner_service.get_application_by_docs_signing_token(db, token)
    if application is None:
        return templates.TemplateResponse(
            request,
            "partner/sign_documents/invalid.html",
            {},
            status_code=404,
        )

    if application.status == partner_service.APPLICATION_STATUS_DOCS_SIGNED:
        if partner_tax_service.get_partner_tax_info_for_application(db, application.id):
            return RedirectResponse(url="/partner/sign-documents/success", status_code=303)
        return templates.TemplateResponse(
            request,
            "partner/sign_documents/invalid.html",
            {
                "error": (
                    "Your documents are already signed. "
                    "Use the W-9 link from your onboarding contact to submit tax information."
                ),
            },
            status_code=404,
        )

    partner_document_service.seed_default_document_templates(db)
    documents = partner_document_service.list_active_document_templates(db)

    if electronic_consent != "on":
        return _render_sign_documents(
            request,
            application=application,
            documents=documents,
            token=token,
            error="You must agree to electronic records and signatures.",
            signature_text=signature_text,
            status_code=400,
        )

    if not documents:
        return templates.TemplateResponse(
            request,
            "partner/sign_documents/invalid.html",
            {"error": "Documents are not configured. Please contact support."},
            status_code=503,
        )

    try:
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
        _, tax_token = partner_service.mark_application_docs_signed(db, application.id)
        db.commit()
        signed_docs = partner_service.list_signed_documents_for_application(db, application.id)
        partner_signed_document_copy_service.send_signed_document_copy_emails(
            application=application,
            signed_documents=signed_docs,
        )
    except ValueError as exc:
        db.rollback()
        return _render_sign_documents(
            request,
            application=application,
            documents=documents,
            token=token,
            error=str(exc),
            signature_text=signature_text,
            status_code=400,
        )

    if tax_token:
        return RedirectResponse(
            url=f"/partner/tax-info?token={tax_token}",
            status_code=303,
        )
    return RedirectResponse(url="/partner/sign-documents/success", status_code=303)


@router.get("/sign-documents/success", response_class=HTMLResponse, response_model=None)
def partner_sign_documents_success(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "partner/sign_documents/success.html", {})


@router.get("/tax-info", response_class=HTMLResponse, response_model=None)
def partner_tax_info_form(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    token: str = Query(""),
):
    application = partner_service.get_application_by_tax_info_token(db, token)
    if application is None:
        return templates.TemplateResponse(
            request,
            "partner/tax_info/invalid.html",
            {},
            status_code=404,
        )

    if partner_tax_service.get_partner_tax_info_for_application(db, application.id):
        return RedirectResponse(url="/partner/tax-info/success", status_code=303)

    default_name = f"{application.first_name} {application.last_name}"
    return _render_tax_info_form(
        request,
        application=application,
        token=token,
        form=_tax_form_context(tax_legal_name=default_name),
    )


@router.post("/tax-info", response_model=None)
def partner_tax_info_submit(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    token: str = Query(""),
    tax_legal_name: str = Form(""),
    tax_business_name: str = Form(""),
    tax_address_line1: str = Form(""),
    tax_address_line2: str = Form(""),
    tax_city: str = Form(""),
    tax_state: str = Form(""),
    tax_postal_code: str = Form(""),
    tax_classification: str = Form(""),
    tax_tin_type: str = Form(""),
    tax_tin: str = Form(""),
    tax_certification: str = Form(""),
):
    application = partner_service.get_application_by_tax_info_token(db, token)
    if application is None:
        return templates.TemplateResponse(
            request,
            "partner/tax_info/invalid.html",
            {},
            status_code=404,
        )

    if partner_tax_service.get_partner_tax_info_for_application(db, application.id):
        return RedirectResponse(url="/partner/tax-info/success", status_code=303)

    form = _tax_form_context(
        tax_legal_name=tax_legal_name,
        tax_business_name=tax_business_name,
        tax_address_line1=tax_address_line1,
        tax_address_line2=tax_address_line2,
        tax_city=tax_city,
        tax_state=tax_state,
        tax_postal_code=tax_postal_code,
        tax_classification=tax_classification,
        tax_tin_type=tax_tin_type,
    )

    try:
        tax_data = partner_tax_service.validate_partner_tax_info(
            legal_name=tax_legal_name,
            business_name=tax_business_name or None,
            address_line1=tax_address_line1,
            address_line2=tax_address_line2 or None,
            city=tax_city,
            state=tax_state,
            postal_code=tax_postal_code,
            tax_classification=tax_classification,
            tin_type=tax_tin_type,
            tin=tax_tin,
            tax_certified=tax_certification == "on",
        )
        partner_tax_service.create_partner_tax_info_for_application(
            db,
            application_id=application.id,
            data=tax_data,
        )
        partner_service.clear_tax_info_token(db, application.id)
        db.commit()
    except ValueError as exc:
        db.rollback()
        return _render_tax_info_form(
            request,
            application=application,
            token=token,
            error=str(exc),
            form=form,
            status_code=400,
        )

    return RedirectResponse(url="/partner/tax-info/success", status_code=303)


@router.get("/tax-info/success", response_class=HTMLResponse, response_model=None)
def partner_tax_info_success(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "partner/tax_info/success.html", {})
