"""
Load model — stores all per-load state required by the spec.

One row per active load. When a load closes (Stage 5 + POD received
OR backend manually closes), is_active is set to False.
"""
from datetime import datetime
from sqlalchemy import (
    Boolean, Column, DateTime, Float, Integer, String, Text
)

from app.models.base import Base


class Load(Base):
    __tablename__ = "loads"

    # ── Identity ──────────────────────────────────────────────────────────────
    id = Column(Integer, primary_key=True, autoincrement=True)
    vehicle_no = Column(String(50), nullable=False)
    from_location = Column(String(200), nullable=False)
    to_location = Column(String(200), nullable=False)
    bilty_no = Column(String(100), nullable=False)
    bilty_date = Column(String(50), nullable=False)          # stored as string (user input)
    driver_whatsapp = Column(String(20), nullable=False)     # E.164 format

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    is_active = Column(Boolean, default=True, nullable=False)
    load_out_time = Column(DateTime, nullable=False)         # trigger = load_out + 6h
    driver_confirmed = Column(Boolean, default=None)         # None = not yet asked

    # ── Flow state ────────────────────────────────────────────────────────────
    current_stage = Column(Integer, default=0)               # 0 = pre-menu
    # Tracks exactly which sub-step we are waiting for within a stage
    # e.g. "s1_location", "s2_critical", "s4_charges_yn", "s5_confirm_yn" …
    pending_step = Column(String(100), default=None)

    last_menu_selection = Column(Integer, default=None)
    next_followup_due = Column(DateTime, default=None)

    # Stage timestamps
    stage1_entered_at = Column(DateTime, default=None)
    stage2_entered_at = Column(DateTime, default=None)
    stage3_entered_at = Column(DateTime, default=None)
    stage4_entered_at = Column(DateTime, default=None)
    stage5_entered_at = Column(DateTime, default=None)

    # ── Stage 1 ───────────────────────────────────────────────────────────────
    s1_last_location = Column(Text, default=None)
    s1_last_location_at = Column(DateTime, default=None)
    s1_difficulty_flag = Column(Boolean, default=None)
    s1_issue_text = Column(Text, default=None)
    s1_issue_type = Column(String(50), default=None)         # "no_space"|"wrong_material"|"other"
    s1_issue_resolved = Column(Boolean, default=None)

    # ── Stage 2 ───────────────────────────────────────────────────────────────
    s2_report_time = Column(String(50), default=None)        # date+time string
    s2_issue_flag = Column(Boolean, default=None)
    s2_last_issue_text = Column(Text, default=None)
    s2_last_issue_type = Column(String(50), default=None)
    s2_same_issue_still_open = Column(Boolean, default=None)
    s2_new_issue_text = Column(Text, default=None)

    # ── Stage 3 ───────────────────────────────────────────────────────────────
    s3_issue_while_unloading = Column(Boolean, default=None)
    s3_issue_text = Column(Text, default=None)
    s3_entered_at = Column(DateTime, default=None)

    # ── Stage 4 / 5 ───────────────────────────────────────────────────────────
    s4_unloading_complete_time = Column(String(50), default=None)
    s4_charges_above_100 = Column(Boolean, default=None)
    s4_amount_paid = Column(Float, default=None)
    s5_corrected_amount = Column(Float, default=None)
    s5_charges_on_pod = Column(Boolean, default=None)        # seal & sign confirmed?
    s5_pod_copy_received = Column(Boolean, default=False)    # WhatsApp POD copy received

    # ── Audit ─────────────────────────────────────────────────────────────────
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return (
            f"<Load id={self.id} vehicle={self.vehicle_no} "
            f"stage={self.current_stage} active={self.is_active}>"
        )
