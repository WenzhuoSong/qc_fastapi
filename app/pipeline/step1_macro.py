"""
Step 1 — Macro Regime Analysis (Structured Outputs)

Calls LLM with real market news, economic calendar, and 5-day history.
Uses OpenAI Structured Outputs to guarantee valid typed output — no
manual JSON parsing. Returns a Step1Output Pydantic object.
"""

import asyncio
from datetime import date
from typing import Dict, List, Any, Literal

from pydantic import BaseModel, Field

from app.config import settings
from app.pipeline.prompts import STEP1_SYSTEM


class Step1Output(BaseModel):
    regime: Literal["Risk-On", "Neutral", "Risk-Off"]
    confidence: int = Field(ge=0, le=100)
    summary: str = Field(description="One sentence macro summary, 10-30 words")
    key_events: List[str] = Field(description="3-5 specific factual events from today's news")
    reasoning: str = Field(description="2-3 sentences explaining why this regime was chosen")


def _format_news(articles: List[dict]) -> str:
    if not articles:
        return "(No macro news available)"
    return "\n".join(
        f"- {a.get('headline', '')}"
        for a in articles[:20]
    )


def _format_calendar(events: List[dict]) -> str:
    if not events:
        return "No high-impact events today"
    return "\n".join(
        f"- {e.get('event', 'Unknown')} (impact: {e.get('impact', '')})"
        for e in events[:5]
    )


def _build_user_message(
    macro_news: List[dict],
    econ_calendar: List[dict],
    history_block: str,
) -> str:
    return (
        f"=== TODAY'S MACRO NEWS ===\n"
        f"{_format_news(macro_news)}\n\n"
        f"=== ECONOMIC CALENDAR ===\n"
        f"{_format_calendar(econ_calendar)}\n\n"
        f"=== RECENT 5-DAY CONTEXT ===\n"
        f"{history_block or 'No historical context available'}\n\n"
        f"Assess the current market regime."
    )


def format_macro_context(parsed: Dict[str, Any]) -> str:
    """Format Step 1 output into a readable string for Step 2/3 consumption.

    Accepts either a Step1Output dict or a raw dict from checkpoint resume.
    """
    regime = parsed.get("regime", "Unknown")
    confidence = parsed.get("confidence", "?")
    summary = parsed.get("summary", "")
    reasoning = parsed.get("reasoning", "")
    events = parsed.get("key_events", [])

    lines = [
        f"Regime: {regime} (Confidence: {confidence}/100)",
        f"Summary: {summary}",
    ]
    if events:
        lines.append(f"Key Events: {', '.join(str(e) for e in events)}")
    if reasoning:
        lines.append(f"Reasoning: {reasoning}")

    return "\n".join(lines)


async def run_macro_analysis(
    target_date: date,
    macro_news: List[dict] | None = None,
    econ_calendar: List[dict] | None = None,
    history_block: str = "",
) -> Step1Output:
    """Return a structured macro analysis grounded in real data.

    Returns a Step1Output Pydantic object with guaranteed valid fields.
    """
    if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY.startswith("sk-test"):
        await asyncio.sleep(1)
        return Step1Output(
            regime="Risk-On",
            confidence=70,
            summary=f"Mock macro analysis for {target_date}",
            key_events=["Mock CPI data", "Mock Fed meeting"],
            reasoning="Mock mode: no real API key configured.",
        )

    user_msg = _build_user_message(
        macro_news or [],
        econ_calendar or [],
        history_block,
    )

    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    response = await client.beta.chat.completions.parse(
        model=settings.OPENAI_MODEL_HEAVY,
        messages=[
            {"role": "system", "content": STEP1_SYSTEM},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.0,
        max_tokens=800,
        response_format=Step1Output,
    )

    result = response.choices[0].message.parsed

    if not result.summary and result.key_events:
        result.summary = f"{result.regime}: {', '.join(result.key_events[:2])}"

    return result
