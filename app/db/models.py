"""
ORM Models

- DailyDecision:      Checkpoint state machine for the LLM research pipeline
- DailyHoldings:      Intraday holdings snapshot reported by QuantConnect
- DailyNewsDigest:    Structured macro/micro summary stored after each pipeline run
- DecisionLog:        Full decision audit trail for post-hoc analysis
- TickerNewsLibrary:  Pre-fetched per-ticker news with LLM summaries and sentiment
"""

import datetime
import uuid
from sqlalchemy import Column, Date, String, Text, DateTime, Boolean, Integer, UniqueConstraint, func
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
    """Holdings snapshot from QuantConnect — updated at 10:00 or 13:30 ET."""
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


class TickerNewsLibrary(Base):
    """Pre-fetched per-ticker news with LLM-generated summaries.

    Populated by pre_fetch_pipeline.py at 13:30 ET for all top_candidates.
    Read by cron_pipeline.py at 14:00 ET — no real-time API calls needed.
    """
    __tablename__ = "ticker_news_library"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ticker = Column(String(10), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    headline = Column(Text, nullable=False)
    source = Column(String(100), nullable=True)
    llm_summary = Column(Text, nullable=True)
    sentiment = Column(String(10), nullable=True)
    is_hard_event = Column(Boolean, default=False)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("ticker", "headline", name="uq_ticker_headline"),
    )

    def __repr__(self) -> str:
        return f"<TickerNews {self.ticker} {self.date} hard={self.is_hard_event}>"
