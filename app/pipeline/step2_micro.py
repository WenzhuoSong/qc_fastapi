"""
Step 2 — Micro Sector Scoring (with Holdings + Pre-Fetched News + Earnings)

Takes the macro thesis from Step 1, current holdings from QC,
pre-fetched news summaries from ticker_news_library, and earnings
flags to produce grounded ETF scores.
"""

import asyncio
from datetime import date, timedelta
from typing import List, Dict, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.pipeline.prompts import MICRO_SYSTEM, MICRO_USER


def build_news_context_from_db(
    db: Session, tickers: List[str], target_date: date
) -> str:
    """Read pre-fetched news from ticker_news_library and format for LLM."""
    from app.db.models import TickerNewsLibrary

    cutoff = target_date - timedelta(days=2)
    parts = []

    for ticker in tickers:
        rows = (
            db.query(TickerNewsLibrary)
            .filter(
                TickerNewsLibrary.ticker == ticker,
                TickerNewsLibrary.date >= cutoff,
            )
            .order_by(TickerNewsLibrary.date.desc())
            .limit(5)
            .all()
        )

        if not rows:
            parts.append(f"**{ticker}**: No recent news")
            continue

        hard_events = [r for r in rows if r.is_hard_event]
        lines = []
        for r in rows:
            sentiment_tag = f"[{r.sentiment}]" if r.sentiment else ""
            summary = r.llm_summary or r.headline[:80]
            lines.append(f"  - {sentiment_tag} {summary}")

        block = f"**{ticker}**:\n" + "\n".join(lines)
        if hard_events:
            block += f"\n  ⚠ HARD EVENT: {hard_events[0].llm_summary}"
        parts.append(block)

    return "\n\n".join(parts) if parts else "(No news data available)"


def build_hard_flags_from_db(
    db: Session, tickers: List[str], target_date: date
) -> Dict[str, List[str]]:
    """Extract hard risk flags from ticker_news_library for allocation response."""
    from app.db.models import TickerNewsLibrary

    cutoff = target_date - timedelta(days=2)
    flags: Dict[str, List[str]] = {}

    for ticker in tickers:
        hard_rows = (
            db.query(TickerNewsLibrary)
            .filter(
                TickerNewsLibrary.ticker == ticker,
                TickerNewsLibrary.date >= cutoff,
                TickerNewsLibrary.is_hard_event.is_(True),
            )
            .all()
        )
        if hard_rows:
            flags[ticker] = [r.llm_summary or r.headline[:60] for r in hard_rows]

    return flags


def _format_earnings_flags(flags: Dict[str, bool]) -> str:
    if not flags:
        return "(No earnings data available)"

    upcoming = [t for t, has in flags.items() if has]
    clear = [t for t, has in flags.items() if not has]

    lines = []
    if upcoming:
        lines.append(f"UPCOMING EARNINGS (high risk): {', '.join(upcoming)}")
    if clear:
        lines.append(f"No earnings soon: {', '.join(clear)}")
    return "\n".join(lines)


async def run_micro_scoring(
    target_date: date,
    macro_context: str,
    holdings: List[str] | None = None,
    news_digest: str = "(No news data available)",
    earnings_flags: Dict[str, bool] | None = None,
) -> str:
    """Score sector ETFs given macro backdrop, holdings, news, and earnings.

    news_digest is a pre-built string from build_news_context_from_db().
    """
    holdings_str = ", ".join(holdings) if holdings else "(no holdings reported)"
    earnings_str = _format_earnings_flags(earnings_flags or {})

    if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY.startswith("sk-test"):
        await asyncio.sleep(1)
        return (
            f'[MOCK] Micro scores for {target_date} '
            f'(holdings: {holdings_str}): '
            '{"XLK": 9, "XLF": 7, "XLV": 5, "XLE": 4, "XLI": 6, '
            '"XLP": 3, "XLU": 2, "XLY": 6, "XLC": 7, "XLRE": 2, "XLB": 4}'
        )

    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": MICRO_SYSTEM},
            {"role": "user", "content": MICRO_USER.format(
                date=target_date,
                macro_context=macro_context,
                holdings=holdings_str,
                news_digest=news_digest,
                earnings_flags=earnings_str,
            )},
        ],
        temperature=0.2,
        max_tokens=800,
    )
    return response.choices[0].message.content or ""
