"""
Step 2 — Micro Sector Scoring

Takes the macro thesis from Step 1 as context and scores individual
sector ETFs, producing raw allocation scores.
"""

import asyncio
from datetime import date

from app.config import settings
from app.pipeline.prompts import MICRO_SYSTEM, MICRO_USER


async def run_micro_scoring(target_date: date, macro_result: str) -> str:
    """Score sector ETFs given the macro backdrop.

    TODO: Replace mock with real OpenAI call once prompts are finalized.
    """
    if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY.startswith("sk-test"):
        await asyncio.sleep(1)
        return (
            f'[MOCK] Micro scores for {target_date}: '
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
            )},
        ],
        temperature=0.2,
        max_tokens=600,
    )
    return response.choices[0].message.content or ""
