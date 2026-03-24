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

    # Phase 3b: Duration estimation
    duration_estimate: Optional[str] = Field(
        default=None,
        description="Phase 3b: Expected duration (e.g., '1-2 weeks', '1-2 months', 'indefinite')"
    )
    duration_category: Optional[str] = Field(
        default=None,
        description="Phase 3b: Duration category (short_term/medium_term/long_term)"
    )
    exit_strategy: Optional[str] = Field(
        default=None,
        description="Phase 3b: Tactical exit strategy based on duration"
    )
    tactical_implications: Optional[List[str]] = Field(
        default=None,
        description="Phase 3b: Actionable tactical recommendations"
    )

    # Phase 3c: Regime transition detection
    transition_probability: Optional[float] = Field(
        default=None,
        ge=0.0, le=1.0,
        description="Phase 3c: Probability of regime transition (0.0-1.0)"
    )
    transition_direction: Optional[str] = Field(
        default=None,
        description="Phase 3c: Expected transition direction (e.g., 'Risk-Off Peak → Fading')"
    )
    pivot_signals: Optional[List[Dict[str, str]]] = Field(
        default=None,
        description="Phase 3c: Pivot signals to monitor for transition"
    )
    confidence_trend: Optional[str] = Field(
        default=None,
        description="Phase 3c: Confidence trajectory (rising/falling/stable/volatile)"
    )
    early_warning: Optional[bool] = Field(
        default=None,
        description="Phase 3c: True if transition appears imminent"
    )
    transition_recommendation: Optional[str] = Field(
        default=None,
        description="Phase 3c: Tactical recommendation for position management"
    )

    # Phase 5b: LLM parallel analysis (stored as JSON strings for OpenAI compatibility)
    llm_contradiction_score: Optional[float] = Field(
        default=None,
        ge=0.0, le=1.0,
        description="Phase 5b: LLM-detected signal contradiction score (0=coherent, 1=contradictory)"
    )
    llm_signal_contradictions: Optional[str] = Field(
        default=None,
        description="Phase 5b: JSON string of contradictions detected by LLM"
    )
    llm_transmission_vector: Optional[str] = Field(
        default=None,
        description="Phase 5b: JSON string of LLM-generated transmission vector"
    )
    llm_confidence_adjustment: Optional[int] = Field(
        default=None,
        ge=-50, le=20,
        description="Phase 5b: LLM-recommended confidence adjustment"
    )
    llm_reasoning: Optional[str] = Field(
        default=None,
        description="Phase 5b: LLM explanation for transmission vector and adjustments"
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

    # Phase 3b fields
    duration_estimate = macro_parsed.get("duration_estimate")
    duration_category = macro_parsed.get("duration_category")
    exit_strategy = macro_parsed.get("exit_strategy")
    tactical_implications = macro_parsed.get("tactical_implications")

    # Phase 3c fields
    transition_probability = macro_parsed.get("transition_probability")
    transition_direction = macro_parsed.get("transition_direction")
    pivot_signals = macro_parsed.get("pivot_signals")
    early_warning = macro_parsed.get("early_warning")
    transition_recommendation = macro_parsed.get("transition_recommendation")

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

    # Phase 3b: Format duration estimate
    phase3b_context = ""
    if duration_estimate and exit_strategy:
        phase3b_context = f"""

                === PHASE 3b: DURATION ESTIMATE & EXIT STRATEGY ===
                EXPECTED DURATION: {duration_estimate}
                CATEGORY         : {duration_category}

                EXIT STRATEGY:
                {exit_strategy}

                TACTICAL IMPLICATIONS:
                {chr(10).join(f'  - {impl}' for impl in (tactical_implications or []))}
                ==========================================="""

    # Phase 3c: Format regime transition analysis
    phase3c_context = ""
    if transition_probability is not None:
        warning_flag = "⚠️ " if early_warning else ""
        prob_pct = int(transition_probability * 100)

        # Format pivot signals
        pivot_str = ""
        if pivot_signals:
            met_count = sum(1 for s in pivot_signals if s.get("status") == "met")
            pivot_str = f"\n                PIVOT SIGNALS: {met_count}/{len(pivot_signals)} met\n"
            for sig in pivot_signals[:4]:  # Show first 4 signals
                status_icon = "✓" if sig.get("status") == "met" else "○"
                pivot_str += f"                  {status_icon} {sig.get('signal', 'Unknown')}\n"

        phase3c_context = f"""

                === PHASE 3c: REGIME TRANSITION ANALYSIS ===
                {warning_flag}TRANSITION PROBABILITY: {prob_pct}%
                EXPECTED DIRECTION     : {transition_direction or 'No clear transition'}
                {pivot_str}
                RECOMMENDATION:
                {transition_recommendation}
                ==========================================="""

    context = f"""=== GLOBAL MACRO ENVIRONMENT ===
                MACRO REGIME  : {regime}
                CONFIDENCE    : {conf_int}/100  ({severity})
                SUMMARY       : {summary}

                KEY EVENTS (USE THESE TO TRIGGER TRANSMISSION RULES):
                {events_str}

                MACRO REASONING:
                {reasoning}{phase3a_context}{phase3b_context}{phase3c_context}
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

    # Phase 3b: Duration estimation and exit strategy
    from app.pipeline.duration_estimation import aggregate_duration_signals

    duration_analysis = aggregate_duration_signals(
        key_events=result.key_events,
        reasoning=result.reasoning,
        regime=result.regime,
    )

    # Update Step1Output with Phase 3b results
    result.duration_estimate = duration_analysis.primary_duration
    result.duration_category = duration_analysis.category
    result.exit_strategy = duration_analysis.exit_strategy
    result.tactical_implications = duration_analysis.tactical_implications

    print(f"[Phase 3b] Duration: {duration_analysis.primary_duration} ({duration_analysis.category})")
    print(f"[Phase 3b] Exit Strategy: {duration_analysis.exit_strategy[:100]}...")

    # Phase 3c: Regime transition detection
    from app.pipeline.regime_transition import (
        detect_regime_transition,
        get_confidence_history,
    )

    # Get confidence history (last 5 days)
    confidence_history = []
    if db:
        confidence_history = get_confidence_history(db, target_date, days=5)
        # Add current confidence
        confidence_history.append(result.confidence)

    # Detect regime transition
    transition_analysis = detect_regime_transition(
        regime=result.regime,
        regime_phase=result.regime_phase or "Unknown",
        net_escalation=result.net_escalation_score or 0.0,
        previous_net_escalation=previous_net_escalation,
        confidence=result.confidence,
        confidence_history=confidence_history,
        key_events=result.key_events,
    )

    # Update Step1Output with Phase 3c results
    result.transition_probability = transition_analysis.transition_probability
    result.transition_direction = transition_analysis.direction
    # Convert PivotSignal objects to dicts
    result.pivot_signals = [s.model_dump() for s in transition_analysis.pivot_signals]
    result.confidence_trend = transition_analysis.confidence_trend
    result.early_warning = transition_analysis.early_warning
    result.transition_recommendation = transition_analysis.recommendation

    print(f"[Phase 3c] Transition Probability: {transition_analysis.transition_probability:.0%}")
    if transition_analysis.direction:
        print(f"[Phase 3c] Direction: {transition_analysis.direction}")
    print(f"[Phase 3c] Confidence Trend: {transition_analysis.confidence_trend}")
    print(f"[Phase 3c] Early Warning: {transition_analysis.early_warning}")
    print(f"[Phase 3c] Pivot Signals: {len(transition_analysis.pivot_signals)} signals, "
          f"{sum(1 for s in transition_analysis.pivot_signals if s.status == 'met')} met")

    # Phase 5b: LLM parallel analysis using GPT-4o
    from app.pipeline.llm_parallel_analysis import run_llm_parallel_analysis
    from app.pipeline.confidence_guard import ConfidenceGuard

    llm_analysis = await run_llm_parallel_analysis(
        key_events=result.key_events,
        reasoning=result.reasoning,
        regime=result.regime,
        confidence=result.confidence,
    )

    # Update Step1Output with Phase 5b results
    # Store complex types as JSON strings for OpenAI structured outputs compatibility
    import json

    result.llm_contradiction_score = llm_analysis.contradiction_score.composite_score
    result.llm_signal_contradictions = json.dumps([c.model_dump() for c in llm_analysis.signal_contradictions])
    result.llm_transmission_vector = json.dumps(llm_analysis.transmission_vector_llm.sectors)
    result.llm_confidence_adjustment = llm_analysis.confidence_adjustment
    result.llm_reasoning = (
        f"Transmission: {llm_analysis.transmission_reasoning} | "
        f"Confidence: {llm_analysis.confidence_reasoning}"
    )

    print(f"[Phase 5b] LLM Parallel Analysis (GPT-4o):")
    print(f"  - Contradiction Score:")
    print(f"    • Composite: {llm_analysis.contradiction_score.composite_score:.2f} (0.7*max + 0.3*avg)")
    print(f"    • Max: {llm_analysis.contradiction_score.max_severity:.2f}")
    print(f"    • Avg: {llm_analysis.contradiction_score.average_severity:.2f}")
    print(f"  - Detected {len(llm_analysis.signal_contradictions)} signal contradictions")
    print(f"  - Confidence Adjustment: {llm_analysis.confidence_adjustment:+d}")

    if llm_analysis.signal_contradictions:
        print(f"  - Key Contradictions:")
        for contradiction in llm_analysis.signal_contradictions[:2]:  # Show first 2
            print(f"    • {contradiction.event_a} vs {contradiction.event_b}")
            print(f"      ({contradiction.contradiction_type}, severity {contradiction.severity:.2f})")

    # Apply LLM confidence adjustment with enhanced triggering logic
    # Trigger conditions:
    # 1. Base confidence < 70 (uncertain)
    # 2. Composite contradiction score >= 0.6 (high conflicts)
    # 3. Max single contradiction >= 0.75 (extreme conflict)
    apply_llm_adjustment = (
        result.confidence < 70 or
        llm_analysis.contradiction_score.composite_score >= 0.6 or
        llm_analysis.contradiction_score.max_severity >= 0.75
    )

    if apply_llm_adjustment and abs(llm_analysis.confidence_adjustment) >= 10:
        original_confidence = result.confidence

        # Apply adjustment using Confidence Guard
        final_confidence, confidence_level, action_desc = ConfidenceGuard.apply_adjustment(
            base_confidence=result.confidence,
            adjustment=llm_analysis.confidence_adjustment
        )

        result.confidence = final_confidence

        print(f"[Phase 5b] Applied LLM confidence adjustment: {original_confidence} → {final_confidence} ({llm_analysis.confidence_adjustment:+d})")
        print(f"[Phase 5b] Confidence Level: {confidence_level.value}")
        print(f"[Phase 5b] Action: {action_desc}")
        print(f"[Phase 5b] Reason: {llm_analysis.confidence_reasoning}")

    return result
