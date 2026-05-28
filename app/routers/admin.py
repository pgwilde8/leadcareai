"""Admin dashboard routes (session-protected)."""

from __future__ import annotations

import uuid
from urllib.parse import quote_plus
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import text
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.core.database import get_db
from app.models.business import Business
from app.models.business_user import BusinessUser
from app.models.commission import COMMISSION_STATUSES, Commission
from app.models.lead import Lead
from app.models.notification_log import NotificationLog
from app.models.user import User
from app.routers.auth import require_admin
from app.services import (
    business_lead_checkout_service,
    business_lead_service,
    business_service,
    commission_service,
    compliance_service,
    demo_service,
    lead_service,
    message_service,
    partner_service,
    phone_number_service,
    user_invite_service,
)
from app.services.compliance_service import COMPLIANCE_STATUSES
from app.services.lead_service import LEAD_STATUSES
from app.services import user_access_service
from app.services.user_service import get_user_by_email, get_user_by_id
from app.templates import templates

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin(request: Request, db: Session) -> User | RedirectResponse:
    return require_admin(request, db)


def _mask_recipient(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return "—"
    if "@" in raw:
        local, _, domain = raw.partition("@")
        local_mask = (local[:1] + "***") if local else "***"
        return f"{local_mask}@{domain}"
    if len(raw) <= 4:
        return "*" * len(raw)
    return f"{'*' * (len(raw) - 4)}{raw[-4:]}"


def _error_summary(value: str | None, max_len: int = 120) -> str:
    if not value:
        return ""
    text_value = value.strip()
    if len(text_value) <= max_len:
        return text_value
    return text_value[: max_len - 1] + "…"


def _system_checks(db: Session) -> list[dict[str, str]]:
    settings = get_settings()

    db_status = "no"
    try:
        db.execute(text("SELECT 1"))
        db_status = "yes"
    except Exception:
        db_status = "no"

    checks = [
        {"name": "PUBLIC_BASE_URL configured", "value": "yes" if bool(settings.public_base_url) else "no"},
        {"name": "TWILIO_ACCOUNT_SID configured", "value": "yes" if bool(settings.twilio_account_sid) else "no"},
        {"name": "TWILIO_AUTH_TOKEN configured", "value": "yes" if bool(settings.twilio_auth_token) else "no"},
        {"name": "TWILIO_PHONE_NUMBER configured", "value": "yes" if bool(settings.twilio_phone_number) else "no"},
        {"name": "TWILIO_WEBHOOK_AUTH_ENABLED", "value": "true" if settings.twilio_webhook_auth_enabled else "false"},
        {"name": "OPENAI_API_KEY configured", "value": "yes" if bool(settings.openai_api_key) else "no"},
        {"name": "OPENAI_ENABLED", "value": "true" if settings.openai_enabled else "false"},
        {"name": "SMTP_HOST configured", "value": "yes" if bool(settings.smtp_host) else "no"},
        {"name": "SMTP_FROM_EMAIL configured", "value": "yes" if bool(settings.smtp_from_email) else "no"},
        {"name": "STRIPE_SECRET_KEY configured", "value": "yes" if bool(settings.stripe_secret_key) else "no"},
        {"name": "STRIPE_WEBHOOK_SECRET configured", "value": "yes" if bool(settings.stripe_webhook_secret) else "no"},
        {
            "name": "STRIPE_PRICE_ID_GROWTH_MONTHLY configured",
            "value": "yes" if bool(settings.stripe_price_id_growth_monthly) else "no",
        },
        {
            "name": "STRIPE_PRICE_ID_SETUP_FEE configured",
            "value": "yes" if bool(settings.stripe_price_id_setup_fee) else "no",
        },
        {"name": "Database reachable", "value": db_status},
    ]
    return checks


def _demo_business_context(db: Session) -> tuple[Business | None, str | None]:
    settings = get_settings()
    raw_id = (settings.demo_business_id or "").strip()
    if not settings.demo_enabled or not raw_id:
        return None, None
    try:
        business_id = uuid.UUID(raw_id)
        return business_service.get_business(db, business_id), None
    except Exception:
        return None, "Demo business is not configured."


def _lead_detail_context(
    db: Session,
    *,
    user: User,
    lead,
    business,
    status_error: str | None = None,
    message_error: str | None = None,
) -> dict:
    return {
        "user": user,
        "lead": lead,
        "business": business,
        "recommended_action": lead_service.recommended_action_for_lead(lead),
        "statuses": sorted(LEAD_STATUSES),
        "status_error": status_error,
        "messages": message_service.list_messages_for_lead(db, lead.id),
        "message_error": message_error,
    }


@router.get("", response_class=HTMLResponse, response_model=None)
def admin_dashboard(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    auth = _require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    return templates.TemplateResponse(
        request,
        "admin/dashboard.html",
        {"user": auth},
    )


@router.get("/notification-logs", response_class=HTMLResponse, response_model=None)
def notification_logs_page(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    status: str = "",
    channel: str = "",
    event_type: str = "",
    business_id: str = "",
):
    auth = _require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    query = db.query(NotificationLog, Business, Lead).join(Business, Business.id == NotificationLog.business_id).join(
        Lead, Lead.id == NotificationLog.lead_id
    )
    status_v = status.strip().lower()
    channel_v = channel.strip().lower()
    event_v = event_type.strip().lower()
    business_v = business_id.strip()

    if status_v:
        query = query.filter(NotificationLog.status == status_v)
    if channel_v:
        query = query.filter(NotificationLog.channel == channel_v)
    if event_v:
        query = query.filter(NotificationLog.event_type == event_v)
    if business_v:
        try:
            query = query.filter(NotificationLog.business_id == uuid.UUID(business_v))
        except ValueError:
            query = query.filter(text("1=0"))

    rows = query.order_by(NotificationLog.created_at.desc()).limit(200).all()
    business_options = business_service.list_businesses(db)
    return templates.TemplateResponse(
        request,
        "admin/notification_logs.html",
        {
            "user": auth,
            "rows": rows,
            "filters": {
                "status": status_v,
                "channel": channel_v,
                "event_type": event_v,
                "business_id": business_v,
            },
            "businesses": business_options,
            "mask_recipient": _mask_recipient,
            "error_summary": _error_summary,
        },
    )


@router.get("/notification-logs/{log_id}", response_class=HTMLResponse, response_model=None)
def notification_log_detail_page(
    request: Request,
    log_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
):
    auth = _require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    row = (
        db.query(NotificationLog, Business, Lead)
        .join(Business, Business.id == NotificationLog.business_id)
        .join(Lead, Lead.id == NotificationLog.lead_id)
        .filter(NotificationLog.id == log_id)
        .one_or_none()
    )
    if row is None:
        return RedirectResponse(url="/admin/notification-logs", status_code=303)
    log, business, lead = row
    return templates.TemplateResponse(
        request,
        "admin/notification_log_detail.html",
        {
            "user": auth,
            "log": log,
            "business": business,
            "lead": lead,
            "masked_recipient": _mask_recipient(log.recipient),
        },
    )


@router.get("/system-check", response_class=HTMLResponse, response_model=None)
def system_check_page(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    auth = _require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth
    return templates.TemplateResponse(
        request,
        "admin/system_check.html",
        {
            "user": auth,
            "checks": _system_checks(db),
        },
    )


def _invite_history_for_template(db: Session, *, user_id: uuid.UUID) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for token in user_access_service.list_invite_history(db, user_id=user_id):
        status = user_access_service.invite_token_status(token)
        rows.append(
            {
                "purpose": token.purpose,
                "status": status,
                "delivery_status": token.delivery_status,
                "created_at": token.created_at,
                "expires_at": token.expires_at,
                "used_at": token.used_at,
            }
        )
    return rows


@router.get("/user-access", response_class=HTMLResponse, response_model=None)
def user_access_list_page(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    role: str = "",
    invite_status: str = "",
    q: str = "",
):
    auth = _require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    rows = user_access_service.list_user_access_rows(
        db,
        role=role,
        invite_status=invite_status,
        q=q,
    )
    return templates.TemplateResponse(
        request,
        "admin/user_access.html",
        {
            "user": auth,
            "rows": rows,
            "filters": {
                "role": role.strip(),
                "invite_status": invite_status.strip(),
                "q": q.strip(),
            },
        },
    )


@router.get("/user-access/{user_id}", response_class=HTMLResponse, response_model=None)
def user_access_detail_page(
    request: Request,
    user_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
):
    auth = _require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    target = get_user_by_id(db, user_id)
    if target is None:
        return RedirectResponse(url="/admin/user-access", status_code=303)

    try:
        row = user_access_service.get_user_access_row(db, user_id)
    except ValueError:
        return RedirectResponse(url="/admin/user-access", status_code=303)

    return templates.TemplateResponse(
        request,
        "admin/user_access_detail.html",
        {
            "user": auth,
            "target_user": {
                "id": target.id,
                "email": target.email,
                "full_name": target.full_name,
                "role": target.role,
                "is_active": target.is_active,
                "created_at": target.created_at,
                "updated_at": target.updated_at,
            },
            "row": row,
            "invite_history": _invite_history_for_template(db, user_id=user_id),
            "masked_email": _mask_recipient(target.email),
        },
    )


@router.get("/commissions", response_class=HTMLResponse, response_model=None)
def commissions_page(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    status: str = "",
):
    auth = _require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth
    status_v = status.strip().lower()
    rows = commission_service.list_commissions(db, status=status_v or None)
    return templates.TemplateResponse(
        request,
        "admin/commissions.html",
        {
            "user": auth,
            "rows": rows,
            "filters": {"status": status_v},
            "statuses": sorted(COMMISSION_STATUSES),
            "refund_review_note": commission_service.REFUND_REVIEW_NOTE,
        },
    )


@router.post("/commissions/{commission_id}/approve", response_model=None)
def approve_commission_submit(
    request: Request,
    commission_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
):
    auth = _require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth
    try:
        commission_service.update_commission_status(db, commission_id=commission_id, action="approve")
        db.commit()
    except ValueError:
        db.rollback()
    return RedirectResponse(url="/admin/commissions", status_code=303)


@router.post("/commissions/{commission_id}/mark-paid", response_model=None)
def mark_commission_paid_submit(
    request: Request,
    commission_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
):
    auth = _require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth
    try:
        commission_service.update_commission_status(db, commission_id=commission_id, action="mark_paid")
        db.commit()
    except ValueError:
        db.rollback()
    return RedirectResponse(url="/admin/commissions", status_code=303)


@router.post("/commissions/{commission_id}/cancel", response_model=None)
def cancel_commission_submit(
    request: Request,
    commission_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
):
    auth = _require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth
    try:
        commission_service.update_commission_status(db, commission_id=commission_id, action="cancel")
        db.commit()
    except ValueError:
        db.rollback()
    return RedirectResponse(url="/admin/commissions", status_code=303)


@router.post("/commissions/{commission_id}/mark-clawed-back", response_model=None)
def mark_commission_clawed_back_submit(
    request: Request,
    commission_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
):
    auth = _require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth
    try:
        commission_service.update_commission_status(
            db,
            commission_id=commission_id,
            action="mark_clawed_back",
        )
        db.commit()
    except ValueError:
        db.rollback()
    return RedirectResponse(url="/admin/commissions", status_code=303)


@router.post("/users/{user_id}/resend-invite", response_model=None)
def resend_user_invite_submit(
    request: Request,
    user_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
):
    auth = _require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    try:
        user_access_service.resend_invite_for_user(
            db,
            user_id=user_id,
            created_by_user_id=auth.id,
        )
        db.commit()
    except ValueError:
        db.rollback()

    return RedirectResponse(url=f"/admin/user-access/{user_id}", status_code=303)


@router.get("/demo", response_class=HTMLResponse, response_model=None)
def demo_control_panel(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    auth = _require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    settings = get_settings()
    demo_business, config_error = _demo_business_context(db)
    rows = (
        demo_service.list_recent_demo_leads(db, business_id=demo_business.id)
        if demo_business is not None
        else []
    )
    readiness = demo_service.build_demo_readiness_checklist(db, settings=settings)
    warning = None
    if demo_business and not (demo_business.notification_email or demo_business.notification_phone):
        warning = "Demo business has no staff notification destination configured."
    return templates.TemplateResponse(
        request,
        "admin/demo.html",
        {
            "user": auth,
            "demo_enabled": settings.demo_enabled,
            "demo_business": demo_business,
            "demo_number": settings.demo_twilio_number or "—",
            "demo_rows": rows,
            "demo_config_error": config_error,
            "warning": warning,
            "readiness_checklist": readiness,
            "clear_result": request.query_params.get("cleared") or "",
        },
    )


@router.post("/demo/clear", response_model=None)
def clear_demo_data(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    auth = _require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    demo_business, _config_error = _demo_business_context(db)
    if demo_business is None:
        return RedirectResponse(url="/admin/demo?cleared=Demo+not+configured", status_code=303)

    result = demo_service.clear_demo_business_data(db, business_id=demo_business.id)
    db.commit()
    message = (
        f"Cleared demo data: {result['leads']} leads, "
        f"{result['messages']} messages, {result['notifications']} notifications."
    )
    return RedirectResponse(url=f"/admin/demo?cleared={quote_plus(message)}", status_code=303)


@router.get("/leads", response_class=HTMLResponse, response_model=None)
def list_operational_leads_page(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    """Operational leads from call/SMS workflows (not business signup pipeline)."""
    auth = _require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    leads = (
        db.query(Lead, Business)
        .join(Business, Business.id == Lead.business_id)
        .order_by(Lead.created_at.desc())
        .all()
    )
    return templates.TemplateResponse(
        request,
        "admin/operational_leads.html",
        {
            "user": auth,
            "rows": leads,
            "recommended_action_for_lead": lead_service.recommended_action_for_lead,
        },
    )


@router.get("/businesses", response_class=HTMLResponse, response_model=None)
def list_businesses_page(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    auth = _require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    businesses = business_service.list_businesses(db)
    return templates.TemplateResponse(
        request,
        "admin/businesses.html",
        {"user": auth, "businesses": businesses},
    )


@router.get("/businesses/new", response_class=HTMLResponse, response_model=None)
def new_business_form(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    auth = _require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    return templates.TemplateResponse(
        request,
        "admin/business_new.html",
        {"user": auth, "error": None, "form": {}},
    )


@router.post("/businesses", response_model=None)
def create_business_submit(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    name: str = Form(""),
    industry: str = Form(""),
    website_url: str = Form(""),
    main_phone: str = Form(""),
    timezone: str = Form("America/New_York"),
):
    auth = _require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    form = {
        "name": name,
        "industry": industry,
        "website_url": website_url,
        "main_phone": main_phone,
        "timezone": timezone,
    }

    try:
        business = business_service.create_business(
            db,
            name=name,
            industry=industry or None,
            website_url=website_url or None,
            main_phone=main_phone or None,
            timezone=timezone,
        )
        db.commit()
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "admin/business_new.html",
            {"user": auth, "error": str(exc), "form": form},
            status_code=400,
        )

    return RedirectResponse(
        url=f"/admin/businesses/{business.id}",
        status_code=303,
    )


@router.get("/businesses/{business_id}", response_class=HTMLResponse, response_model=None)
def business_detail_page(
    request: Request,
    business_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
):
    auth = _require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    try:
        business = business_service.get_business(db, business_id)
    except ValueError:
        return RedirectResponse(url="/admin/businesses", status_code=303)

    links = (
        db.query(BusinessUser)
        .options(joinedload(BusinessUser.user))
        .filter(BusinessUser.business_id == business_id)
        .order_by(BusinessUser.created_at)
        .all()
    )

    phone_numbers = phone_number_service.list_phone_numbers_for_business(db, business_id)
    leads = lead_service.list_leads_for_business(db, business_id)
    compliance_profile = compliance_service.get_compliance_profile_for_business(db, business_id)

    primary_user_link = links[0] if links else None
    business_user_invite = None
    if primary_user_link is not None:
        business_user_invite = user_invite_service.latest_invite_status(
            db,
            user_id=primary_user_link.user_id,
            purpose=user_invite_service.BUSINESS_INVITE,
        )

    return templates.TemplateResponse(
        request,
        "admin/business_detail.html",
        {
            "user": auth,
            "business": business,
            "links": links,
            "link_error": None,
            "phone_numbers": phone_numbers,
            "leads": leads,
            "compliance_profile": compliance_profile,
            "business_user_invite": business_user_invite,
        },
    )


@router.get("/businesses/{business_id}/compliance", response_class=HTMLResponse, response_model=None)
def business_compliance_page(
    request: Request,
    business_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
):
    auth = _require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    try:
        business = business_service.get_business(db, business_id)
        profile = compliance_service.create_or_get_compliance_profile(db, business_id)
        db.commit()
    except ValueError:
        return RedirectResponse(url="/admin/businesses", status_code=303)

    return templates.TemplateResponse(
        request,
        "admin/business_compliance.html",
        {
            "user": auth,
            "business": business,
            "profile": profile,
            "statuses": sorted(COMPLIANCE_STATUSES),
            "error": None,
            "status_error": None,
        },
    )


@router.post("/businesses/{business_id}/compliance", response_model=None)
def business_compliance_save(
    request: Request,
    business_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    legal_business_name: str = Form(""),
    dba_name: str = Form(""),
    business_type: str = Form(""),
    ein: str = Form(""),
    website_url: str = Form(""),
    business_phone: str = Form(""),
    business_email: str = Form(""),
    address_line1: str = Form(""),
    address_line2: str = Form(""),
    city: str = Form(""),
    state: str = Form(""),
    postal_code: str = Form(""),
    country: str = Form("US"),
    authorized_rep_name: str = Form(""),
    authorized_rep_title: str = Form(""),
    authorized_rep_email: str = Form(""),
    sms_use_case: str = Form(""),
    opt_in_description: str = Form(""),
    sample_message_1: str = Form(""),
    sample_message_2: str = Form(""),
    privacy_policy_url: str = Form(""),
    terms_url: str = Form(""),
    twilio_brand_sid: str = Form(""),
    twilio_campaign_sid: str = Form(""),
):
    auth = _require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    try:
        business = business_service.get_business(db, business_id)
        compliance_service.update_compliance_profile(
            db,
            business_id,
            legal_business_name=legal_business_name,
            dba_name=dba_name,
            business_type=business_type,
            ein=ein,
            website_url=website_url,
            business_phone=business_phone,
            business_email=business_email,
            address_line1=address_line1,
            address_line2=address_line2,
            city=city,
            state=state,
            postal_code=postal_code,
            country=country,
            authorized_rep_name=authorized_rep_name,
            authorized_rep_title=authorized_rep_title,
            authorized_rep_email=authorized_rep_email,
            sms_use_case=sms_use_case,
            opt_in_description=opt_in_description,
            sample_message_1=sample_message_1,
            sample_message_2=sample_message_2,
            privacy_policy_url=privacy_policy_url,
            terms_url=terms_url,
            twilio_brand_sid=twilio_brand_sid,
            twilio_campaign_sid=twilio_campaign_sid,
        )
        db.commit()
    except ValueError as exc:
        try:
            business = business_service.get_business(db, business_id)
            profile = compliance_service.create_or_get_compliance_profile(db, business_id)
        except ValueError:
            return RedirectResponse(url="/admin/businesses", status_code=303)

        return templates.TemplateResponse(
            request,
            "admin/business_compliance.html",
            {
                "user": auth,
                "business": business,
                "profile": profile,
                "statuses": sorted(COMPLIANCE_STATUSES),
                "error": str(exc),
                "status_error": None,
            },
            status_code=400,
        )

    return RedirectResponse(url=f"/admin/businesses/{business_id}", status_code=303)


@router.post("/businesses/{business_id}/compliance/status", response_model=None)
def business_compliance_status_update(
    request: Request,
    business_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    status: str = Form(""),
    rejection_reason: str = Form(""),
):
    auth = _require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    try:
        business = business_service.get_business(db, business_id)
        compliance_service.update_compliance_status(
            db,
            business_id,
            status=status,
            rejection_reason=rejection_reason or None,
        )
        db.commit()
    except ValueError as exc:
        try:
            business = business_service.get_business(db, business_id)
            profile = compliance_service.create_or_get_compliance_profile(db, business_id)
        except ValueError:
            return RedirectResponse(url="/admin/businesses", status_code=303)

        return templates.TemplateResponse(
            request,
            "admin/business_compliance.html",
            {
                "user": auth,
                "business": business,
                "profile": profile,
                "statuses": sorted(COMPLIANCE_STATUSES),
                "error": None,
                "status_error": str(exc),
            },
            status_code=400,
        )

    return RedirectResponse(
        url=f"/admin/businesses/{business_id}/compliance",
        status_code=303,
    )


@router.post("/businesses/{business_id}/users", response_model=None)
def link_user_to_business_submit(
    request: Request,
    business_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    email: str = Form(""),
    role: str = Form("owner"),
):
    auth = _require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    try:
        business = business_service.get_business(db, business_id)
    except ValueError:
        return RedirectResponse(url="/admin/businesses", status_code=303)

    links = (
        db.query(BusinessUser)
        .options(joinedload(BusinessUser.user))
        .filter(BusinessUser.business_id == business_id)
        .order_by(BusinessUser.created_at)
        .all()
    )

    link_error: str | None = None
    user = get_user_by_email(db, email)
    if user is None:
        link_error = f"No user found with email {email.strip().lower()!r}"
    else:
        try:
            business_service.link_user_to_business(
                db,
                user_id=user.id,
                business_id=business_id,
                role=role,
            )
            db.commit()
            return RedirectResponse(
                url=f"/admin/businesses/{business_id}",
                status_code=303,
            )
        except ValueError as exc:
            link_error = str(exc)

    phone_numbers = phone_number_service.list_phone_numbers_for_business(db, business_id)
    leads = lead_service.list_leads_for_business(db, business_id)
    compliance_profile = compliance_service.get_compliance_profile_for_business(db, business_id)

    primary_user_link = links[0] if links else None
    business_user_invite = None
    if primary_user_link is not None:
        business_user_invite = user_invite_service.latest_invite_status(
            db,
            user_id=primary_user_link.user_id,
            purpose=user_invite_service.BUSINESS_INVITE,
        )

    return templates.TemplateResponse(
        request,
        "admin/business_detail.html",
        {
            "user": auth,
            "business": business,
            "links": links,
            "link_error": link_error,
            "phone_numbers": phone_numbers,
            "leads": leads,
            "compliance_profile": compliance_profile,
            "business_user_invite": business_user_invite,
        },
        status_code=400,
    )


@router.post("/businesses/{business_id}/resend-invite", response_model=None)
def resend_business_invite_submit(
    request: Request,
    business_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
):
    auth = _require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth
    try:
        business = business_service.get_business(db, business_id)
    except ValueError:
        return RedirectResponse(url="/admin/businesses", status_code=303)

    links = (
        db.query(BusinessUser)
        .options(joinedload(BusinessUser.user))
        .filter(BusinessUser.business_id == business_id)
        .order_by(BusinessUser.created_at)
        .all()
    )
    if not links or links[0].user is None:
        return RedirectResponse(url=f"/admin/businesses/{business_id}", status_code=303)
    user = links[0].user
    try:
        user_invite_service.create_or_invite_business_user_for_business(
            db,
            business=business,
            email=user.email,
            full_name=user.full_name,
            created_by_user_id=auth.id,
            resend=True,
        )
        db.commit()
    except ValueError:
        db.rollback()
    return RedirectResponse(url=f"/admin/businesses/{business_id}", status_code=303)


@router.get(
    "/businesses/{business_id}/phone-numbers/new",
    response_class=HTMLResponse,
    response_model=None,
)
def new_phone_number_form(
    request: Request,
    business_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
):
    auth = _require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    try:
        business = business_service.get_business(db, business_id)
    except ValueError:
        return RedirectResponse(url="/admin/businesses", status_code=303)

    return templates.TemplateResponse(
        request,
        "admin/phone_number_new.html",
        {"user": auth, "business": business, "error": None, "form": {}},
    )


@router.post("/businesses/{business_id}/phone-numbers", response_model=None)
def create_phone_number_submit(
    request: Request,
    business_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    phone_number: str = Form(""),
    label: str = Form(""),
    forward_to_number: str = Form(""),
    provider: str = Form("manual"),
    provider_sid: str = Form(""),
    status: str = Form("pending"),
):
    auth = _require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    try:
        business = business_service.get_business(db, business_id)
    except ValueError:
        return RedirectResponse(url="/admin/businesses", status_code=303)

    form = {
        "phone_number": phone_number,
        "label": label,
        "forward_to_number": forward_to_number,
        "provider": provider,
        "provider_sid": provider_sid,
        "status": status,
    }

    try:
        phone_number_service.create_phone_number(
            db,
            business_id=business_id,
            phone_number=phone_number,
            label=label or None,
            forward_to_number=forward_to_number or None,
            provider=provider,
            provider_sid=provider_sid or None,
            status=status,
        )
        db.commit()
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "admin/phone_number_new.html",
            {"user": auth, "business": business, "error": str(exc), "form": form},
            status_code=400,
        )

    return RedirectResponse(
        url=f"/admin/businesses/{business_id}",
        status_code=303,
    )


@router.post("/phone-numbers/{phone_number_id}/status", response_model=None)
def update_phone_number_status_submit(
    request: Request,
    phone_number_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    status: str = Form(""),
):
    auth = _require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    try:
        record = phone_number_service.get_phone_number(db, phone_number_id)
        phone_number_service.update_phone_number_status(db, phone_number_id, status=status)
        db.commit()
        business_id = record.business_id
    except ValueError:
        return RedirectResponse(url="/admin/businesses", status_code=303)

    return RedirectResponse(
        url=f"/admin/businesses/{business_id}",
        status_code=303,
    )


@router.get("/businesses/{business_id}/leads", response_class=HTMLResponse, response_model=None)
def list_leads_page(
    request: Request,
    business_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
):
    auth = _require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    try:
        business = business_service.get_business(db, business_id)
    except ValueError:
        return RedirectResponse(url="/admin/businesses", status_code=303)

    leads = lead_service.list_leads_for_business(db, business_id)
    return templates.TemplateResponse(
        request,
        "admin/leads.html",
        {"user": auth, "business": business, "leads": leads},
    )


@router.get("/businesses/{business_id}/leads/new", response_class=HTMLResponse, response_model=None)
def new_lead_form(
    request: Request,
    business_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
):
    auth = _require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    try:
        business = business_service.get_business(db, business_id)
    except ValueError:
        return RedirectResponse(url="/admin/businesses", status_code=303)

    return templates.TemplateResponse(
        request,
        "admin/lead_new.html",
        {"user": auth, "business": business, "error": None, "form": {}},
    )


@router.post("/businesses/{business_id}/leads", response_model=None)
def create_lead_submit(
    request: Request,
    business_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    name: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    service_needed: str = Form(""),
    location: str = Form(""),
    urgency: str = Form(""),
    summary: str = Form(""),
):
    auth = _require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    try:
        business = business_service.get_business(db, business_id)
    except ValueError:
        return RedirectResponse(url="/admin/businesses", status_code=303)

    form = {
        "name": name,
        "phone": phone,
        "email": email,
        "service_needed": service_needed,
        "location": location,
        "urgency": urgency,
        "summary": summary,
    }

    try:
        lead = lead_service.create_lead(
            db,
            business_id=business_id,
            name=name or None,
            phone=phone or None,
            email=email or None,
            service_needed=service_needed or None,
            location=location or None,
            urgency=urgency or None,
            summary=summary or None,
        )
        db.commit()
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "admin/lead_new.html",
            {"user": auth, "business": business, "error": str(exc), "form": form},
            status_code=400,
        )

    return RedirectResponse(url=f"/admin/leads/{lead.id}", status_code=303)


@router.get("/leads/{lead_id}", response_class=HTMLResponse, response_model=None)
def lead_detail_page(
    request: Request,
    lead_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
):
    auth = _require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    try:
        lead = lead_service.get_lead(db, lead_id)
        business = business_service.get_business(db, lead.business_id)
    except ValueError:
        return RedirectResponse(url="/admin/businesses", status_code=303)

    return templates.TemplateResponse(
        request,
        "admin/lead_detail.html",
        _lead_detail_context(db, user=auth, lead=lead, business=business),
    )


@router.get("/leads/{lead_id}/messages", response_model=None)
def lead_messages_redirect(
    request: Request,
    lead_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
):
    auth = _require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    try:
        lead_service.get_lead(db, lead_id)
    except ValueError:
        return RedirectResponse(url="/admin/businesses", status_code=303)

    return RedirectResponse(url=f"/admin/leads/{lead_id}", status_code=303)


@router.post("/leads/{lead_id}/messages", response_model=None)
def create_message_submit(
    request: Request,
    lead_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    body: str = Form(""),
    direction: str = Form("internal"),
    channel: str = Form("manual"),
):
    auth = _require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    try:
        lead = lead_service.get_lead(db, lead_id)
        business = business_service.get_business(db, lead.business_id)
        message_service.create_message(
            db,
            business_id=lead.business_id,
            lead_id=lead_id,
            body=body,
            direction=direction,
            channel=channel,
        )
        db.commit()
    except ValueError as exc:
        try:
            lead = lead_service.get_lead(db, lead_id)
            business = business_service.get_business(db, lead.business_id)
        except ValueError:
            return RedirectResponse(url="/admin/businesses", status_code=303)

        return templates.TemplateResponse(
            request,
            "admin/lead_detail.html",
            _lead_detail_context(
                db,
                user=auth,
                lead=lead,
                business=business,
                message_error=str(exc),
            ),
            status_code=400,
        )

    return RedirectResponse(url=f"/admin/leads/{lead_id}", status_code=303)


@router.post("/leads/{lead_id}/status", response_model=None)
def update_lead_status_submit(
    request: Request,
    lead_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    status: str = Form(""),
):
    auth = _require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    try:
        lead = lead_service.get_lead(db, lead_id)
        business = business_service.get_business(db, lead.business_id)
        lead_service.update_lead_status(db, lead_id, status)
        db.commit()
    except ValueError as exc:
        try:
            lead = lead_service.get_lead(db, lead_id)
            business = business_service.get_business(db, lead.business_id)
        except ValueError:
            return RedirectResponse(url="/admin/businesses", status_code=303)

        return templates.TemplateResponse(
            request,
            "admin/lead_detail.html",
            _lead_detail_context(
                db,
                user=auth,
                lead=lead,
                business=business,
                status_error=str(exc),
            ),
            status_code=400,
        )

    return RedirectResponse(url=f"/admin/leads/{lead_id}", status_code=303)


def _partner_application_detail_context(
    request: Request,
    db: Session,
    *,
    application,
    signed_docs,
    partner,
    application_id: uuid.UUID,
    error: str | None = None,
    reject_error: str | None = None,
) -> dict:
    settings = get_settings()
    referral_link = None
    linked_user = None
    login_active = False
    referred_leads: list = []
    partner_invite_status = None
    if partner is not None:
        linked_user = partner.user
        login_active = bool(linked_user and linked_user.is_active and partner.user_id)
        referral_link = f"{settings.app_base_url.rstrip('/')}/?ref={partner.referral_code}"
        referred_leads = business_lead_service.list_business_leads_for_partner(db, partner.id)
        if linked_user is not None:
            partner_invite_status = user_invite_service.latest_invite_status(
                db,
                user_id=linked_user.id,
                purpose=user_invite_service.PARTNER_INVITE,
            )

    return {
        "application": application,
        "signed_docs": signed_docs,
        "partner": partner,
        "linked_user": linked_user,
        "login_active": login_active,
        "referral_link": referral_link,
        "referred_leads": referred_leads,
        "partner_invite_status": partner_invite_status,
        "activation_notice": partner_service.pop_activation_notice(request, application_id),
        "error": error,
        "reject_error": reject_error,
    }


@router.get("/partners", response_class=HTMLResponse, response_model=None)
def list_partners_page(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    status: str | None = None,
):
    auth = _require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    applications = partner_service.list_applications(db, status=status or None)
    partners = partner_service.list_partners(db)
    return templates.TemplateResponse(
        request,
        "admin/partners.html",
        {
            "user": auth,
            "applications": applications,
            "partners": partners,
            "status_filter": status or "",
        },
    )


@router.get("/partners/{application_id}", response_class=HTMLResponse, response_model=None)
def partner_application_detail_page(
    request: Request,
    application_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
):
    auth = _require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    try:
        application = partner_service.get_application(db, application_id)
        signed_docs = partner_service.list_signed_documents_for_application(db, application_id)
        partner = partner_service.get_partner_by_application(db, application_id)
    except ValueError:
        return RedirectResponse(url="/admin/partners", status_code=303)

    ctx = _partner_application_detail_context(
        request,
        db,
        application=application,
        signed_docs=signed_docs,
        partner=partner,
        application_id=application_id,
    )
    return templates.TemplateResponse(
        request,
        "admin/partner_application_detail.html",
        {"user": auth, **ctx},
    )


@router.post("/partners/{application_id}/approve", response_model=None)
def approve_partner_application_submit(
    request: Request,
    application_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
):
    auth = _require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    try:
        result = partner_service.approve_application(
            db,
            application_id,
            reviewed_by_user_id=auth.id,
        )
        db.commit()
        partner_service.store_activation_notice(
            request,
            application_id=application_id,
            login_email=result.user.email,
            invite_status=result.invite_status,
            invite_error=result.invite_error,
            user_was_created=result.user_was_created,
        )
    except ValueError as exc:
        db.rollback()
        try:
            application = partner_service.get_application(db, application_id)
            signed_docs = partner_service.list_signed_documents_for_application(db, application_id)
            partner = partner_service.get_partner_by_application(db, application_id)
        except ValueError:
            return RedirectResponse(url="/admin/partners", status_code=303)

        ctx = _partner_application_detail_context(
            request,
            db,
            application=application,
            signed_docs=signed_docs,
            partner=partner,
            application_id=application_id,
            error=str(exc),
        )
        ctx["activation_notice"] = None
        return templates.TemplateResponse(
            request,
            "admin/partner_application_detail.html",
            {"user": auth, **ctx},
            status_code=400,
        )

    return RedirectResponse(url=f"/admin/partners/{application_id}", status_code=303)


@router.post("/partners/{application_id}/reject", response_model=None)
def reject_partner_application_submit(
    request: Request,
    application_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    rejection_reason: str = Form(""),
):
    auth = _require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    try:
        partner_service.reject_application(
            db,
            application_id,
            reviewed_by_user_id=auth.id,
            rejection_reason=rejection_reason,
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        try:
            application = partner_service.get_application(db, application_id)
            signed_docs = partner_service.list_signed_documents_for_application(db, application_id)
            partner = partner_service.get_partner_by_application(db, application_id)
        except ValueError:
            return RedirectResponse(url="/admin/partners", status_code=303)

        ctx = _partner_application_detail_context(
            request,
            db,
            application=application,
            signed_docs=signed_docs,
            partner=partner,
            application_id=application_id,
            reject_error=str(exc),
        )
        ctx["activation_notice"] = None
        return templates.TemplateResponse(
            request,
            "admin/partner_application_detail.html",
            {"user": auth, **ctx},
            status_code=400,
        )

    return RedirectResponse(url=f"/admin/partners/{application_id}", status_code=303)


@router.post("/partners/{application_id}/resend-invite", response_model=None)
def resend_partner_invite_submit(
    request: Request,
    application_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
):
    auth = _require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth
    try:
        application = partner_service.get_application(db, application_id)
        partner = partner_service.get_partner_by_application(db, application_id)
        if partner is None:
            raise ValueError("Partner not approved yet")
        partner_service.activate_partner_login(
            db,
            partner=partner,
            application=application,
            created_by_user_id=auth.id,
            resend_invite=True,
        )
        db.commit()
    except ValueError:
        db.rollback()
    return RedirectResponse(url=f"/admin/partners/{application_id}", status_code=303)


@router.get("/business-leads", response_class=HTMLResponse, response_model=None)
def list_business_leads_page(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    auth = _require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    leads = business_lead_service.list_business_leads(db)
    return templates.TemplateResponse(
        request,
        "admin/business_leads.html",
        {"user": auth, "leads": leads},
    )


@router.get("/business-leads/{lead_id}", response_class=HTMLResponse, response_model=None)
def business_lead_detail_page(
    request: Request,
    lead_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
):
    auth = _require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    try:
        lead = business_lead_service.get_business_lead(db, lead_id)
    except ValueError:
        return RedirectResponse(url="/admin/business-leads", status_code=303)

    from app.models.business_lead import BUSINESS_LEAD_STATUSES

    from app.models.business import Business

    converted_business = None
    if lead.converted_business_id is not None:
        converted_business = db.get(Business, lead.converted_business_id)

    return templates.TemplateResponse(
        request,
        "admin/business_lead_detail.html",
        {
            "user": auth,
            "lead": lead,
            "converted_business": converted_business,
            "statuses": sorted(BUSINESS_LEAD_STATUSES),
            "status_error": None,
            "checkout_error": None,
        },
    )


@router.post("/business-leads/{lead_id}/status", response_model=None)
def business_lead_status_update(
    request: Request,
    lead_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    status: str = Form(""),
):
    auth = _require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    try:
        lead = business_lead_service.update_business_lead_status(db, lead_id, status)
        db.commit()
    except ValueError as exc:
        db.rollback()
        try:
            lead = business_lead_service.get_business_lead(db, lead_id)
        except ValueError:
            return RedirectResponse(url="/admin/business-leads", status_code=303)

        from app.models.business_lead import BUSINESS_LEAD_STATUSES

        converted_business = None
        if lead.converted_business_id is not None:
            from app.models.business import Business

            converted_business = db.get(Business, lead.converted_business_id)

        return templates.TemplateResponse(
            request,
            "admin/business_lead_detail.html",
            {
                "user": auth,
                "lead": lead,
                "converted_business": converted_business,
                "statuses": sorted(BUSINESS_LEAD_STATUSES),
                "status_error": str(exc),
                "checkout_error": None,
            },
            status_code=400,
        )

    return RedirectResponse(url=f"/admin/business-leads/{lead.id}", status_code=303)


@router.post("/business-leads/{lead_id}/create-checkout", response_model=None)
def business_lead_create_checkout(
    request: Request,
    lead_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
):
    auth = _require_admin(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    from app.models.business import Business
    from app.models.business_lead import BUSINESS_LEAD_STATUSES

    try:
        result = business_lead_checkout_service.create_checkout_for_lead(db, lead_id)
        db.commit()
        return RedirectResponse(url=f"/admin/business-leads/{lead_id}", status_code=303)
    except ValueError as exc:
        db.rollback()
        try:
            lead = business_lead_service.get_business_lead(db, lead_id)
        except ValueError:
            return RedirectResponse(url="/admin/business-leads", status_code=303)

        converted_business = None
        if lead.converted_business_id is not None:
            converted_business = db.get(Business, lead.converted_business_id)

        return templates.TemplateResponse(
            request,
            "admin/business_lead_detail.html",
            {
                "user": auth,
                "lead": lead,
                "converted_business": converted_business,
                "statuses": sorted(BUSINESS_LEAD_STATUSES),
                "status_error": None,
                "checkout_error": str(exc),
            },
            status_code=400,
        )
