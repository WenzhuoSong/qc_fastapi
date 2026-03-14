"""
Data Fetcher — Finnhub Market Data Integration

Two layers of data:
  1. Macro:  general market news + economic calendar   → feeds Step 1
  2. Micro:  per-ticker company news + earnings flags  → feeds Step 2

All calls use sync httpx (already in deps) with timeouts and graceful
error handling so a single API failure never crashes the pipeline.
"""

from datetime import datetime, timedelta
from typing import Dict, List

import httpx

from app.config import settings

_BASE = "https://finnhub.io/api/v1"
_TIMEOUT = 10


def _token() -> str:
    return settings.FINNHUB_API_KEY


# ═══════════════════════════════════════════════════════════════
# Macro data (Step 1)
# ═══════════════════════════════════════════════════════════════

def fetch_macro_news(limit: int = 20) -> List[dict]:
    """Fetch latest general market news (past ~24 h)."""
    if not _token():
        return []
    try:
        resp = httpx.get(
            f"{_BASE}/news",
            params={"category": "general", "token": _token()},
            timeout=_TIMEOUT,
        )
        items = resp.json()[:limit]
        return [
            {
                "headline": it.get("headline", ""),
                "summary": it.get("summary", ""),
                "source": it.get("source", ""),
            }
            for it in items
        ]
    except Exception as e:
        print(f"[DataFetcher] macro news error: {e}")
        return []


def fetch_economic_calendar(days_ahead: int = 3) -> List[dict]:
    """Fetch upcoming high-impact economic events (Fed, CPI, NFP, etc.)."""
    if not _token():
        return []
    today = datetime.utcnow().date()
    end = today + timedelta(days=days_ahead)
    try:
        resp = httpx.get(
            f"{_BASE}/calendar/economic",
            params={"from": str(today), "to": str(end), "token": _token()},
            timeout=_TIMEOUT,
        )
        events = resp.json().get("economicCalendar", [])
        high = [e for e in events if e.get("impact") == "high"]
        if not high:
            high = events[:5]
        return high[:10]
    except Exception as e:
        print(f"[DataFetcher] econ calendar error: {e}")
        return []


# ═══════════════════════════════════════════════════════════════
# Micro data (Step 2)
# ═══════════════════════════════════════════════════════════════

def fetch_ticker_news(ticker: str, days_back: int = 2, limit: int = 10) -> List[dict]:
    """Fetch recent company news for a single ticker."""
    if not _token():
        return []
    today = datetime.utcnow().date()
    start = today - timedelta(days=days_back)
    try:
        resp = httpx.get(
            f"{_BASE}/company-news",
            params={
                "symbol": ticker,
                "from": str(start),
                "to": str(today),
                "token": _token(),
            },
            timeout=_TIMEOUT,
        )
        items = resp.json()[:limit]
        return [
            {
                "headline": it.get("headline", ""),
                "summary": it.get("summary", ""),
                "source": it.get("source", ""),
            }
            for it in items
        ]
    except Exception as e:
        print(f"[DataFetcher] {ticker} news error: {e}")
        return []


def fetch_all_holdings_news(tickers: List[str]) -> Dict[str, List[dict]]:
    """Batch-fetch news for every holding. Returns {ticker: [articles]}."""
    return {t: fetch_ticker_news(t) for t in tickers}


# ═══════════════════════════════════════════════════════════════
# Hard risk scanning (factual event detection)
# ═══════════════════════════════════════════════════════════════

_HARD_RISK_PATTERNS: Dict[str, List[str]] = {
    "earnings_soon": ["earnings", "quarterly results", "revenue report", "eps"],
    "fda_pending": ["fda approval", "fda decision", "fda review", "drug approval"],
    "trading_halted": ["trading halt", "halted trading", "suspended trading"],
    "acquisition_target": [
        "acquisition", "merger", "takeover", "buyout",
        "takeover bid", "merger agreement",
    ],
    "major_lawsuit": ["lawsuit", "class action", "sec investigation", "fraud"],
}


def scan_hard_risks(
    ticker: str, news: List[dict], has_earnings: bool
) -> Dict[str, str]:
    """Scan a ticker's news for hard risk events that warrant automatic action.

    Returns {risk_type: reason} for each detected risk. Empty dict = clean.
    These are factual event detections, not predictions — high confidence.
    """
    risks: Dict[str, str] = {}

    if has_earnings:
        risks["earnings_soon"] = "Earnings report within 7 days"

    combined_text = " ".join(
        (a.get("headline", "") + " " + a.get("summary", "")).lower()
        for a in news
    )

    for risk_type, keywords in _HARD_RISK_PATTERNS.items():
        if risk_type == "earnings_soon":
            continue
        for kw in keywords:
            if kw in combined_text:
                risks[risk_type] = f"Detected keyword '{kw}' in recent news"
                break

    return risks


def scan_all_holdings_risks(
    tickers: List[str],
    news: Dict[str, List[dict]],
    earnings_flags: Dict[str, bool],
) -> Dict[str, Dict[str, str]]:
    """Batch-scan all holdings for hard risks. Returns {ticker: {risk_type: reason}}."""
    return {
        t: scan_hard_risks(t, news.get(t, []), earnings_flags.get(t, False))
        for t in tickers
    }


def fetch_earnings_flag(ticker: str, days_ahead: int = 7) -> bool:
    """Check if a ticker has an earnings event within N days.

    Upcoming earnings = high-risk event → avoid new positions.
    """
    if not _token():
        return False
    today = datetime.utcnow().date()
    end = today + timedelta(days=days_ahead)
    try:
        resp = httpx.get(
            f"{_BASE}/calendar/earnings",
            params={
                "from": str(today),
                "to": str(end),
                "symbol": ticker,
                "token": _token(),
            },
            timeout=_TIMEOUT,
        )
        items = resp.json().get("earningsCalendar", [])
        return len(items) > 0
    except Exception:
        return False
