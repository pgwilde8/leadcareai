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
from app.services.user_invite_service import consume_invite_and_set_password, get_valid_token_by_raw
from app.templates import templates

router = APIRouter(tags=["auth"])

SESSION_USER_ID_KEY = "user_id"
SESSION_USER_ROLE_KEY = "user_role"

_LOGIN_VIEW_TEMPLATES: dict[str, str] = {
    "business": "auth/login_business.html",
    "admin": "auth/login_admin.html",
}


def _login_form_context(
    login_view: str,
    *,
    error: str | None = None,
    prefill_email: str = "",
) -> dict:
    return {
        "login_view": login_view,
        "login_action": "/login",
        "error": error,
        "prefill_email": prefill_email,
    }


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
    return templates.TemplateResponse(request, "auth/login_index.html", {})


@router.get("/login/business", response_class=HTMLResponse)
def login_business_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "auth/login_business.html",
        _login_form_context("business"),
    )


@router.get("/login/admin", response_class=HTMLResponse)
def login_admin_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "auth/login_admin.html",
        _login_form_context("admin"),
    )


@router.post("/login", response_model=None)
def login_submit(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    email: str = Form(""),
    password: str = Form(""),
    login_view: str = Form("business"),
):
    view = login_view if login_view in _LOGIN_VIEW_TEMPLATES else "business"
    template_name = _LOGIN_VIEW_TEMPLATES[view]
    user = get_user_by_email(db, email)

    if (
        user is None
        or not user.is_active
        or not verify_password(password, user.hashed_password)
    ):
        return templates.TemplateResponse(
            request,
            template_name,
            _login_form_context(view, error="Invalid email or password", prefill_email=email.strip()),
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


@router.get("/auth/accept-invite", response_class=HTMLResponse)
def accept_invite_page(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    token: str = "",
) -> HTMLResponse:
    trimmed = token.strip()
    valid = bool(trimmed and get_valid_token_by_raw(db, raw_token=trimmed))
    return templates.TemplateResponse(
        request,
        "auth/accept_invite.html",
        {
            "token": trimmed,
            "valid": valid,
            "error": None if valid else "Invite link is invalid or expired",
            "success": False,
        },
    )


@router.post("/auth/accept-invite")
def accept_invite_submit(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    token: str = Form(""),
    password: str = Form(""),
    password_confirm: str = Form(""),
):
    trimmed = token.strip()
    if not trimmed:
        return templates.TemplateResponse(
            request,
            "auth/accept_invite.html",
            {"token": "", "valid": False, "error": "Missing invite token", "success": False},
            status_code=400,
        )
    if password != password_confirm:
        return templates.TemplateResponse(
            request,
            "auth/accept_invite.html",
            {"token": trimmed, "valid": True, "error": "Passwords do not match", "success": False},
            status_code=400,
        )
    try:
        user = consume_invite_and_set_password(db, raw_token=trimmed, new_password=password)
        if user is None:
            db.rollback()
            return templates.TemplateResponse(
                request,
                "auth/accept_invite.html",
                {"token": trimmed, "valid": False, "error": "Invite link is invalid or expired", "success": False},
                status_code=400,
            )
        db.commit()
    except ValueError as exc:
        db.rollback()
        return templates.TemplateResponse(
            request,
            "auth/accept_invite.html",
            {"token": trimmed, "valid": True, "error": str(exc), "success": False},
            status_code=400,
        )

    return RedirectResponse(url="/login", status_code=303)
