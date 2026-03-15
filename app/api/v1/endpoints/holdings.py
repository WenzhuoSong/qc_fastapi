"""
Holdings Endpoint — QC Position Snapshot

Supports two modes:
  POST /holdings/ — JSON body (local testing, standard HTTP clients)
  GET  /holdings/?data={url_encoded_json}&token={api_token}
       — QC's self.Download() only supports GET

Both modes accept current_holdings as either:
  list:  ["AAOI", "GE", "RTX"]
  dict:  {"AAOI": {"weight": 0.15, "gain_pct": -17.7, "days_held": 5}, ...}
"""

import json
from datetime import date
from urllib.parse import unquote
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import verify_token
from app.db.database import get_db
from app.db.models import DailyHoldings
from app.models.schemas import HoldingsRequest, HoldingsResponse

router = APIRouter()


def _normalize_payload(payload: dict) -> tuple[list[str], dict]:
    """Normalize current_holdings to a ticker list + enriched payload.

    Accepts both list and dict formats for current_holdings.
    Returns (tickers_list, full_payload_for_db).
    """
    holdings = payload.get("current_holdings", [])

    if isinstance(holdings, list):
        tickers = [str(t) for t in holdings]
        payload["current_holdings"] = {
            t: {"weight": 0.0, "gain_pct": 0.0, "days_held": 0}
            for t in tickers
        }
    elif isinstance(holdings, dict):
        tickers = list(holdings.keys())
    else:
        tickers = []

    return tickers, payload


async def _save_holdings(payload: dict, db: Session) -> dict:
    """Shared upsert logic for both GET and POST."""
    today = date.today()
    tickers, payload = _normalize_payload(payload)

    record = db.query(DailyHoldings).filter_by(date=today).first()
    if record:
        record.tickers = tickers
        record.payload = payload
    else:
        record = DailyHoldings(
            date=today,
            tickers=tickers,
            payload=payload,
        )
        db.add(record)

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    return {"status": "ok", "date": str(today), "tickers": tickers}


def _verify_query_token(token: str) -> None:
    """Verify API token passed as query parameter (for QC GET requests)."""
    if settings.API_TOKEN and token != settings.API_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API token",
        )


@router.post("/", response_model=HoldingsResponse)
async def submit_holdings_post(
    request: HoldingsRequest,
    _token: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """Receive holdings via POST with JSON body (standard HTTP clients)."""
    return await _save_holdings(request.model_dump(), db)


@router.get("/submit")
async def submit_holdings_get(
    data: str = Query(..., description="URL-encoded JSON payload"),
    token: str = Query("", description="API token"),
    db: Session = Depends(get_db),
):
    """Receive holdings via GET with query params (QC self.Download).

    Usage: GET /holdings/submit?data={url_encoded_json}&token={api_token}
    """
    _verify_query_token(token)

    try:
        payload = json.loads(unquote(data))
    except (json.JSONDecodeError, TypeError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON in data param: {e}")

    return await _save_holdings(payload, db)


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
