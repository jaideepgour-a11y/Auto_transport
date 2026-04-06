"""
Scheduler — runs every SCHEDULER_POLL_SECONDS to:
1. Trigger loads whose load_out_time + 6h has passed and driver_confirmed is None.
2. Send the main menu again for active loads whose next_followup_due has passed.
"""
import asyncio
import logging
from datetime import datetime

from sqlalchemy import select

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.load import Load
from app.services.flow_engine import trigger_load
from app.services.whatsapp import send_list
from app.services import messages as msg

logger = logging.getLogger(__name__)

_stop_event = asyncio.Event()


async def start_scheduler():
    logger.info(
        "Scheduler started — polling every %ds", settings.SCHEDULER_POLL_SECONDS
    )
    while not _stop_event.is_set():
        try:
            await _run_cycle()
        except Exception as exc:
            logger.exception("Scheduler cycle error: %s", exc)
        await asyncio.sleep(settings.SCHEDULER_POLL_SECONDS)


async def stop_scheduler():
    _stop_event.set()


async def _run_cycle():
    now = datetime.utcnow()
    async with AsyncSessionLocal() as db:

        # 1. Trigger new loads (load_out_time + 6h passed, not yet confirmed)
        result = await db.execute(
            select(Load).where(
                Load.is_active == True,
                Load.driver_confirmed == None,       # noqa: E711
                Load.load_out_time <= now,
            )
        )
        new_loads = result.scalars().all()
        for load in new_loads:
            logger.info("Triggering load %d (vehicle %s)", load.id, load.vehicle_no)
            await trigger_load(load, db)

        # 2. Follow-up: active loads with no pending step and followup due
        result = await db.execute(
            select(Load).where(
                Load.is_active == True,
                Load.driver_confirmed == True,
                Load.pending_step == None,           # noqa: E711
                Load.next_followup_due <= now,
            )
        )
        followup_loads = result.scalars().all()
        for load in followup_loads:
            logger.info(
                "Follow-up for load %d (vehicle %s, stage %d)",
                load.id, load.vehicle_no, load.current_stage,
            )
            await send_list(
                load.driver_whatsapp,
                msg.MAIN_MENU_BODY,
                button_label="Select Status",
                sections=msg.MAIN_MENU_SECTIONS,
                header=f"Load: {load.vehicle_no} | {load.from_location} → {load.to_location}",
            )
            # Reset next follow-up (will be rescheduled when driver responds)
            load.next_followup_due = None
            await db.commit()
