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
from app.routers.auth import require_partner
from app.services import business_lead_service, commission_service
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
        },
    )
