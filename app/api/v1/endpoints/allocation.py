"""
Allocation Endpoint — The Delivery Gateway for QuantConnect

This endpoint NEVER calls LLM. It only queries PostgreSQL and returns
pre-computed weights. Designed for <10ms response time.

Graceful degradation (is_stale):
  - Happy path: today's READY record → is_stale=false
  - Fallback: most recent READY record → is_stale=true
  - No data at all: empty weights with error message

Also returns:
  - defense_level: full / light / half (for position sizing)
  - risk_flags: per-ticker hard risk flags (for exclusion logic)
  - regime: AI's macro regime call
"""

from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.security import verify_token_flexible
from app.db.database import get_db
from app.db.models import DailyDecision, DailyNewsDigest, DecisionLog, EventTransmission
from app.models.schemas import AllocationResponse

router = APIRouter()


def _extract_risk_flags(digest: DailyNewsDigest | None) -> dict:
    """Extract {ticker: [flag_list]} from DailyNewsDigest.ticker_risks."""
    if not digest or not digest.ticker_risks:
        return {}
    flags = {}
    for ticker, info in digest.ticker_risks.items():
        f = info.get("flags", []) if isinstance(info, dict) else []
        if f:
            flags[ticker] = f
    return flags


@router.get("/", response_model=AllocationResponse)
async def get_allocation(
    _token: str = Depends(verify_token_flexible),
    db: Session = Depends(get_db),
):
    """Return the latest portfolio allocation weights for QuantConnect.

    Supports both Bearer token and query param (?token=xxx) for QC compatibility.
    """
    today = date.today()

    today_row = db.query(DailyDecision).filter_by(
        date=today, status="READY"
    ).first()

    if today_row:
        log = db.query(DecisionLog).filter_by(date=today).first()
        digest = db.query(DailyNewsDigest).filter_by(date=today).first()
        transmission = db.query(EventTransmission).filter_by(date=today).first()

        # Phase 3a & 3b: Extract event direction and duration analysis from step1_macro_result
        import json
        net_escalation = None
        regime_phase = None
        event_direction_reasoning = None
        duration_estimate = None
        duration_category = None
        exit_strategy = None
        tactical_implications = None
        if today_row.step1_macro_result:
            try:
                step1_data = json.loads(today_row.step1_macro_result)
                # Phase 3a
                net_escalation = step1_data.get("net_escalation_score")
                regime_phase = step1_data.get("regime_phase")
                event_direction_reasoning = step1_data.get("event_direction_reasoning")
                # Phase 3b
                duration_estimate = step1_data.get("duration_estimate")
                duration_category = step1_data.get("duration_category")
                exit_strategy = step1_data.get("exit_strategy")
                tactical_implications = step1_data.get("tactical_implications")
            except json.JSONDecodeError:
                pass

        return AllocationResponse(
            date=str(today_row.date),
            status=today_row.status,
            is_stale=False,
            weights=today_row.final_weights or {},
            defense_level=log.defense_level if log else "full",
            risk_flags=_extract_risk_flags(digest),
            regime=log.ai_regime if log else None,
            confidence=log.confidence if log else None,
            regime_override=log.regime_override if log else None,
            transmission_vector=transmission.transmission_vector if transmission else None,
            net_escalation_score=net_escalation,
            regime_phase=regime_phase,
            event_direction_reasoning=event_direction_reasoning,
            duration_estimate=duration_estimate,
            duration_category=duration_category,
            exit_strategy=exit_strategy,
            tactical_implications=tactical_implications,
        )

    latest_row = (
        db.query(DailyDecision)
        .filter_by(status="READY")
        .order_by(desc(DailyDecision.date))
        .first()
    )

    if latest_row:
        log = db.query(DecisionLog).filter_by(date=latest_row.date).first()
        digest = db.query(DailyNewsDigest).filter_by(date=latest_row.date).first()
        transmission = db.query(EventTransmission).filter_by(date=latest_row.date).first()

        # Phase 3a & 3b: Extract event direction and duration analysis
        import json
        net_escalation = None
        regime_phase = None
        event_direction_reasoning = None
        duration_estimate = None
        duration_category = None
        exit_strategy = None
        tactical_implications = None
        if latest_row.step1_macro_result:
            try:
                step1_data = json.loads(latest_row.step1_macro_result)
                # Phase 3a
                net_escalation = step1_data.get("net_escalation_score")
                regime_phase = step1_data.get("regime_phase")
                event_direction_reasoning = step1_data.get("event_direction_reasoning")
                # Phase 3b
                duration_estimate = step1_data.get("duration_estimate")
                duration_category = step1_data.get("duration_category")
                exit_strategy = step1_data.get("exit_strategy")
                tactical_implications = step1_data.get("tactical_implications")
            except json.JSONDecodeError:
                pass

        return AllocationResponse(
            date=str(latest_row.date),
            status=latest_row.status,
            is_stale=True,
            weights=latest_row.final_weights or {},
            defense_level=log.defense_level if log else "full",
            risk_flags=_extract_risk_flags(digest),
            regime=log.ai_regime if log else None,
            confidence=log.confidence if log else None,
            regime_override=log.regime_override if log else None,
            transmission_vector=transmission.transmission_vector if transmission else None,
            net_escalation_score=net_escalation,
            regime_phase=regime_phase,
            event_direction_reasoning=event_direction_reasoning,
            duration_estimate=duration_estimate,
            duration_category=duration_category,
            exit_strategy=exit_strategy,
            tactical_implications=tactical_implications,
            message=f"No READY data for {today}, using {latest_row.date}",
        )

    return AllocationResponse(
        date=str(today),
        status="NO_DATA",
        is_stale=True,
        weights={},
        message="No allocation data available yet",
    )
