"""Stripe webhooks."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services import business_lead_checkout_service, stripe_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


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

    if event_type == "checkout.session.completed":
        session_payload = event.get("data", {}).get("object", {})
        try:
            business_lead_checkout_service.handle_checkout_session_completed(
                db,
                stripe_event_id=event_id,
                session_payload=session_payload,
            )
            db.commit()
        except ValueError as exc:
            db.rollback()
            logger.warning("Stripe checkout handler skipped: %s", exc)
            return JSONResponse({"received": True, "skipped": str(exc)})
        except Exception:
            db.rollback()
            logger.exception("Stripe checkout handler failed")
            return JSONResponse({"error": "processing failed"}, status_code=500)
    else:
        logger.info("Ignoring Stripe event type: %s", event_type)

    return JSONResponse({"received": True})
