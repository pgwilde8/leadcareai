"""Twilio webhooks (inbound SMS/voice + outbound auto-response via REST API)."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.twilio_webhook import validate_twilio_signature
from app.services import message_service, notification_service, sms_service
from app.services.twilio_inbound_sms_service import TWILIO_PROVIDER, process_inbound_sms
from app.services.twilio_inbound_voice_service import (
    process_inbound_voice,
    update_voice_call_status,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/twilio", tags=["twilio"])

TWIML_EMPTY = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
TWIML_VOICE = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say>Thanks for calling. We will text you now.</Say>
  <Hangup/>
</Response>"""
TWIML_MEDIA_TYPE = "application/xml"


def _twiml_response(content: str = TWIML_EMPTY) -> Response:
    return Response(content=content, media_type=TWIML_MEDIA_TYPE)


async def _parse_twilio_form(request: Request, settings: Settings) -> dict[str, str]:
    form = await request.form()
    params = {key: str(value) for key, value in form.multi_items()}

    if settings.twilio_webhook_auth_enabled:
        if not settings.twilio_auth_token:
            raise HTTPException(status_code=403, detail="Twilio webhook auth not configured")
        signature = request.headers.get("X-Twilio-Signature", "")
        if not validate_twilio_signature(
            str(request.url),
            params,
            signature,
            settings.twilio_auth_token,
        ):
            raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    return params


@router.post("/sms")
async def inbound_sms_webhook(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    settings = get_settings()
    params = await _parse_twilio_form(request, settings)

    from_phone = (params.get("From") or "").strip()
    to_phone = (params.get("To") or "").strip()
    body = (params.get("Body") or "").strip()
    provider_sid = (params.get("MessageSid") or params.get("SmsSid") or "").strip() or None

    if not from_phone or not to_phone or not body:
        return _twiml_response()

    processed = process_inbound_sms(
        db,
        from_phone=from_phone,
        to_phone=to_phone,
        body=body,
        provider_sid=provider_sid,
    )
    if processed is not None:
        try:
            sms_service.send_inbound_auto_response(db, processed)
        except Exception:
            logger.exception(
                "Unexpected error sending inbound auto-response",
                extra={"lead_id": str(processed.lead_id)},
            )
        try:
            from app.services.business_service import get_business
            from app.services.lead_service import get_lead

            business = get_business(db, processed.business_id)
            lead = get_lead(db, processed.lead_id)
            notification_service.notify_inbound_sms_reply(
                db,
                business,
                lead,
                processed.body,
            )
        except Exception:
            logger.exception(
                "Unexpected error sending inbound SMS staff notification",
                extra={"lead_id": str(processed.lead_id)},
            )
    db.commit()
    return _twiml_response()


@router.post("/voice")
async def inbound_voice_webhook(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    settings = get_settings()
    try:
        params = await _parse_twilio_form(request, settings)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Voice webhook failed parsing request")
        return _twiml_response(TWIML_VOICE)

    from_phone = (params.get("From") or params.get("Caller") or "").strip()
    to_phone = (params.get("To") or params.get("Called") or "").strip()
    call_sid = (params.get("CallSid") or "").strip()
    call_status = (params.get("CallStatus") or "ringing").strip()
    direction = (params.get("Direction") or "").strip() or None

    if not from_phone or not to_phone or not call_sid:
        db.commit()
        return _twiml_response(TWIML_VOICE)

    try:
        processed = process_inbound_voice(
            db,
            from_phone=from_phone,
            to_phone=to_phone,
            call_sid=call_sid,
            call_status=call_status,
            direction=direction,
        )
        if processed is not None:
            try:
                sms_service.send_missed_call_textback(db, processed)
            except Exception:
                logger.exception(
                    "Unexpected error sending missed-call text-back",
                    extra={"lead_id": str(processed.lead_id), "call_sid": call_sid},
                )
            try:
                from app.services.business_service import get_business
                from app.services.lead_service import get_lead

                business = get_business(db, processed.business_id)
                lead = get_lead(db, processed.lead_id)
                voice_msg = message_service.get_message_by_provider_sid(
                    db, TWILIO_PROVIDER, processed.call_sid
                )
                notification_service.notify_new_missed_call_lead(
                    db,
                    business,
                    lead,
                    voice_msg.body if voice_msg else f"Inbound call from {processed.from_phone}",
                )
            except Exception:
                logger.exception(
                    "Unexpected error sending missed-call staff notification",
                    extra={"lead_id": str(processed.lead_id), "call_sid": call_sid},
                )
    except Exception:
        logger.exception("Voice webhook processing failed", extra={"call_sid": call_sid})

    db.commit()
    return _twiml_response(TWIML_VOICE)


@router.post("/voice/status")
async def voice_status_webhook(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    settings = get_settings()
    try:
        params = await _parse_twilio_form(request, settings)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Voice status webhook failed parsing request")
        return Response(status_code=200)

    call_sid = (params.get("CallSid") or "").strip()
    call_status = (params.get("CallStatus") or "").strip()

    if call_sid and call_status:
        try:
            update_voice_call_status(
                db,
                call_sid=call_sid,
                call_status=call_status,
                from_phone=(params.get("From") or "").strip() or None,
                to_phone=(params.get("To") or "").strip() or None,
                call_duration=(params.get("CallDuration") or "").strip() or None,
            )
        except Exception:
            logger.exception(
                "Voice status webhook update failed",
                extra={"call_sid": call_sid},
            )

    db.commit()
    return Response(status_code=200)
