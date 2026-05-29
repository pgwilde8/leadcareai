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
from app.services import call_forwarding_service, lead_service, message_service, phone_number_service
from app.services import business_settings_service
from app.services import notification_service
from app.services.lead_service import BUSINESS_SELECTABLE_STATUSES, LEAD_STATUSES
from app.templates import templates

router = APIRouter(prefix="/business", tags=["business"])


def _require_business(request: Request, db: Session) -> tuple[User, Business] | RedirectResponse:
    return require_business_user(request, db)


def _settings_form_from_business(business: Business) -> dict[str, str]:
    mobile_value = ""
    if business.customer_phone_is_mobile is True:
        mobile_value = "yes"
    elif business.customer_phone_is_mobile is False:
        mobile_value = "no"
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
        "customer_phone_is_mobile": mobile_value,
        "customer_phone_carrier": business.customer_phone_carrier or "",
    }


def _business_page_context(
    *,
    user: User,
    business: Business,
    extra: dict | None = None,
) -> dict:
    ctx = {
        "user": user,
        "business": business,
        "forwarding_incomplete": not call_forwarding_service.is_forwarding_setup_complete(business),
        "forwarding_banner_message": call_forwarding_service.INCOMPLETE_BANNER_MESSAGE,
    }
    if extra:
        ctx.update(extra)
    return ctx


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
        _business_page_context(user=user, business=business, extra={"stats": stats}),
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
        _business_page_context(
            user=user,
            business=business,
            extra={
                "inbox_rows": inbox_rows,
                "recommended_action_for_lead": lead_service.recommended_action_for_lead,
            },
        ),
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

    detail_ctx = _lead_detail_context(db, user=user, business=business, lead=lead)
    detail_ctx.update(
        {
            "forwarding_incomplete": not call_forwarding_service.is_forwarding_setup_complete(
                business
            ),
            "forwarding_banner_message": call_forwarding_service.INCOMPLETE_BANNER_MESSAGE,
        }
    )
    return templates.TemplateResponse(request, "business/lead_detail.html", detail_ctx)


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
        _business_page_context(
            user=user,
            business=business,
            extra={
                "phone_numbers": phone_numbers,
                "form": _settings_form_from_business(business),
                "default_missed_call_message": business_settings_service.preview_default_missed_call_message(
                    business
                ),
                "saved": saved == 1,
                "error": None,
                "carrier_choices": call_forwarding_service.CARRIER_LABELS,
            },
        ),
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
    customer_phone_is_mobile: str = Form(""),
    customer_phone_carrier: str = Form(""),
    can_access_phone_during_onboarding: str = Form(""),
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
        "customer_phone_is_mobile": customer_phone_is_mobile,
        "customer_phone_carrier": customer_phone_carrier,
    }
    try:
        mobile_raw = customer_phone_is_mobile.strip().lower()
        mobile_bool: bool | None = None
        if mobile_raw == "yes":
            mobile_bool = True
        elif mobile_raw == "no":
            mobile_bool = False
        elif mobile_raw:
            raise ValueError("Please indicate whether your customer-facing number is a mobile phone")

        can_access = can_access_phone_during_onboarding.strip().lower() == "yes"

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
            customer_phone_is_mobile=mobile_bool,
            customer_phone_carrier=customer_phone_carrier or None,
            can_access_phone_during_onboarding=False if not can_access else None,
        )
        db.commit()
    except ValueError as exc:
        phone_numbers = phone_number_service.list_phone_numbers_for_business(db, business.id)
        db.refresh(business)
        return templates.TemplateResponse(
            request,
            "business/settings.html",
            _business_page_context(
                user=user,
                business=business,
                extra={
                    "phone_numbers": phone_numbers,
                    "form": form,
                    "default_missed_call_message": business_settings_service.preview_default_missed_call_message(
                        business
                    ),
                    "saved": False,
                    "error": str(exc),
                    "carrier_choices": call_forwarding_service.CARRIER_LABELS,
                },
            ),
            status_code=400,
        )

    return RedirectResponse(url="/business/settings?saved=1", status_code=303)


def _backup_mode_page_response(
    request: Request,
    *,
    user: User,
    business: Business,
    db: Session,
):
    call_forwarding_service.mark_instructions_sent(db, business.id)
    db.commit()
    db.refresh(business)

    assigned = call_forwarding_service.get_assigned_leadcare_number(db, business.id)
    assigned_display = (
        call_forwarding_service.format_phone_for_display(assigned.phone_number)
        if assigned
        else None
    )
    leadcare_e164 = assigned.phone_number if assigned else None
    guidance = call_forwarding_service.get_carrier_guidance(
        business.customer_phone_carrier,
        leadcare_e164,
    )

    return templates.TemplateResponse(
        request,
        "business/backup_mode.html",
        _business_page_context(
            user=user,
            business=business,
            extra={
                "assigned_number": assigned,
                "assigned_number_display": assigned_display,
                "guidance": guidance,
                "backup_mode_subtitle": call_forwarding_service.BACKUP_MODE_SUBTITLE,
                "backup_mode_plain_language": call_forwarding_service.BACKUP_MODE_PLAIN_LANGUAGE,
                "setup_checklist": call_forwarding_service.SETUP_CHECKLIST_ITEMS,
                "carrier_caveat": call_forwarding_service.CARRIER_CAVEAT,
                "carrier_label": call_forwarding_service.carrier_display_label(
                    business.customer_phone_carrier
                ),
                "status_label": business.customer_phone_forwarding_status.replace("_", " "),
                "setup_complete": call_forwarding_service.is_forwarding_setup_complete(business),
            },
        ),
    )


@router.get("/backup-mode", response_class=HTMLResponse, response_model=None)
def business_backup_mode_page(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    auth = _require_business(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    user, business = auth
    return _backup_mode_page_response(request, user=user, business=business, db=db)


@router.get("/call-forwarding", response_class=HTMLResponse, response_model=None)
def business_call_forwarding_page(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    """Legacy URL; same Backup Mode page for compatibility."""
    auth = _require_business(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    user, business = auth
    return _backup_mode_page_response(request, user=user, business=business, db=db)


def _mark_backup_mode_attempted(
    request: Request,
    db: Session,
) -> RedirectResponse | None:
    auth = _require_business(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    _user, business = auth
    call_forwarding_service.mark_customer_attempted(db, business.id)
    db.commit()
    return None


@router.post("/backup-mode/attempted", response_model=None)
def business_backup_mode_attempted(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    redirect = _mark_backup_mode_attempted(request, db)
    if redirect is not None:
        return redirect
    return RedirectResponse(url="/business/backup-mode", status_code=303)


@router.post("/call-forwarding/attempted", response_model=None)
def business_call_forwarding_attempted(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    redirect = _mark_backup_mode_attempted(request, db)
    if redirect is not None:
        return redirect
    return RedirectResponse(url="/business/backup-mode", status_code=303)
