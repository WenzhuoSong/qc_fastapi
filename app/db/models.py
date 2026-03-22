"""
ORM Models

- DailyDecision:       Checkpoint state machine for the LLM research pipeline
- DailyHoldings:       Intraday holdings snapshot reported by QuantConnect
- DailyNewsDigest:     Structured macro/micro summary stored after each pipeline run
- DecisionLog:         Full decision audit trail for post-hoc analysis
- TickerNewsLibrary:   Pre-fetched per-ticker news with LLM summaries and sentiment
- SectorNewsLibrary:   Aggregated sector-level summaries from constituent ticker news
- EventTransmission:   Phase 2 - Macro event → sector transmission vectors (causal modeling)
"""

import datetime
import uuid
from sqlalchemy import Column, Date, String, Text, DateTime, Boolean, Integer, Float, UniqueConstraint, func
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

    Populated by pre_fetch_pipeline.py at 13:30 ET for all holdings,
    QC candidates, and ETF_TOP5 constituents.
    Read by cron_pipeline.py at 14:00 ET — no real-time API calls needed.

    Phase 1 enhancements (2026-03-17):
    - category: filter noise ("company news" vs "press release")
    - related: contagion analysis (related tickers from Finnhub)
    - datetime_utc: Unix timestamp for time-series clustering
    - url: optional link to full article
    - credibility: source trustworthiness score (0-100 integer)
    """
    __tablename__ = "ticker_news_library"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ticker = Column(String(10), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    headline = Column(Text, nullable=False)
    source = Column(String(100), nullable=True)
    llm_summary = Column(Text, nullable=True)
    sentiment = Column(String(10), nullable=True)
    relevance = Column(String(15), nullable=True)
    is_hard_event = Column(Boolean, default=False)

    # Phase 1 enhancements
    category = Column(String(50), nullable=True)
    related = Column(JSONB, nullable=True)  # List of related ticker symbols
    datetime_utc = Column(Integer, nullable=True)  # Unix timestamp
    url = Column(Text, nullable=True)
    credibility = Column(Integer, nullable=True)  # 0-100 score

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("ticker", "headline", name="uq_ticker_headline"),
    )

    def __repr__(self) -> str:
        return f"<TickerNews {self.ticker} {self.date} hard={self.is_hard_event}>"


class SectorNewsLibrary(Base):
    """Aggregated sector-level summaries derived from constituent ticker news.

    Each row is one sector ETF's daily outlook, synthesized from the
    individual ticker news of its top-5 holdings.
    """
    __tablename__ = "sector_news_library"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sector = Column(String(10), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    sector_summary = Column(Text, nullable=True)
    sentiment = Column(String(10), nullable=True)
    outlook = Column(String(10), nullable=True)
    key_themes = Column(JSONB, nullable=True)
    contributing_tickers = Column(JSONB, nullable=True)
    news_count = Column(Integer, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("sector", "date", name="uq_sector_date"),
    )

    def __repr__(self) -> str:
        return f"<SectorNews {self.sector} {self.date} outlook={self.outlook}>"


class EventTransmission(Base):
    """Phase 2: Event transmission vectors — macro event → sector impact mapping.

    Records canonical transmission patterns for each macro event detected by Step 1.
    Used to provide sector priors to Step 2, then validated via backtesting.

    Example:
        Event: "Strait of Hormuz closure"
        Transmission: {"XLE": 0.95, "XLY": -0.75, "XLI": 0.70, ...}

    The transmission_vector maps sector ETF symbols to impact strength:
        1.0  = Full direct beneficiary (e.g., oil spike → XLE)
        0.5-0.8 = Strong secondary effect
        0.2-0.4 = Weak indirect effect
        0.0  = Neutral
        -0.2 to -1.0 = Negative impact (losers)

    Post-hoc validation:
        - accuracy_score: Correlation between predicted transmission and actual sector returns
        - validated: True after backtesting completes
    """
    __tablename__ = "event_transmission"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, index=True)
    event_id = Column(String(100), unique=True, nullable=False, index=True)
    event_type = Column(String(50), index=True)  # supply_shock, demand_shock, rate_shock, etc.
    event_description = Column(Text, nullable=True)
    confidence = Column(Integer, nullable=True)  # 0-100 from Step 1
    transmission_vector = Column(JSONB, nullable=True)  # {sector: strength, ...}

    # Backtesting validation
    validated = Column(Boolean, default=False)
    accuracy_score = Column(Float, nullable=True)  # 0.0-1.0 correlation

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<EventTransmission {self.date} {self.event_id} validated={self.validated}>"
