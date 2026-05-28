"""Business dashboard — lead inbox and detail (session-protected)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.business import Business
from app.models.user import User
from app.routers.auth import require_business_user
from app.services import lead_service, message_service, phone_number_service
from app.services import business_settings_service
from app.services import notification_service
from app.services.lead_service import BUSINESS_SELECTABLE_STATUSES, LEAD_STATUSES
from app.templates import templates

router = APIRouter(prefix="/business", tags=["business"])


def _require_business(request: Request, db: Session) -> tuple[User, Business] | RedirectResponse:
    return require_business_user(request, db)


def _settings_form_from_business(business: Business) -> dict[str, str]:
    return {
        "name": business.name or "",
        "industry": business.industry or "",
        "website_url": business.website_url or "",
        "contact_email": business.contact_email or "",
        "contact_phone": business.main_phone or "",
        "notification_email": business.notification_email or "",
        "notification_phone": business.notification_phone or "",
        "missed_call_textback_message": business.missed_call_textback_message or "",
        "sms_signature": business.sms_signature or "",
        "lead_intake_prompt": business.lead_intake_prompt or "",
    }


def _lead_detail_context(
    db: Session,
    *,
    user: User,
    business: Business,
    lead,
    status_error: str | None = None,
) -> dict:
    recent_notifications = notification_service.list_recent_notifications_for_lead(
        db,
        business_id=business.id,
        lead_id=lead.id,
        limit=5,
    )
    return {
        "user": user,
        "business": business,
        "lead": lead,
        "messages": message_service.list_messages_for_lead(db, lead.id),
        "recommended_action": lead_service.recommended_action_for_lead(lead),
        "recent_notifications": recent_notifications,
        "statuses": list(BUSINESS_SELECTABLE_STATUSES),
        "status_error": status_error,
    }


@router.get("/dashboard", response_class=HTMLResponse, response_model=None)
def business_dashboard(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    auth = _require_business(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    user, business = auth
    stats = lead_service.dashboard_lead_counts(db, business.id)

    return templates.TemplateResponse(
        request,
        "business/dashboard.html",
        {
            "user": user,
            "business": business,
            "stats": stats,
        },
    )


@router.get("/leads", response_class=HTMLResponse, response_model=None)
def business_leads_list(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    auth = _require_business(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    user, business = auth
    inbox_rows = lead_service.list_lead_inbox_for_business(db, business.id)

    return templates.TemplateResponse(
        request,
        "business/leads.html",
        {
            "user": user,
            "business": business,
            "inbox_rows": inbox_rows,
            "recommended_action_for_lead": lead_service.recommended_action_for_lead,
        },
    )


@router.get("/leads/{lead_id}", response_class=HTMLResponse, response_model=None)
def business_lead_detail(
    request: Request,
    lead_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
):
    auth = _require_business(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    user, business = auth
    try:
        lead = lead_service.get_lead_for_business(db, business.id, lead_id)
    except ValueError:
        return RedirectResponse(url="/business/leads", status_code=303)

    return templates.TemplateResponse(
        request,
        "business/lead_detail.html",
        _lead_detail_context(db, user=user, business=business, lead=lead),
    )


@router.post("/leads/{lead_id}/status", response_model=None)
def business_lead_status_update(
    request: Request,
    lead_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    status: str = Form(""),
):
    auth = _require_business(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    user, business = auth
    try:
        lead = lead_service.get_lead_for_business(db, business.id, lead_id)
        if status not in LEAD_STATUSES:
            raise ValueError(f"Invalid lead status: {status!r}")
        lead_service.update_lead_status(db, lead_id, status)
        db.commit()
    except ValueError as exc:
        try:
            lead = lead_service.get_lead_for_business(db, business.id, lead_id)
        except ValueError:
            return RedirectResponse(url="/business/leads", status_code=303)

        return templates.TemplateResponse(
            request,
            "business/lead_detail.html",
            _lead_detail_context(
                db,
                user=user,
                business=business,
                lead=lead,
                status_error=str(exc),
            ),
            status_code=400,
        )

    return RedirectResponse(url=f"/business/leads/{lead_id}", status_code=303)


@router.get("/settings", response_class=HTMLResponse, response_model=None)
def business_settings_page(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    saved: int = 0,
):
    auth = _require_business(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    user, business = auth
    phone_numbers = phone_number_service.list_phone_numbers_for_business(db, business.id)

    return templates.TemplateResponse(
        request,
        "business/settings.html",
        {
            "user": user,
            "business": business,
            "phone_numbers": phone_numbers,
            "form": _settings_form_from_business(business),
            "default_missed_call_message": business_settings_service.preview_default_missed_call_message(
                business
            ),
            "saved": saved == 1,
            "error": None,
        },
    )


@router.post("/settings", response_model=None)
def business_settings_save(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    name: str = Form(""),
    industry: str = Form(""),
    website_url: str = Form(""),
    contact_email: str = Form(""),
    contact_phone: str = Form(""),
    notification_email: str = Form(""),
    notification_phone: str = Form(""),
    missed_call_textback_message: str = Form(""),
    sms_signature: str = Form(""),
    lead_intake_prompt: str = Form(""),
):
    auth = _require_business(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    user, business = auth
    form = {
        "name": name,
        "industry": industry,
        "website_url": website_url,
        "contact_email": contact_email,
        "contact_phone": contact_phone,
        "notification_email": notification_email,
        "notification_phone": notification_phone,
        "missed_call_textback_message": missed_call_textback_message,
        "sms_signature": sms_signature,
        "lead_intake_prompt": lead_intake_prompt,
    }

    try:
        business_settings_service.update_business_settings(
            db,
            business.id,
            name=name,
            industry=industry or None,
            website_url=website_url or None,
            contact_email=contact_email or None,
            contact_phone=contact_phone or None,
            notification_email=notification_email or None,
            notification_phone=notification_phone or None,
            missed_call_textback_message=missed_call_textback_message or None,
            sms_signature=sms_signature or None,
            lead_intake_prompt=lead_intake_prompt or None,
        )
        db.commit()
    except ValueError as exc:
        phone_numbers = phone_number_service.list_phone_numbers_for_business(db, business.id)
        db.refresh(business)
        return templates.TemplateResponse(
            request,
            "business/settings.html",
            {
                "user": user,
                "business": business,
                "phone_numbers": phone_numbers,
                "form": form,
                "default_missed_call_message": business_settings_service.preview_default_missed_call_message(
                    business
                ),
                "saved": False,
                "error": str(exc),
            },
            status_code=400,
        )

    return RedirectResponse(url="/business/settings?saved=1", status_code=303)
