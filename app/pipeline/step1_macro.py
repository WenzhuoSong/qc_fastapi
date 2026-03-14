"""
Step 1 — Macro Regime Analysis (Structured JSON Output)

Calls LLM with real market news, economic calendar, and 5-day history
to produce a structured macro assessment. Returns a dict with parsed
fields for downstream consumption and database persistence.
"""

import asyncio
import json
from datetime import date
from typing import Dict, List, Any

from app.config import settings
from app.pipeline.prompts import MACRO_SYSTEM, MACRO_USER


MACRO_DEFAULTS: Dict[str, Any] = {
    "regime": "Neutral",
    "confidence": 50,
    "summary": "",
    "key_events": [],
    "sector_thesis": "",
    "reasoning": "",
    "raw_text": "",
}


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


def parse_macro_output(raw_text: str) -> Dict[str, Any]:
    """Extract structured JSON from Step 1 LLM output.

    Returns a dict with all expected keys, using defaults for any
    fields that couldn't be parsed.
    """
    result = {**MACRO_DEFAULTS, "raw_text": raw_text}

    i = raw_text.find("{")
    if i == -1:
        return result

    depth = 0
    for j in range(i, len(raw_text)):
        if raw_text[j] == "{":
            depth += 1
        elif raw_text[j] == "}":
            depth -= 1
            if depth == 0:
                try:
                    parsed = json.loads(raw_text[i:j + 1])
                    if isinstance(parsed, dict) and "regime" in parsed:
                        for key in MACRO_DEFAULTS:
                            if key != "raw_text" and key in parsed:
                                result[key] = parsed[key]
                        return result
                except json.JSONDecodeError:
                    pass
                break

    return result


def format_macro_context(parsed: Dict[str, Any]) -> str:
    """Format the parsed Step 1 output into a readable string for Step 2/3."""
    regime = parsed.get("regime", "Unknown")
    confidence = parsed.get("confidence", "?")
    summary = parsed.get("summary", "")
    thesis = parsed.get("sector_thesis", "")
    reasoning = parsed.get("reasoning", "")
    events = parsed.get("key_events", [])

    lines = [
        f"Regime: {regime} (Confidence: {confidence}/100)",
        f"Summary: {summary}",
    ]
    if events:
        lines.append(f"Key Events: {', '.join(str(e) for e in events)}")
    if thesis:
        lines.append(f"Sector Thesis: {thesis}")
    if reasoning:
        lines.append(f"Reasoning: {reasoning}")

    return "\n".join(lines)


async def run_macro_analysis(
    target_date: date,
    macro_news: List[dict] | None = None,
    econ_calendar: List[dict] | None = None,
    history_block: str = "",
) -> Dict[str, Any]:
    """Return a structured macro analysis grounded in real data.

    Returns a dict with keys: regime, confidence, summary, key_events,
    sector_thesis, reasoning, raw_text.
    """
    news_str = _format_news(macro_news or [])
    cal_str = _format_calendar(econ_calendar or [])
    hist_str = history_block or "(No historical context yet — first run)"

    if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY.startswith("sk-test"):
        await asyncio.sleep(1)
        return {
            "regime": "Risk-On",
            "confidence": 70,
            "summary": f"Mock macro analysis for {target_date}",
            "key_events": ["Mock CPI data", "Mock Fed meeting"],
            "sector_thesis": "Overweight Technology, underweight Utilities",
            "reasoning": "Mock mode: no real API key configured.",
            "raw_text": f"[MOCK] Macro analysis for {target_date}",
        }

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
                history_block=hist_str,
            )},
        ],
        temperature=0.3,
        max_tokens=1000,
    )
    raw_text = response.choices[0].message.content or ""
    return parse_macro_output(raw_text)
