"""
ORM Models

- DailyDecision:    Checkpoint state machine for the LLM research pipeline
- DailyHoldings:    Intraday holdings snapshot reported by QuantConnect at 10:00 ET
- DailyNewsDigest:  Structured macro/micro summary stored after each pipeline run
- DecisionLog:      Full decision audit trail for post-hoc analysis
"""

import datetime
from sqlalchemy import Column, Date, String, Text, DateTime, Boolean, Integer, func
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


class DailyNewsDigest(Base):
    """Structured macro + micro summary persisted after each pipeline run.

    Serves three purposes:
      1. Feed historical context back into Step 1 (trend awareness)
      2. Provide data for post-hoc news quality analysis
      3. Record per-ticker risk assessments
    """
    __tablename__ = "daily_news_digest"

    date = Column(Date, primary_key=True, default=datetime.date.today)
    macro_summary = Column(Text, nullable=True)
    macro_regime = Column(String(20), nullable=True)
    confidence = Column(Integer, nullable=True)
    key_events = Column(JSONB, nullable=True)
    sector_thesis = Column(Text, nullable=True)
    ticker_risks = Column(JSONB, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<DailyNewsDigest {self.date} regime={self.macro_regime}>"


class DecisionLog(Base):
    """Full decision audit trail — compares QC vs AI regime calls.

    Post-hoc fields (market_outcome, decision_correct) are left NULL
    and can be filled later for accuracy analysis.
    """
    __tablename__ = "decision_log"

    date = Column(Date, primary_key=True, default=datetime.date.today)
    qc_regime = Column(String(20), nullable=True)
    ai_regime = Column(String(20), nullable=True)
    regime_override = Column(Boolean, nullable=True)
    confidence = Column(Integer, nullable=True)
    defense_level = Column(String(20), nullable=True)
    final_weights = Column(JSONB, nullable=True)
    reasoning = Column(Text, nullable=True)

    market_outcome = Column(Text, nullable=True)
    decision_correct = Column(Boolean, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<DecisionLog {self.date} ai={self.ai_regime} override={self.regime_override}>"
