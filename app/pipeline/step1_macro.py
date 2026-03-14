"""
Step 1 — Macro Regime Analysis

Calls LLM with real market news + economic calendar to produce a
directional thesis that downstream steps depend on.
"""

import asyncio
from datetime import date
from typing import List

from app.config import settings
from app.pipeline.prompts import MACRO_SYSTEM, MACRO_USER


def _format_news(articles: List[dict]) -> str:
    if not articles:
        return "(No macro news available)"
    lines = []
    for a in articles[:15]:
        headline = a.get("headline", "")
        summary = a.get("summary", "")
        source = a.get("source", "")
        lines.append(f"- [{source}] {headline}")
        if summary:
            lines.append(f"  {summary[:200]}")
    return "\n".join(lines)


def _format_calendar(events: List[dict]) -> str:
    if not events:
        return "(No high-impact events in the next 3 days)"
    lines = []
    for e in events:
        event_name = e.get("event", "Unknown")
        country = e.get("country", "")
        impact = e.get("impact", "")
        lines.append(f"- [{country}] {event_name} (impact: {impact})")
    return "\n".join(lines)


async def run_macro_analysis(
    target_date: date,
    macro_news: List[dict] | None = None,
    econ_calendar: List[dict] | None = None,
) -> str:
    """Return a macro analysis grounded in real news and economic events."""
    news_str = _format_news(macro_news or [])
    cal_str = _format_calendar(econ_calendar or [])

    if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY.startswith("sk-test"):
        await asyncio.sleep(1)
        return (
            f"[MOCK] Macro analysis for {target_date}: "
            "Risk-on regime. Overweight Technology and Financials. "
            "Underweight Utilities and Real Estate. "
            "Key risk: upcoming CPI print may surprise to the upside."
        )

    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": MACRO_SYSTEM},
            {"role": "user", "content": MACRO_USER.format(
                date=target_date,
                macro_news=news_str,
                econ_calendar=cal_str,
            )},
        ],
        temperature=0.3,
        max_tokens=1000,
    )
    return response.choices[0].message.content or ""
