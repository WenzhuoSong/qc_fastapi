"""
Holdings Endpoint — QC 10:00 ET Position Snapshot

QuantConnect reports its current holdings each morning. This data is
stored in PostgreSQL and later used as context for the 14:00 ET
LLM research pipeline.
"""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import verify_token
from app.db.database import get_db
from app.db.models import DailyHoldings
from app.models.schemas import HoldingsRequest, HoldingsResponse

router = APIRouter()


@router.post("/", response_model=HoldingsResponse)
async def submit_holdings(
    request: HoldingsRequest,
    _token: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """Receive and store today's holdings from QuantConnect.

    Idempotent: if today's record already exists, it gets updated.
    """
    today = date.today()

    record = db.query(DailyHoldings).filter_by(date=today).first()

    if record:
        record.tickers = request.current_holdings
        record.payload = request.model_dump()
    else:
        record = DailyHoldings(
            date=today,
            tickers=request.current_holdings,
            payload=request.model_dump(),
        )
        db.add(record)

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    return HoldingsResponse(
        status="ok",
        message=f"Holdings for {today} recorded ({len(request.current_holdings)} tickers)",
    )


@router.get("/")
async def get_today_holdings(
    _token: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """Retrieve today's holdings snapshot (for debugging / pipeline use)."""
    today = date.today()
    record = db.query(DailyHoldings).filter_by(date=today).first()

    if not record:
        return {"date": str(today), "status": "no_data", "tickers": [], "payload": None}

    return {
        "date": str(record.date),
        "status": "ok",
        "tickers": record.tickers,
        "payload": record.payload,
    }
