"""
Flow Engine — handles every inbound message and drives the state machine.

Design principles (from spec):
1. Anti-redundancy: if a later stage is selected, fetch stored data,
   ask only MISSING critical fields, confirm existing ones only when needed.
2. Repeat loop: every 6 hours show main menu again; never re-ask captured data.
3. Pending step: the `load.pending_step` column stores exactly what we are
   waiting for, so we know how to interpret the next free-text reply.
"""
import logging
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.load import Load
from app.services import messages as msg
from app.services.whatsapp import (
    ask_datetime,
    send_buttons,
    send_list,
    send_text,
)

logger = logging.getLogger(__name__)

YES_IDS = {"yes", "btn_yes", "yes_btn"}
NO_IDS = {"no", "btn_no", "no_btn"}


# ── Entry point ───────────────────────────────────────────────────────────────

async def handle_message(load: Load, incoming: str, db: AsyncSession) -> None:
    """
    Route an inbound message to the correct handler based on load state.
    `incoming` is always stripped and lower-cased before comparison,
    but the original text is stored for free-text fields.
    """
    raw = incoming.strip()
    token = raw.lower()

    # Step 1: driver confirmation (only once per load)
    if load.driver_confirmed is None:
        await _handle_driver_confirmation(load, token, raw, db)
        return

    if load.driver_confirmed is False:
        # Already said not the driver — ignore further messages
        return

    # Step 2: if we're mid-flow waiting for a specific answer
    if load.pending_step:
        await _handle_pending_step(load, token, raw, db)
        return

    # Step 3: main menu selection (or first menu send)
    await _handle_menu_selection(load, token, db)


# ── Driver confirmation ───────────────────────────────────────────────────────

async def _handle_driver_confirmation(
    load: Load, token: str, raw: str, db: AsyncSession
) -> None:
    if token in YES_IDS or token == "yes":
        load.driver_confirmed = True
        await db.commit()
        await _send_main_menu(load)
    elif token in NO_IDS or token == "no":
        load.driver_confirmed = False
        await db.commit()
        await send_text(load.driver_whatsapp, msg.thank_you_close())
    else:
        # Re-ask
        await send_buttons(
            load.driver_whatsapp,
            msg.ask_driver_confirmation(
                load.vehicle_no, load.from_location, load.to_location
            ),
            buttons=[
                {"id": "yes", "title": "Yes"},
                {"id": "no", "title": "No"},
            ],
        )


# ── Main menu ─────────────────────────────────────────────────────────────────

async def _send_main_menu(load: Load) -> None:
    await send_list(
        load.driver_whatsapp,
        msg.MAIN_MENU_BODY,
        button_label="Select Status",
        sections=msg.MAIN_MENU_SECTIONS,
        header=f"Load: {load.vehicle_no} | {load.from_location} → {load.to_location}",
    )


async def _handle_menu_selection(
    load: Load, token: str, db: AsyncSession
) -> None:
    stage_map = {
        "stage_1": 1, "1": 1,
        "stage_2": 2, "2": 2,
        "stage_3": 3, "3": 3,
        "stage_4": 4, "4": 4,
        "stage_5": 5, "5": 5,
    }
    selected = stage_map.get(token)
    if selected is None:
        await _send_main_menu(load)
        return

    load.last_menu_selection = selected
    now = datetime.utcnow()

    # Anti-redundancy: collect missing critical fields if jumping ahead
    # Then enter the target stage
    if selected == 1:
        await _enter_stage1(load, db, now)
    elif selected == 2:
        await _enter_stage2(load, db, now)
    elif selected == 3:
        await _enter_stage3(load, db, now)
    elif selected == 4:
        await _enter_stage4(load, db, now)
    elif selected == 5:
        await _enter_stage5(load, db, now)

    await db.commit()


# ── Stage 1: Enroute ──────────────────────────────────────────────────────────

async def _enter_stage1(load: Load, db: AsyncSession, now: datetime) -> None:
    load.current_stage = 1
    if not load.stage1_entered_at:
        load.stage1_entered_at = now

    # Check for unresolved Stage 1 issue
    if load.s1_issue_text and load.s1_issue_resolved is False:
        load.pending_step = "s1_issue_resolution"
        await send_buttons(
            load.driver_whatsapp,
            msg.ask_s1_issue_resolved(load.s1_issue_text),
            buttons=[{"id": "yes", "title": "Yes"}, {"id": "no", "title": "No"}],
        )
    else:
        await _ask_s1_location(load)


async def _ask_s1_location(load: Load) -> None:
    load.pending_step = "s1_location"
    await send_text(load.driver_whatsapp, msg.ask_current_location())


async def _ask_s1_difficulty(load: Load) -> None:
    load.pending_step = "s1_difficulty"
    await send_buttons(
        load.driver_whatsapp,
        msg.ask_difficulty(),
        buttons=[{"id": "yes", "title": "Yes"}, {"id": "no", "title": "No"}],
    )


# ── Stage 2: Reached unloading point ─────────────────────────────────────────

async def _enter_stage2(load: Load, db: AsyncSession, now: datetime) -> None:
    load.current_stage = 2
    if not load.stage2_entered_at:
        load.stage2_entered_at = now

    # Critical field — always ask first
    if not load.s2_report_time:
        load.pending_step = "s2_report_time"
        await ask_datetime(load.driver_whatsapp, msg.ask_s2_report_time())
    else:
        await _ask_s2_issue(load)


async def _ask_s2_issue(load: Load) -> None:
    if load.s2_last_issue_text and load.s2_same_issue_still_open is not False:
        # Earlier issue exists — ask if still ongoing
        load.pending_step = "s2_existing_issue_yn"
        await send_buttons(
            load.driver_whatsapp,
            msg.ask_s2_issue_existing(load.s2_last_issue_text),
            buttons=[{"id": "yes", "title": "Yes"}, {"id": "no", "title": "No"}],
        )
    else:
        load.pending_step = "s2_issue_yn"
        await send_buttons(
            load.driver_whatsapp,
            msg.ask_s2_issue_yn(),
            buttons=[{"id": "yes", "title": "Yes"}, {"id": "no", "title": "No"}],
        )


# ── Stage 3: Unloading started ────────────────────────────────────────────────

async def _enter_stage3(load: Load, db: AsyncSession, now: datetime) -> None:
    load.current_stage = 3
    if not load.stage3_entered_at:
        load.stage3_entered_at = now

    load.pending_step = "s3_issue_yn"
    await send_buttons(
        load.driver_whatsapp,
        msg.ask_s3_issue(),
        buttons=[{"id": "yes", "title": "Yes"}, {"id": "no", "title": "No"}],
    )


# ── Stage 4: Unloaded, POD not received ──────────────────────────────────────

async def _enter_stage4(load: Load, db: AsyncSession, now: datetime) -> None:
    load.current_stage = 4
    if not load.stage4_entered_at:
        load.stage4_entered_at = now

    # Critical field — always ask first
    if not load.s4_unloading_complete_time:
        load.pending_step = "s4_unloading_time"
        await ask_datetime(load.driver_whatsapp, msg.ask_s4_unloading_time())
    else:
        await _ask_s4_charges(load)


async def _ask_s4_charges(load: Load) -> None:
    if load.s4_charges_above_100 is None:
        load.pending_step = "s4_charges_yn"
        await send_buttons(
            load.driver_whatsapp,
            msg.ask_charges_yn(),
            buttons=[{"id": "yes", "title": "Yes"}, {"id": "no", "title": "No"}],
        )
    else:
        # Already captured — send closing message
        await _send_s4_closing(load)


async def _send_s4_closing(load: Load) -> None:
    load.pending_step = None
    _schedule_followup(load)
    if load.s4_charges_above_100:
        await send_text(
            load.driver_whatsapp,
            msg.stage4_pod_seal_warning_no_charges()
            if not load.s4_amount_paid
            else (
                f"Charges of INR {load.s4_amount_paid:.0f} noted. "
                + msg.stage4_pod_seal_warning_no_charges()
            ),
        )
    else:
        await send_text(load.driver_whatsapp, msg.stage4_pod_seal_warning_no_charges())


# ── Stage 5: Unloaded + POD received ─────────────────────────────────────────

async def _enter_stage5(load: Load, db: AsyncSession, now: datetime) -> None:
    load.current_stage = 5
    if not load.stage5_entered_at:
        load.stage5_entered_at = now

    # Collect any missing Stage 4 critical fields first
    missing = _missing_stage4_fields(load)
    if missing:
        await _collect_missing_s4_for_s5(load, missing)
    else:
        await _ask_s5_confirmation(load)


def _missing_stage4_fields(load: Load) -> list[str]:
    missing = []
    if not load.s4_unloading_complete_time:
        missing.append("unloading_time")
    if load.s4_charges_above_100 is None:
        missing.append("charges_yn")
    if load.s4_charges_above_100 is True and load.s4_amount_paid is None:
        missing.append("amount_paid")
    return missing


async def _collect_missing_s4_for_s5(load: Load, missing: list[str]) -> None:
    field = missing[0]
    if field == "unloading_time":
        load.pending_step = "s5_fill_s4_unloading_time"
        await ask_datetime(load.driver_whatsapp, msg.ask_s4_unloading_time())
    elif field == "charges_yn":
        load.pending_step = "s5_fill_s4_charges_yn"
        await send_buttons(
            load.driver_whatsapp,
            msg.ask_charges_yn(),
            buttons=[{"id": "yes", "title": "Yes"}, {"id": "no", "title": "No"}],
        )
    elif field == "amount_paid":
        load.pending_step = "s5_fill_s4_amount"
        await send_text(load.driver_whatsapp, msg.ask_charges_amount())


async def _ask_s5_confirmation(load: Load) -> None:
    if load.s4_charges_above_100 is False:
        load.pending_step = "s5_confirm_yn"
        await send_buttons(
            load.driver_whatsapp,
            msg.ask_s5_confirm_no_charges(),
            buttons=[{"id": "yes", "title": "Yes"}, {"id": "no", "title": "No"}],
        )
    else:
        amount = load.s5_corrected_amount or load.s4_amount_paid or 0
        load.pending_step = "s5_confirm_yn"
        await send_buttons(
            load.driver_whatsapp,
            msg.ask_s5_confirm_with_charges(amount),
            buttons=[{"id": "yes", "title": "Yes"}, {"id": "no", "title": "No"}],
        )


# ── Pending step dispatcher ───────────────────────────────────────────────────

async def _handle_pending_step(
    load: Load, token: str, raw: str, db: AsyncSession
) -> None:
    step = load.pending_step

    # ── Stage 1 steps ────────────────────────────────────────────────────
    if step == "s1_issue_resolution":
        if token in YES_IDS or token == "yes":
            load.s1_issue_resolved = True
            await _ask_s1_location(load)
        else:
            load.pending_step = None
            _schedule_followup(load)
            await send_text(
                load.driver_whatsapp,
                msg.stage1_unresolved_issue(load.s1_issue_text or ""),
            )

    elif step == "s1_location":
        load.s1_last_location = raw
        load.s1_last_location_at = datetime.utcnow()
        await _ask_s1_difficulty(load)

    elif step == "s1_difficulty":
        if token in YES_IDS or token == "yes":
            load.s1_difficulty_flag = True
            load.pending_step = "s1_issue_type"
            await send_buttons(
                load.driver_whatsapp,
                "Please select the difficulty you are facing:",
                buttons=[
                    {"id": "s1_no_fuel", "title": "No fuel / breakdown"},
                    {"id": "s1_route", "title": "Route/road issue"},
                    {"id": "s1_other", "title": "Other issue"},
                ],
            )
        else:
            load.s1_difficulty_flag = False
            load.pending_step = None
            _schedule_followup(load)
            await send_text(load.driver_whatsapp, msg.generic_thank_you())

    elif step == "s1_issue_type":
        load.s1_issue_type = token
        if token == "s1_other":
            load.pending_step = "s1_issue_text"
            await send_text(load.driver_whatsapp, "Please describe the issue:")
        else:
            label = {
                "s1_no_fuel": "No fuel / breakdown",
                "s1_route": "Route/road issue",
            }.get(token, token)
            load.s1_issue_text = label
            load.s1_issue_resolved = False
            load.pending_step = None
            _schedule_followup(load)
            await send_text(load.driver_whatsapp, msg.stage1_issue_noted())

    elif step == "s1_issue_text":
        load.s1_issue_text = raw
        load.s1_issue_resolved = False
        load.pending_step = None
        _schedule_followup(load)
        await send_text(load.driver_whatsapp, msg.stage1_issue_noted())

    # ── Stage 2 steps ────────────────────────────────────────────────────
    elif step == "s2_report_time":
        load.s2_report_time = raw
        await _ask_s2_issue(load)

    elif step == "s2_existing_issue_yn":
        if token in YES_IDS or token == "yes":
            load.s2_same_issue_still_open = True
            load.pending_step = None
            _schedule_followup(load)
            await send_text(load.driver_whatsapp, msg.stage23_issue_noted())
        else:
            load.s2_same_issue_still_open = False
            load.pending_step = "s2_new_issue_yn"
            await send_buttons(
                load.driver_whatsapp,
                msg.ask_s2_new_issue(),
                buttons=[{"id": "yes", "title": "Yes"}, {"id": "no", "title": "No"}],
            )

    elif step == "s2_new_issue_yn":
        if token in YES_IDS or token == "yes":
            load.pending_step = "s2_new_issue_text"
            await send_text(load.driver_whatsapp, "Please describe the new issue:")
        else:
            load.pending_step = None
            _schedule_followup(load)
            await send_text(load.driver_whatsapp, msg.generic_thank_you())

    elif step == "s2_new_issue_text":
        load.s2_new_issue_text = raw
        load.s2_last_issue_text = raw
        load.s2_same_issue_still_open = True
        load.pending_step = None
        _schedule_followup(load)
        await send_text(load.driver_whatsapp, msg.stage23_issue_noted())

    elif step == "s2_issue_yn":
        if token in YES_IDS or token == "yes":
            load.s2_issue_flag = True
            load.pending_step = "s2_issue_select"
            await send_buttons(
                load.driver_whatsapp,
                msg.ask_s2_select_issue(),
                buttons=[
                    {"id": "s2_no_space", "title": "No space to unload"},
                    {"id": "s2_wrong_material", "title": "Wrong material"},
                    {"id": "s2_other", "title": "Any other issue"},
                ],
            )
        else:
            load.s2_issue_flag = False
            load.pending_step = None
            _schedule_followup(load)
            await send_text(load.driver_whatsapp, msg.generic_thank_you())

    elif step == "s2_issue_select":
        if token == "s2_other":
            load.pending_step = "s2_other_issue_text"
            await send_text(load.driver_whatsapp, "Please describe the issue:")
        else:
            label = {
                "s2_no_space": "No space to unload",
                "s2_wrong_material": "Wrong material received",
            }.get(token, raw)
            load.s2_last_issue_text = label
            load.s2_last_issue_type = token
            load.s2_same_issue_still_open = True
            load.pending_step = None
            _schedule_followup(load)
            await send_text(load.driver_whatsapp, msg.stage23_issue_noted())

    elif step == "s2_other_issue_text":
        load.s2_last_issue_text = raw
        load.s2_last_issue_type = "other"
        load.s2_same_issue_still_open = True
        load.pending_step = None
        _schedule_followup(load)
        await send_text(load.driver_whatsapp, msg.stage23_issue_noted())

    # ── Stage 3 steps ────────────────────────────────────────────────────
    elif step == "s3_issue_yn":
        if token in YES_IDS or token == "yes":
            load.s3_issue_while_unloading = True
            load.pending_step = "s3_issue_text"
            await send_text(load.driver_whatsapp, "Please describe the issue:")
        else:
            load.s3_issue_while_unloading = False
            load.pending_step = None
            _schedule_followup(load)
            await send_text(load.driver_whatsapp, msg.generic_thank_you())

    elif step == "s3_issue_text":
        load.s3_issue_text = raw
        load.pending_step = None
        _schedule_followup(load)
        await send_text(load.driver_whatsapp, msg.stage23_issue_noted())

    # ── Stage 4 steps ────────────────────────────────────────────────────
    elif step == "s4_unloading_time":
        load.s4_unloading_complete_time = raw
        await _ask_s4_charges(load)

    elif step == "s4_charges_yn":
        if token in YES_IDS or token == "yes":
            load.s4_charges_above_100 = True
            load.pending_step = "s4_amount"
            await send_text(load.driver_whatsapp, msg.ask_charges_amount())
        else:
            load.s4_charges_above_100 = False
            load.pending_step = None
            _schedule_followup(load)
            await send_text(load.driver_whatsapp, msg.stage4_pod_seal_warning_no_charges())

    elif step == "s4_amount":
        parsed = _parse_amount(raw)
        if parsed is None:
            await send_text(load.driver_whatsapp, msg.invalid_amount())
        else:
            load.s4_amount_paid = parsed
            load.pending_step = None
            _schedule_followup(load)
            await send_text(load.driver_whatsapp, msg.stage4_pod_seal_warning_no_charges())

    # ── Stage 5 — filling missing Stage 4 data ────────────────────────────
    elif step == "s5_fill_s4_unloading_time":
        load.s4_unloading_complete_time = raw
        missing = _missing_stage4_fields(load)
        if missing:
            await _collect_missing_s4_for_s5(load, missing)
        else:
            await _ask_s5_confirmation(load)

    elif step == "s5_fill_s4_charges_yn":
        if token in YES_IDS or token == "yes":
            load.s4_charges_above_100 = True
            missing = _missing_stage4_fields(load)
            if missing:
                await _collect_missing_s4_for_s5(load, missing)
            else:
                await _ask_s5_confirmation(load)
        else:
            load.s4_charges_above_100 = False
            await _ask_s5_confirmation(load)

    elif step == "s5_fill_s4_amount":
        parsed = _parse_amount(raw)
        if parsed is None:
            await send_text(load.driver_whatsapp, msg.invalid_amount())
        else:
            load.s4_amount_paid = parsed
            await _ask_s5_confirmation(load)

    # ── Stage 5 confirmation ──────────────────────────────────────────────
    elif step == "s5_confirm_yn":
        if token in YES_IDS or token == "yes":
            load.pending_step = None
            load.is_active = False    # POD flow complete — stop loop
            if load.s4_charges_above_100 is False:
                await send_text(load.driver_whatsapp, msg.pod_instruction_no_charges())
            else:
                await send_text(load.driver_whatsapp, msg.pod_instruction_with_charges())
        else:
            # Confirmation rejected — ask corrected amount
            load.pending_step = "s5_corrected_amount"
            await send_text(load.driver_whatsapp, msg.ask_corrected_amount())

    elif step == "s5_corrected_amount":
        parsed = _parse_amount(raw)
        if parsed is None:
            await send_text(load.driver_whatsapp, msg.invalid_amount())
        else:
            load.s5_corrected_amount = parsed
            load.pending_step = "s5_pod_seal_yn"
            await send_buttons(
                load.driver_whatsapp,
                msg.ask_charges_on_pod(),
                buttons=[{"id": "yes", "title": "Yes"}, {"id": "no", "title": "No"}],
            )

    elif step == "s5_pod_seal_yn":
        load.pending_step = None
        load.is_active = False
        if token in YES_IDS or token == "yes":
            load.s5_charges_on_pod = True
            await send_text(load.driver_whatsapp, msg.pod_instruction_no_charges())
        else:
            load.s5_charges_on_pod = False
            await send_text(load.driver_whatsapp, msg.pod_no_seal_warning())

    else:
        # Unknown pending step — reset to menu
        load.pending_step = None
        await _send_main_menu(load)

    await db.commit()


# ── Scheduler helpers ─────────────────────────────────────────────────────────

def _schedule_followup(load: Load) -> None:
    """Set next_followup_due to now + FOLLOWUP_INTERVAL_SECONDS."""
    load.next_followup_due = datetime.utcnow() + timedelta(
        seconds=settings.FOLLOWUP_INTERVAL_SECONDS
    )


# ── Utility ───────────────────────────────────────────────────────────────────

def _parse_amount(raw: str) -> float | None:
    """Return float if raw is a valid number, else None."""
    try:
        cleaned = raw.replace(",", "").replace("₹", "").replace("INR", "").strip()
        return float(cleaned)
    except ValueError:
        return None


# ── First-time trigger (called by scheduler or load creation API) ─────────────

async def trigger_load(load: Load, db: AsyncSession) -> None:
    """
    Called load_out_time + 6 hours.
    Sends the driver confirmation question to open the conversation.
    Uses a template message to open the 24-hour window.
    """
    from app.services.whatsapp import send_buttons
    await send_buttons(
        load.driver_whatsapp,
        msg.ask_driver_confirmation(
            load.vehicle_no, load.from_location, load.to_location
        ),
        buttons=[
            {"id": "yes", "title": "Yes"},
            {"id": "no", "title": "No"},
        ],
        header="Shivani Carriers - Load Update",
        footer="Reply Yes to confirm you are the driver",
    )
    await db.commit()
