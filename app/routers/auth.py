"""Session-based login and logout (HTML forms)."""

from __future__ import annotations

import uuid
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import verify_password
from app.models.business import Business
from app.models.user import User
from app.services.business_service import get_primary_business_for_user
from app.services.user_service import get_user_by_email
from app.templates import templates

router = APIRouter(tags=["auth"])

SESSION_USER_ID_KEY = "user_id"
SESSION_USER_ROLE_KEY = "user_role"


def get_current_user(request: Request, db: Session) -> User | None:
    raw_user_id = request.session.get(SESSION_USER_ID_KEY)
    if not raw_user_id:
        return None
    try:
        user_id = UUID(str(raw_user_id))
    except (TypeError, ValueError):
        return None
    return db.get(User, user_id)


def require_admin(request: Request, db: Session) -> User | RedirectResponse:
    user = get_current_user(request, db)
    if user is None or not user.is_active or user.role != "admin":
        return RedirectResponse(url="/login", status_code=303)
    return user


def require_business_user(
    request: Request,
    db: Session,
) -> tuple[User, Business] | RedirectResponse:
    """Active business user with a linked business, or redirect to login."""
    user = get_current_user(request, db)
    if user is None or not user.is_active or user.role != "business_user":
        return RedirectResponse(url="/login", status_code=303)

    business = get_primary_business_for_user(db, user.id)
    if business is None:
        return RedirectResponse(url="/login", status_code=303)
    return user, business


def require_partner(request: Request, db: Session):
    """Active partner session, or redirect to login."""
    from app.models.partner import Partner
    from app.services.partner_service import PARTNER_STATUS_ACTIVE

    user = get_current_user(request, db)
    if user is None or not user.is_active or user.role != "partner":
        return RedirectResponse(url="/login", status_code=303)

    partner = db.query(Partner).filter(Partner.user_id == user.id).one_or_none()
    if partner is None or partner.status != PARTNER_STATUS_ACTIVE:
        return RedirectResponse(url="/login", status_code=303)
    return partner


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "auth/login.html",
        {"error": None, "prefill_email": ""},
    )


@router.post("/login", response_model=None)
def login_submit(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    email: str = Form(""),
    password: str = Form(""),
):
    user = get_user_by_email(db, email)

    if (
        user is None
        or not user.is_active
        or not verify_password(password, user.hashed_password)
    ):
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            {
                "error": "Invalid email or password",
                "prefill_email": email.strip(),
            },
            status_code=401,
        )

    request.session[SESSION_USER_ID_KEY] = str(user.id)
    request.session[SESSION_USER_ROLE_KEY] = user.role

    if user.role == "admin":
        return RedirectResponse(url="/admin", status_code=303)
    if user.role == "partner":
        return RedirectResponse(url="/partner/dashboard", status_code=303)
    if user.role == "business_user":
        return RedirectResponse(url="/business/dashboard", status_code=303)
    return RedirectResponse(url="/", status_code=303)


@router.post("/logout")
def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)
