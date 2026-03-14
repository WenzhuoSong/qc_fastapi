"""
ORM Models — daily_decisions Checkpoint State Machine

Status flow: INIT → STEP1_DONE → STEP2_DONE → STEP3_DONE → READY (or ERROR)
"""

from sqlalchemy import Column, Date, String, Text, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB

from app.db.database import Base


class DailyDecision(Base):
    __tablename__ = "daily_decisions"

    date = Column(Date, primary_key=True)
    status = Column(String(20), default="INIT", nullable=False)

    # Checkpoint fields for resume-on-failure
    step1_macro_result = Column(Text, nullable=True)
    step2_micro_result = Column(Text, nullable=True)
    step3_risk_result = Column(Text, nullable=True)

    # Final delivery
    final_weights = Column(JSONB, nullable=True)
    error_log = Column(Text, nullable=True)

    updated_at = Column(
        DateTime(timezone=True),
        default=func.now(),
        onupdate=func.now(),
    )

    VALID_STATUSES = ("INIT", "STEP1_DONE", "STEP2_DONE", "STEP3_DONE", "READY", "ERROR")

    def __repr__(self) -> str:
        return f"<DailyDecision {self.date} status={self.status}>"
