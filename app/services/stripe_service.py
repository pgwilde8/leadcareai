"""Stripe Checkout and webhook helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.core.config import get_settings


@dataclass
class CheckoutSessionResult:
    session_id: str
    url: str
    customer_id: str | None = None


def _stripe_client():
    settings = get_settings()
    if not settings.stripe_secret_key:
        raise ValueError("STRIPE_SECRET_KEY is not configured")
    import stripe

    stripe.api_key = settings.stripe_secret_key
    return stripe


def _build_line_items() -> list[dict[str, Any]]:
    settings = get_settings()
    if not settings.stripe_price_id_growth_monthly:
        raise ValueError("STRIPE_PRICE_ID_GROWTH_MONTHLY is not configured")

    line_items: list[dict[str, Any]] = [
        {"price": settings.stripe_price_id_growth_monthly, "quantity": 1},
    ]

    if settings.stripe_price_id_setup_fee:
        line_items.append({"price": settings.stripe_price_id_setup_fee, "quantity": 1})
    elif settings.stripe_setup_amount_cents > 0:
        line_items.append(
            {
                "price_data": {
                    "currency": "usd",
                    "unit_amount": settings.stripe_setup_amount_cents,
                    "product_data": {"name": "LeadCare AI one-time setup fee"},
                },
                "quantity": 1,
            }
        )
    return line_items


def create_growth_checkout_session(
    *,
    customer_email: str,
    metadata: dict[str, str],
    success_url: str,
    cancel_url: str,
) -> CheckoutSessionResult:
    """Create Stripe Checkout (subscription + optional one-time setup fee)."""
    stripe = _stripe_client()
    session = stripe.checkout.Session.create(
        mode="subscription",
        customer_email=customer_email.strip().lower(),
        line_items=_build_line_items(),
        metadata=metadata,
        subscription_data={"metadata": metadata},
        success_url=success_url,
        cancel_url=cancel_url,
    )
    customer_id = session.customer
    if isinstance(customer_id, str):
        pass
    elif customer_id is not None and hasattr(customer_id, "id"):
        customer_id = customer_id.id
    else:
        customer_id = None

    return CheckoutSessionResult(
        session_id=session.id,
        url=session.url or "",
        customer_id=customer_id,
    )


def retrieve_checkout_session(session_id: str) -> dict[str, Any]:
    stripe = _stripe_client()
    session = stripe.checkout.Session.retrieve(session_id)
    return dict(session)


def construct_webhook_event(payload: bytes, signature_header: str | None) -> dict[str, Any]:
    settings = get_settings()
    stripe = _stripe_client()
    if settings.stripe_webhook_secret and signature_header:
        event = stripe.Webhook.construct_event(
            payload,
            signature_header,
            settings.stripe_webhook_secret,
        )
        return dict(event)
    return json.loads(payload.decode("utf-8"))
