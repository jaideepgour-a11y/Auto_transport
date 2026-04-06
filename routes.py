"""
Webhook routes:
  GET  /webhook  — Meta hub verification challenge
  POST /webhook  — Inbound WhatsApp messages
  POST /loads    — Create a new load (called by your dispatch system)
"""
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.load import Load
from app.models.message_log import MessageLog
from app.services.flow_engine import handle_message

logger = logging.getLogger(__name__)

webhook_router = APIRouter()


# ── Meta webhook verification ─────────────────────────────────────────────────

@webhook_router.get("")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        logger.info("Webhook verified by Meta.")
        return int(hub_challenge)
    raise HTTPException(status_code=403, detail="Verification failed")


# ── Inbound message handler ───────────────────────────────────────────────────

@webhook_router.post("")
async def receive_message(request: Request, db: AsyncSession = Depends(get_db)):
    body = await request.json()
    logger.debug("Inbound payload: %s", body)

    try:
        entry = body["entry"][0]
        change = entry["changes"][0]["value"]

        # Ignore status updates (delivered/read receipts)
        if "statuses" in change and "messages" not in change:
            return {"status": "ok"}

        message = change["messages"][0]
        from_number = message["from"]
        wa_msg_id = message.get("id", "")
        msg_type = message.get("type", "text")

        # Extract text payload
        if msg_type == "text":
            incoming_text = message["text"]["body"]
        elif msg_type == "interactive":
            interactive = message["interactive"]
            itype = interactive.get("type")
            if itype == "button_reply":
                incoming_text = interactive["button_reply"]["id"]
            elif itype == "list_reply":
                incoming_text = interactive["list_reply"]["id"]
            else:
                incoming_text = ""
        else:
            # Unsupported type (image, audio, etc.) — ignore
            return {"status": "ok"}

        # Find the active load for this driver number
        result = await db.execute(
            select(Load).where(
                Load.driver_whatsapp == from_number,
                Load.is_active == True,              # noqa: E712
            ).order_by(Load.id.desc())
        )
        load = result.scalars().first()

        if not load:
            logger.warning("No active load for number %s", from_number)
            return {"status": "ok"}

        # Log inbound
        db.add(MessageLog(
            load_id=load.id,
            wa_message_id=wa_msg_id,
            direction="inbound",
            from_number=from_number,
            message_type=msg_type,
            content=incoming_text,
            stage_at_time=load.current_stage,
        ))
        await db.commit()

        # Drive the flow
        await handle_message(load, incoming_text, db)

    except (KeyError, IndexError) as exc:
        logger.warning("Webhook parse error: %s | body=%s", exc, body)

    return {"status": "ok"}


# ── Load creation API ─────────────────────────────────────────────────────────

class CreateLoadRequest(BaseModel):
    vehicle_no: str
    from_location: str
    to_location: str
    bilty_no: str
    bilty_date: str
    driver_whatsapp: str          # E.164: +919XXXXXXXXX
    load_out_time: datetime       # ISO-8601; trigger = this + 6h


@webhook_router.post("/loads", tags=["Load Management"])
async def create_load(payload: CreateLoadRequest, db: AsyncSession = Depends(get_db)):
    """
    Register a new load. The scheduler will fire the driver confirmation
    message at load_out_time + 6 hours automatically.
    """
    # Normalise phone: ensure + prefix
    phone = payload.driver_whatsapp
    if not phone.startswith("+"):
        phone = "+" + phone

    load = Load(
        vehicle_no=payload.vehicle_no,
        from_location=payload.from_location,
        to_location=payload.to_location,
        bilty_no=payload.bilty_no,
        bilty_date=payload.bilty_date,
        driver_whatsapp=phone,
        load_out_time=payload.load_out_time,
        next_followup_due=payload.load_out_time + timedelta(
            seconds=settings.FOLLOWUP_INTERVAL_SECONDS
        ),
    )
    db.add(load)
    await db.commit()
    await db.refresh(load)
    logger.info("Load created: id=%d vehicle=%s", load.id, load.vehicle_no)
    return {"load_id": load.id, "status": "created"}


@webhook_router.post("/loads/{load_id}/close", tags=["Load Management"])
async def close_load(load_id: int, db: AsyncSession = Depends(get_db)):
    """Manually close a load (backend team action)."""
    result = await db.execute(select(Load).where(Load.id == load_id))
    load = result.scalars().first()
    if not load:
        raise HTTPException(status_code=404, detail="Load not found")
    load.is_active = False
    await db.commit()
    return {"load_id": load_id, "status": "closed"}
