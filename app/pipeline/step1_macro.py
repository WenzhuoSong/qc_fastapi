"""
Step 1 — Macro Regime Analysis

Calls LLM to assess the current macro environment and produce a
directional thesis that downstream steps depend on.
"""

import asyncio
from datetime import date

from app.config import settings
from app.pipeline.prompts import MACRO_SYSTEM, MACRO_USER


async def run_macro_analysis(target_date: date) -> str:
    """Return a macro analysis essay for the given date.

    TODO: Replace mock with real OpenAI call once prompts are finalized.
    """
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
            {"role": "user", "content": MACRO_USER.format(date=target_date)},
        ],
        temperature=0.3,
        max_tokens=800,
    )
    return response.choices[0].message.content or ""
