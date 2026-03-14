"""
Decision Log Endpoint — Review and Backfill

GET  /decisions/         → list recent decisions for review
GET  /decisions/{date}   → single day detail
PATCH /decisions/{date}  → backfill market_outcome and decision_correct
"""

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.security import verify_token
from app.db.database import get_db
from app.db.models import DecisionLog
from app.models.schemas import DecisionLogResponse, DecisionLogUpdate

router = APIRouter()


def _row_to_response(row: DecisionLog) -> DecisionLogResponse:
    return DecisionLogResponse(
        date=str(row.date),
        qc_regime=row.qc_regime,
        ai_regime=row.ai_regime,
        regime_override=row.regime_override,
        confidence=row.confidence,
        defense_level=row.defense_level,
        final_weights=row.final_weights,
        reasoning=row.reasoning,
        market_outcome=row.market_outcome,
        decision_correct=row.decision_correct,
    )


@router.get("/", response_model=list[DecisionLogResponse])
async def list_decisions(
    limit: int = Query(default=20, le=100),
    _token: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """List recent decision logs for review and accuracy tracking."""
    rows = (
        db.query(DecisionLog)
        .order_by(desc(DecisionLog.date))
        .limit(limit)
        .all()
    )
    return [_row_to_response(r) for r in rows]


@router.get("/{target_date}", response_model=DecisionLogResponse)
async def get_decision(
    target_date: str,
    _token: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """Get a specific day's decision log."""
    try:
        d = datetime.strptime(target_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(400, "Date must be YYYY-MM-DD")

    row = db.query(DecisionLog).filter_by(date=d).first()
    if not row:
        raise HTTPException(404, f"No decision log for {target_date}")
    return _row_to_response(row)


@router.patch("/{target_date}", response_model=DecisionLogResponse)
async def update_decision(
    target_date: str,
    update: DecisionLogUpdate,
    _token: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """Backfill post-hoc analysis: market_outcome and decision_correct.

    Used for building the validation dataset to measure AI accuracy.
    """
    try:
        d = datetime.strptime(target_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(400, "Date must be YYYY-MM-DD")

    row = db.query(DecisionLog).filter_by(date=d).first()
    if not row:
        raise HTTPException(404, f"No decision log for {target_date}")

    if update.market_outcome is not None:
        row.market_outcome = update.market_outcome
    if update.decision_correct is not None:
        row.decision_correct = update.decision_correct

    db.commit()
    return _row_to_response(row)
