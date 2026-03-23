"""
Step 1 — Macro Regime Analysis (Structured Outputs)

Calls LLM with real market news, economic calendar, and 5-day history.
Uses OpenAI Structured Outputs to guarantee valid typed output — no
manual JSON parsing. Returns a Step1Output Pydantic object.
"""

import asyncio
from datetime import date
from typing import Dict, List, Any, Literal, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.pipeline.prompts import STEP1_SYSTEM


class Step1Output(BaseModel):
    regime: Literal["Risk-On", "Neutral", "Risk-Off"]
    confidence: int = Field(ge=0, le=100)
    summary: str = Field(description="One sentence macro summary, 10-30 words")
    key_events: List[str] = Field(description="3-5 specific factual events from today's news")
    reasoning: str = Field(description="2-3 sentences explaining why this regime was chosen")
    transmission_vector: Optional[Dict[str, float]] = Field(
        default=None,
        description="Phase 2: Sector transmission vector derived from key_events"
    )

    # Phase 3a: Event direction analysis
    net_escalation_score: Optional[float] = Field(
        default=None,
        ge=-1.0, le=1.0,
        description="Phase 3a: Net escalation score from event direction analysis"
    )
    regime_phase: Optional[str] = Field(
        default=None,
        description="Phase 3a: Regime evolution phase (Building/Peak/Fading/Recovery)"
    )
    event_direction_reasoning: Optional[str] = Field(
        default=None,
        description="Phase 3a: Explanation of event direction analysis"
    )


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
    qc_quant_context: str = "",
) -> str:
    msg = (
        f"=== TODAY'S MACRO NEWS ===\n"
        f"{_format_news(macro_news)}\n\n"
        f"=== ECONOMIC CALENDAR ===\n"
        f"{_format_calendar(econ_calendar)}\n\n"
        f"=== RECENT 5-DAY CONTEXT ===\n"
        f"{history_block or 'No historical context available'}\n\n"
    )

    if qc_quant_context:
        msg += f"=== QC QUANTITATIVE INDICATORS ===\n{qc_quant_context}\n\n"

    msg += "Assess the current market regime."
    return msg


def get_qc_quantitative_context(db: Session) -> Optional[Dict[str, Any]]:
    """Extract latest QC quantitative indicators from DailyHoldings.

    Returns dict with: spy_vs_ma200, hyg_ief_ratio, breadth_pct, high_vol, portfolio_dd
    Returns None if no recent data available.
    """
    from app.db.models import DailyHoldings
    from sqlalchemy import desc

    latest = db.query(DailyHoldings).order_by(desc(DailyHoldings.date)).first()
    if not latest or not latest.payload:
        return None

    qc_detail = latest.payload.get("qc_regime_detail", {})
    if not qc_detail:
        return None

    return {
        "spy_vs_ma200": qc_detail.get("spy_vs_ma200", 1.0),
        "spy_vs_ma50": qc_detail.get("spy_vs_ma50", 1.0),
        "hyg_ief_ratio": qc_detail.get("hyg_ief_ratio", 1.0),
        "breadth_pct": qc_detail.get("breadth_pct", 0.5),
        "high_vol": qc_detail.get("high_vol", False),
        "radar_warning": qc_detail.get("radar_warning", False),
        "portfolio_dd": qc_detail.get("portfolio_dd", 0.0),
    }


def format_qc_quantitative_context(qc_data: Optional[Dict[str, Any]]) -> str:
    """Format QC quantitative indicators into prompt-friendly text."""
    if not qc_data:
        return "(No QC quantitative data available)"

    spy_ma200 = qc_data.get("spy_vs_ma200", 1.0)
    spy_ma50 = qc_data.get("spy_vs_ma50", 1.0)
    hyg_ief = qc_data.get("hyg_ief_ratio", 1.0)
    breadth = qc_data.get("breadth_pct", 0.5)
    high_vol = qc_data.get("high_vol", False)
    radar = qc_data.get("radar_warning", False)
    dd = qc_data.get("portfolio_dd", 0.0)

    # Directional indicators
    spy_direction = "above" if spy_ma200 > 1.0 else "below"
    credit_status = "risk-on" if hyg_ief > 1.05 else "risk-off" if hyg_ief < 0.95 else "neutral"
    vol_status = "elevated" if high_vol else "normal"

    lines = [
        f"- SPY vs 200MA: {spy_ma200:.2f} ({(spy_ma200-1)*100:+.1f}% {spy_direction})",
        f"- SPY vs 50MA: {spy_ma50:.2f} ({(spy_ma50-1)*100:+.1f}%)",
        f"- Credit markets: HYG/IEF = {hyg_ief:.3f} ({credit_status})",
        f"- Market breadth: {breadth:.1%} of stocks above 200MA",
        f"- Volatility: {vol_status}",
        f"- Portfolio drawdown: {dd:.1%}",
    ]

    if radar:
        lines.append("- ⚠ RADAR WARNING: Breadth or credit deterioration detected")

    return "\n".join(lines)


def format_macro_context(macro_parsed: dict) -> str:
    """
    Convert Step 1 macro JSON into a richly structured text block for Step 2.

    Goal: ensure every war/oil/crisis keyword survives into Step 2's context
    window intact, so Macro Transmission Rules fire correctly.

    Output format is designed so _extract_key_events_from_context() in
    step2_micro.py can parse the numbered event lines for the validator.

    Phase 3a: Includes event direction analysis and regime phase.
    """
    regime     = macro_parsed.get("regime", "Neutral")
    confidence = macro_parsed.get("confidence", 50)
    summary    = macro_parsed.get("summary", "No macro summary available.")
    events     = (
        macro_parsed.get("key_events")
        or macro_parsed.get("events")
        or []
    )
    reasoning  = macro_parsed.get("reasoning", "No reasoning provided.")

    # Phase 3a fields
    net_escalation = macro_parsed.get("net_escalation_score")
    regime_phase = macro_parsed.get("regime_phase")
    direction_reasoning = macro_parsed.get("event_direction_reasoning")

    # Severity label anchors Step 2's rule application strength
    try:
        conf_int = int(confidence)
    except (TypeError, ValueError):
        conf_int = 50

    if conf_int >= 80:
        severity = "HIGH -- strong conviction, apply macro rules strictly"
    elif conf_int >= 60:
        severity = "MEDIUM -- apply macro rules, allow +/-1 micro adjustment"
    else:
        severity = "LOW -- macro rules are advisory, micro news may dominate"

    # Numbered list so step2_micro._extract_key_events_from_context() can parse
    events_str = (
        "\n".join(f"  [{i+1}] {e}" for i, e in enumerate(events))
        if events else "  - None detected"
    )

    # Phase 3a: Format event direction analysis
    phase3a_context = ""
    if net_escalation is not None and regime_phase:
        escalation_label = (
            "STRONG ESCALATION" if net_escalation > 0.6 else
            "MODERATE ESCALATION" if net_escalation > 0.3 else
            "BALANCED / MIXED" if net_escalation > -0.3 else
            "DE-ESCALATION"
        )
        phase3a_context = f"""

                === PHASE 3a: EVENT DIRECTION ANALYSIS ===
                REGIME PHASE        : {regime_phase}
                NET ESCALATION SCORE: {net_escalation:.2f} ({escalation_label})
                ANALYSIS            : {direction_reasoning}

                TACTICAL IMPLICATION:
                - If "Peak" → Maintain current positioning but prepare for pivot signals
                - If "Building" → Strengthen directional positioning
                - If "Fading" → Begin reducing extreme positions
                - If "Recovery" → Consider early transition positioning
                ==========================================="""

    context = f"""=== GLOBAL MACRO ENVIRONMENT ===
                MACRO REGIME  : {regime}
                CONFIDENCE    : {conf_int}/100  ({severity})
                SUMMARY       : {summary}

                KEY EVENTS (USE THESE TO TRIGGER TRANSMISSION RULES):
                {events_str}

                MACRO REASONING:
                {reasoning}{phase3a_context}
                ================================="""

    return context


async def run_macro_analysis(
    target_date: date,
    macro_news: List[dict] | None = None,
    econ_calendar: List[dict] | None = None,
    history_block: str = "",
    db: Session | None = None,
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

    # Phase 1: Get QC quantitative indicators if available
    qc_quant = None
    if db:
        qc_quant = get_qc_quantitative_context(db)

    qc_quant_context = format_qc_quantitative_context(qc_quant)

    user_msg = _build_user_message(
        macro_news or [],
        econ_calendar or [],
        history_block,
        qc_quant_context,
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

    # Phase 2: Generate transmission vector from key_events
    from app.pipeline.transmission_rules import match_event_to_pattern

    transmission = match_event_to_pattern(
        key_events=result.key_events,
        reasoning=result.reasoning
    )
    result.transmission_vector = transmission if transmission else None

    # Phase 3a: Event direction analysis and signal contradiction handling
    from app.pipeline.event_direction import analyze_event_directions

    # Get previous day's net escalation score for trend detection
    previous_net_escalation = None
    if db:
        from app.db.models import DailyDecision
        from datetime import timedelta

        previous_date = target_date - timedelta(days=1)
        previous_decision = db.query(DailyDecision).filter_by(date=previous_date).first()

        if previous_decision and previous_decision.step1_macro_result:
            import json
            try:
                prev_data = json.loads(previous_decision.step1_macro_result)
                previous_net_escalation = prev_data.get("net_escalation_score")
            except (json.JSONDecodeError, KeyError):
                pass

    # Analyze event directions
    direction_analysis = analyze_event_directions(
        key_events=result.key_events,
        regime=result.regime,
        confidence=result.confidence,
        previous_net_escalation=previous_net_escalation,
    )

    # Update Step1Output with Phase 3a results
    result.net_escalation_score = direction_analysis.net_escalation_score
    result.regime_phase = direction_analysis.regime_phase
    result.event_direction_reasoning = direction_analysis.reasoning

    # Apply confidence adjustment from signal contradictions
    if direction_analysis.confidence_adjustment != 0:
        original_confidence = result.confidence
        result.confidence = max(0, min(100, result.confidence + direction_analysis.confidence_adjustment))
        print(f"[Phase 3a] Confidence adjusted: {original_confidence} → {result.confidence} ({direction_analysis.confidence_adjustment:+d})")

    return result
