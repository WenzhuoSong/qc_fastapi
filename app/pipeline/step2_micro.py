"""
Step 2 — Micro Sector Scoring (with Holdings + News + Earnings Flags)

Takes the macro thesis from Step 1, current holdings from QC,
real-time news from Finnhub, and earnings flags to produce
grounded ETF scores.
"""

import asyncio
from datetime import date
from typing import List, Dict

from app.config import settings
from app.pipeline.prompts import MICRO_SYSTEM, MICRO_USER


def _format_news_digest(news: Dict[str, List[dict]]) -> str:
    """Convert fetcher output into a compact string for the LLM prompt."""
    if not news:
        return "(No news data available)"

    parts = []
    for ticker, articles in news.items():
        if articles:
            lines = []
            for a in articles[:5]:
                headline = a.get("headline", "") if isinstance(a, dict) else str(a)
                summary = a.get("summary", "") if isinstance(a, dict) else ""
                lines.append(f"  - {headline}")
                if summary:
                    lines.append(f"    {summary[:150]}")
            parts.append(f"**{ticker}**:\n" + "\n".join(lines))
        else:
            parts.append(f"**{ticker}**: No recent news")

    return "\n\n".join(parts)


def _format_earnings_flags(flags: Dict[str, bool]) -> str:
    """Format earnings flags into a readable block."""
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
    news: Dict[str, List[dict]] | None = None,
    earnings_flags: Dict[str, bool] | None = None,
) -> str:
    """Score sector ETFs given macro backdrop, holdings, news, and earnings.

    macro_context is a pre-formatted string from format_macro_context().
    """
    holdings_str = ", ".join(holdings) if holdings else "(no holdings reported)"
    news_digest = _format_news_digest(news or {})
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
