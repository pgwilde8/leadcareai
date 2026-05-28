"""Public contact form persistence and notifications."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.contact_message import ContactMessage
from app.services.email_service import send_email

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_MAX_MESSAGE_LEN = 10_000
CONTACT_SUBJECTS = frozenset(
    {
        "General inquiry",
        "Product demo",
        "Billing",
        "Partnership",
        "Technical support",
        "Other",
    }
)


def _strip(value: str | None, *, max_len: int) -> str:
    return (value or "").strip()[:max_len]


def submit_contact_message(
    db: Session,
    *,
    name: str,
    email: str,
    phone: str | None,
    subject: str,
    message: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> ContactMessage:
    clean_name = _strip(name, max_len=255)
    clean_email = _strip(email, max_len=255).lower()
    clean_phone = _strip(phone, max_len=50) or None
    clean_subject = _strip(subject, max_len=255) or "General inquiry"
    clean_message = _strip(message, max_len=_MAX_MESSAGE_LEN)

    if len(clean_name) < 2:
        raise ValueError("Please enter your name.")
    if not _EMAIL_RE.match(clean_email):
        raise ValueError("Please enter a valid email address.")
    if clean_subject not in CONTACT_SUBJECTS:
        raise ValueError("Please choose a valid topic.")
    if len(clean_message) < 10:
        raise ValueError("Please enter a message (at least 10 characters).")

    record = ContactMessage(
        name=clean_name,
        email=clean_email,
        phone=clean_phone,
        subject=clean_subject,
        message=clean_message,
        ip_address=_strip(ip_address, max_len=64) or None,
        user_agent=_strip(user_agent, max_len=500) or None,
    )
    db.add(record)
    db.flush()

    settings = get_settings()
    email_result = send_email(
        to_email=settings.default_support_email,
        subject=f"[{settings.app_name}] Contact: {clean_subject}",
        body=_format_support_email(record, settings.app_name),
    )
    record.email_status = email_result.status
    record.email_error = email_result.error
    db.commit()
    db.refresh(record)
    return record


def _format_support_email(record: ContactMessage, app_name: str) -> str:
    lines = [
        f"New contact form submission on {app_name}",
        "",
        f"Message ID: {record.id}",
        f"Name: {record.name}",
        f"Email: {record.email}",
        f"Phone: {record.phone or '—'}",
        f"Topic: {record.subject}",
        "",
        "Message:",
        record.message,
        "",
    ]
    if record.ip_address:
        lines.append(f"IP: {record.ip_address}")
    return "\n".join(lines)


def contact_form_defaults() -> dict[str, Any]:
    return {
        "name": "",
        "email": "",
        "phone": "",
        "subject": "General inquiry",
        "message": "",
    }
