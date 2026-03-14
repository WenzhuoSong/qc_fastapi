"""
ORM Models

- DailyDecision: Checkpoint state machine for the LLM research pipeline
- DailyHoldings: Intraday holdings snapshot reported by QuantConnect at 10:00 ET
"""

import datetime
from sqlalchemy import Column, Date, String, Text, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB

from app.db.database import Base


class DailyDecision(Base):
    """Pipeline checkpoint: INIT → STEP1_DONE → STEP2_DONE → STEP3_DONE → READY (or ERROR)"""
    __tablename__ = "daily_decisions"

    date = Column(Date, primary_key=True)
    status = Column(String(20), default="INIT", nullable=False)

    step1_macro_result = Column(Text, nullable=True)
    step2_micro_result = Column(Text, nullable=True)
    step3_risk_result = Column(Text, nullable=True)

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


class DailyHoldings(Base):
    """10:00 ET holdings snapshot from QuantConnect — serves as input context for the 14:00 pipeline."""
    __tablename__ = "daily_holdings"

    date = Column(Date, primary_key=True, default=datetime.date.today)
    tickers = Column(JSONB, nullable=False)
    payload = Column(JSONB, nullable=True)

    received_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    def __repr__(self) -> str:
        return f"<DailyHoldings {self.date} tickers={self.tickers}>"
