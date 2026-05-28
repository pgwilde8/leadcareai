"""Partner dashboard (session-protected)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.models.partner import Partner
from app.routers.auth import require_partner
from app.services import business_lead_service
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

    return templates.TemplateResponse(
        request,
        "partner/dashboard.html",
        {
            "partner": partner,
            "referral_link": referral_link,
            "referred_leads": referred_leads,
            "stats": {
                "businesses_referred": referred_count,
                "active_paying_customers": 0,
                "pending_commissions": 0,
                "approved_commissions": 0,
                "paid_commissions": 0,
            },
        },
    )
