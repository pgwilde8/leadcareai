"""Stripe webhooks."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services import business_lead_checkout_service, stripe_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def _run_webhook_handler(handler: Callable[..., Any], db: Session, *, stripe_event_id: str, payload: dict) -> JSONResponse:
    try:
        handler(db, stripe_event_id=stripe_event_id, **payload)
        db.commit()
    except ValueError as exc:
        db.rollback()
        logger.warning("Stripe handler skipped: %s", exc)
        return JSONResponse({"received": True, "skipped": str(exc)})
    except Exception:
        db.rollback()
        logger.exception("Stripe handler failed for event %s", stripe_event_id)
        return JSONResponse({"error": "processing failed"}, status_code=500)
    return JSONResponse({"received": True})


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    stripe_signature: str | None = Header(None, alias="Stripe-Signature"),
):
    payload = await request.body()
    try:
        event = stripe_service.construct_webhook_event(payload, stripe_signature)
    except Exception as exc:
        logger.warning("Stripe webhook verification failed: %s", exc)
        return JSONResponse({"error": "invalid payload"}, status_code=400)

    event_id = event.get("id")
    event_type = event.get("type")
    if not event_id or not event_type:
        return JSONResponse({"error": "missing event id or type"}, status_code=400)

    obj = event.get("data", {}).get("object", {})

    handlers: dict[str, tuple[Callable[..., Any], dict[str, Any]]] = {
        "checkout.session.completed": (
            business_lead_checkout_service.handle_checkout_session_completed,
            {"session_payload": obj},
        ),
        "checkout.session.expired": (
            business_lead_checkout_service.handle_checkout_session_expired,
            {"session_payload": obj},
        ),
        "invoice.paid": (
            business_lead_checkout_service.handle_invoice_paid,
            {"invoice_payload": obj},
        ),
        "invoice.payment_failed": (
            business_lead_checkout_service.handle_invoice_payment_failed,
            {"invoice_payload": obj},
        ),
        "customer.subscription.deleted": (
            business_lead_checkout_service.handle_subscription_deleted,
            {"subscription_payload": obj},
        ),
        "customer.subscription.updated": (
            business_lead_checkout_service.handle_subscription_updated,
            {"subscription_payload": obj},
        ),
        "charge.refunded": (
            business_lead_checkout_service.handle_charge_refunded,
            {"charge_payload": obj},
        ),
        "charge.dispute.created": (
            business_lead_checkout_service.handle_charge_dispute_created,
            {"dispute_payload": obj},
        ),
    }

    entry = handlers.get(event_type)
    if entry is None:
        logger.info("Ignoring Stripe event type: %s", event_type)
        return JSONResponse({"received": True})

    handler, kwargs = entry
    return _run_webhook_handler(handler, db, stripe_event_id=event_id, payload=kwargs)
