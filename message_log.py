"""
MessageLog — full audit trail of every inbound and outbound message.
"""
from datetime import datetime
from sqlalchemy import Column, DateTime, Integer, String, Text, ForeignKey

from app.models.base import Base


class MessageLog(Base):
    __tablename__ = "message_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    load_id = Column(Integer, ForeignKey("loads.id"), nullable=True)
    wa_message_id = Column(String(100), nullable=True)       # Meta message ID
    direction = Column(String(10), nullable=False)           # "inbound" | "outbound"
    from_number = Column(String(20), nullable=True)
    to_number = Column(String(20), nullable=True)
    message_type = Column(String(50), nullable=True)         # "text"|"interactive"|"template"
    content = Column(Text, nullable=True)                    # raw text or JSON summary
    stage_at_time = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
