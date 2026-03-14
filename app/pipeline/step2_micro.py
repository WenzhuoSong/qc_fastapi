"""
Step 2 — Micro Sector Scoring (with Holdings + News Context)

Takes the macro thesis from Step 1, current holdings from QC,
and real-time news from Finnhub to produce grounded ETF scores.
"""

import asyncio
from datetime import date
from typing import List, Dict

from app.config import settings
from app.pipeline.prompts import MICRO_SYSTEM, MICRO_USER


def _format_news_digest(news: Dict[str, List[str]]) -> str:
    """Convert fetcher output into a compact string for the LLM prompt."""
    if not news:
        return "(No news data available)"

    parts = []
    for ticker, articles in news.items():
        if articles:
            joined = "\n".join(f"  - {a[:200]}" for a in articles)
            parts.append(f"**{ticker}**:\n{joined}")
        else:
            parts.append(f"**{ticker}**: No recent news")

    return "\n\n".join(parts)


async def run_micro_scoring(
    target_date: date,
    macro_result: str,
    holdings: List[str] | None = None,
    news: Dict[str, List[str]] | None = None,
) -> str:
    """Score sector ETFs given macro backdrop, current holdings, and news.

    Falls back to mock when OPENAI_API_KEY is not configured.
    """
    holdings_str = ", ".join(holdings) if holdings else "(no holdings reported)"
    news_digest = _format_news_digest(news or {})

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
                macro_result=macro_result,
                holdings=holdings_str,
                news_digest=news_digest,
            )},
        ],
        temperature=0.2,
        max_tokens=800,
    )
    return response.choices[0].message.content or ""
