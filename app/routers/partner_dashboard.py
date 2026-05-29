"""Partner dashboard (session-protected)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.models.partner import Partner
from app.models.business import Business
from app.routers.auth import get_current_user, require_partner
from app.services.partner_service import PARTNER_STATUS_ACTIVE
from app.services import business_lead_service, commission_payout_service, commission_service
from app.services.partner_training_service import list_partner_training_videos
from app.services.demo_live_service import DEMO_PHONE_DISPLAY
from app.templates import templates

router = APIRouter(prefix="/partner", tags=["partner"])


@router.get("/dashboard", response_class=HTMLResponse, response_model=None)
def partner_dashboard(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    auth = require_partner(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    partner: Partner = auth
    settings = get_settings()
    referral_link = f"{settings.app_base_url.rstrip('/')}/?ref={partner.referral_code}"
    referred_leads = business_lead_service.list_business_leads_for_partner(db, partner.id)
    referred_count = len(referred_leads)
    commissions = commission_service.list_commissions_for_partner(db, partner_id=partner.id)
    commission_stats = commission_service.commission_totals_by_status(db, partner_id=partner.id)
    business_names: dict[str, str] = {}
    if commissions:
        business_ids = {item.business_id for item in commissions}
        businesses = db.query(Business).filter(Business.id.in_(business_ids)).all()
        business_names = {str(item.id): item.name for item in businesses}

    return templates.TemplateResponse(
        request,
        "partner/dashboard.html",
        {
            "partner": partner,
            "referral_link": referral_link,
            "referred_leads": referred_leads,
            "commissions": commissions,
            "commission_business_names": business_names,
            "stats": {
                "businesses_referred": referred_count,
                "active_paying_customers": len([lead for lead in referred_leads if lead.payment_status == "paid"]),
                "pending_commissions": commission_stats["pending"],
                "approved_commissions": commission_stats["approved"],
                "paid_commissions": commission_stats["paid"],
            },
            "demo_phone_display": DEMO_PHONE_DISPLAY,
        },
    )


@router.get("/payouts", response_class=HTMLResponse, response_model=None)
def partner_payouts(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    auth = require_partner(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    partner: Partner = auth
    payout_rows = commission_payout_service.list_payouts_for_partner(db, partner_id=partner.id)
    return templates.TemplateResponse(
        request,
        "partner/payouts.html",
        {
            "partner": partner,
            "payout_rows": payout_rows,
        },
    )


@router.get("/payplan", response_class=HTMLResponse, response_model=None)
def partner_payplan(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> HTMLResponse:
    settings = get_settings()
    base = settings.app_base_url.rstrip("/")
    partner = None
    referral_link = None
    user = get_current_user(request, db)
    if user is not None and user.is_active and user.role == "partner":
        partner = db.query(Partner).filter(Partner.user_id == user.id).one_or_none()
        if partner is not None and partner.status == PARTNER_STATUS_ACTIVE:
            referral_link = f"{base}/?ref={partner.referral_code}"

    return templates.TemplateResponse(
        request,
        "partner/payplan.html",
        {
            "partner": partner,
            "referral_link": referral_link,
            "referral_example": f"{base}/?ref=YOURCODE",
        },
    )


def _public_base_url() -> str:
    settings = get_settings()
    return settings.effective_public_base_url or settings.app_base_url.rstrip("/")


@router.get("/marketing", response_class=HTMLResponse, response_model=None)
def partner_marketing(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    auth = require_partner(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    partner: Partner = auth
    base = _public_base_url()
    code = partner.referral_code
    demo_link = f"{base}/demo?ref={code}"
    referral_landing_link = f"{base}/r/{code}"
    demo_book_link = f"{base}/demo/book?ref={code}"

    return templates.TemplateResponse(
        request,
        "partner/marketing.html",
        {
            "partner": partner,
            "referral_code": code,
            "demo_link": demo_link,
            "referral_landing_link": referral_landing_link,
            "demo_book_link": demo_book_link,
        },
    )


@router.get("/resources", response_class=HTMLResponse, response_model=None)
def partner_resources(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
):
    auth = require_partner(request, db)
    if isinstance(auth, RedirectResponse):
        return auth

    partner: Partner = auth
    base = _public_base_url()
    code = partner.referral_code

    return templates.TemplateResponse(
        request,
        "partner/resources.html",
        {
            "partner": partner,
            "referral_code": code,
            "demo_link": f"{base}/demo?ref={code}",
            "referral_landing_link": f"{base}/r/{code}",
            "demo_book_link": f"{base}/demo/book?ref={code}",
            "demo_phone_display": DEMO_PHONE_DISPLAY,
            "training_videos": list_partner_training_videos(),
        },
    )
