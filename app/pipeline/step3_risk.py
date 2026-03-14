"""
Step 3 — Risk Audit

Reviews the macro view + micro scores and enforces risk guardrails
(max concentration, defensive floor, etc.).
"""

import asyncio
from datetime import date

from app.config import settings
from app.pipeline.prompts import RISK_SYSTEM, RISK_USER


async def run_risk_audit(
    target_date: date,
    macro_result: str,
    micro_result: str,
) -> str:
    """Audit the proposed scores against risk constraints.

    TODO: Replace mock with real OpenAI call once prompts are finalized.
    """
    if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY.startswith("sk-test"):
        await asyncio.sleep(1)
        return (
            f"[MOCK] Risk audit for {target_date}: "
            "All checks passed. XLK capped at 40% max. "
            "Defensive floor met via XLP + XLU at 12%. No red flags."
        )

    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": RISK_SYSTEM},
            {"role": "user", "content": RISK_USER.format(
                date=target_date,
                macro_result=macro_result,
                micro_result=micro_result,
            )},
        ],
        temperature=0.1,
        max_tokens=600,
    )
    return response.choices[0].message.content or ""
