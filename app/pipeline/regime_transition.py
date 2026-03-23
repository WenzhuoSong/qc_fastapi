"""
Phase 3c: Regime Transition Detection & Pivot Signal Generation

Detects regime transitions by analyzing trends in escalation, confidence,
and market indicators. Provides early warning signals for regime changes.

Key concepts:
- Transition detection: Identifies when regime is changing (Peak → Fading → Recovery)
- Pivot signals: Actionable indicators to watch (oil stabilization, credit spreads, VIX)
- Confidence trends: Tracks confidence over 5 days to detect deterioration/improvement
- Transition probability: Estimates likelihood of regime change in next 1-2 weeks

Example:
    Current: Risk-Off Peak (net_escalation=0.46, declining)
    Pivot Signals: 2/4 met (oil stabilizing, G7 convoy active)
    Transition Probability: 25% (prepare for Fading phase)
    Recommendation: Maintain Risk-Off but prepare to reduce extreme positions
"""

from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from datetime import date, timedelta


class PivotSignal(BaseModel):
    """Single pivot signal indicating potential regime transition.

    Attributes:
        signal: Description of the signal (e.g., "Oil price < $95")
        status: Current status (met/pending/unknown)
        current_value: Current observed value (optional)
    """
    signal: str
    status: str  # "met", "pending", "unknown"
    current_value: Optional[str] = None


class TransitionAnalysis(BaseModel):
    """Complete regime transition analysis with pivot signals.

    Attributes:
        transition_probability: Probability of regime change (0.0-1.0)
        direction: Expected direction if transition occurs
        pivot_signals: List of signals to monitor
        confidence_trend: Recent confidence trajectory
        early_warning: Whether early warning is triggered
        recommendation: Tactical guidance for position management
    """
    transition_probability: float = Field(ge=0.0, le=1.0)
    direction: Optional[str] = Field(
        default=None,
        description="Expected transition direction (e.g., 'Risk-Off → Neutral', 'Peak → Fading')"
    )
    pivot_signals: List[PivotSignal] = Field(default_factory=list)
    confidence_trend: str = Field(
        description="Confidence trajectory (e.g., 'stable', 'rising', 'falling')"
    )
    early_warning: bool = Field(
        default=False,
        description="True if transition appears imminent (within 1-2 weeks)"
    )
    recommendation: str = Field(
        description="Tactical recommendation for position management"
    )


# ═══════════════════════════════════════════════════════════════
# Pivot Signal Definitions
# ═══════════════════════════════════════════════════════════════

def generate_pivot_signals(
    regime: str,
    net_escalation: float,
    regime_phase: str,
    key_events: List[str],
) -> List[PivotSignal]:
    """Generate pivot signals based on current regime and events.

    Args:
        regime: Current regime (Risk-On, Neutral, Risk-Off)
        net_escalation: Net escalation score
        regime_phase: Current regime phase
        key_events: Key events from Step 1

    Returns:
        List of pivot signals to monitor for transition
    """
    signals = []

    # Risk-Off pivot signals (conditions for exit)
    if regime == "Risk-Off":
        # Oil-related signals
        if any("oil" in e.lower() or "energy" in e.lower() for e in key_events):
            signals.append(PivotSignal(
                signal="Oil price stabilizes below $95",
                status="pending",
                current_value="Unknown (check live data)"
            ))

        # Geopolitical signals
        if any("iran" in e.lower() or "war" in e.lower() or "conflict" in e.lower() for e in key_events):
            signals.append(PivotSignal(
                signal="Geopolitical tensions ease (ceasefire, diplomatic progress)",
                status="pending",
                current_value="Monitor news flow"
            ))

            # Check for de-escalation signals in events
            deescalation_keywords = ["cease", "truce", "backs security", "stabilization", "resume"]
            if any(kw in e.lower() for e in key_events for kw in deescalation_keywords):
                signals[-1].status = "met"
                signals[-1].current_value = "De-escalation signals detected in news"

        # Credit market signals
        signals.append(PivotSignal(
            signal="Credit spreads normalize (HYG/IEF > 0.95)",
            status="unknown",
            current_value="Check QC quantitative indicators"
        ))

        # Volatility signals
        signals.append(PivotSignal(
            signal="VIX normalizes below 25",
            status="unknown",
            current_value="Check QC quantitative indicators"
        ))

        # Regime phase-specific signals
        if "Peak" in regime_phase or "Fading" in regime_phase:
            signals.append(PivotSignal(
                signal="Net escalation continues declining (trend confirmation)",
                status="pending",
                current_value=f"Current: {net_escalation:.2f} (monitor next day)"
            ))

    # Risk-On pivot signals (conditions for exit)
    elif regime == "Risk-On":
        # Credit stress signals
        signals.append(PivotSignal(
            signal="Credit spreads widen (HYG/IEF < 0.95)",
            status="unknown",
            current_value="Check QC quantitative indicators"
        ))

        # Volatility spike
        signals.append(PivotSignal(
            signal="VIX spikes above 25",
            status="unknown",
            current_value="Check QC quantitative indicators"
        ))

        # Escalation emergence
        if net_escalation > 0.3:
            signals.append(PivotSignal(
                signal="Escalation signals emerging",
                status="met",
                current_value=f"Net escalation: {net_escalation:.2f} (> 0.3 threshold)"
            ))

    # Neutral pivot signals (conditions for directional move)
    else:  # Neutral
        if net_escalation > 0.4:
            signals.append(PivotSignal(
                signal="Escalation threshold breached → Risk-Off transition",
                status="met",
                current_value=f"Net escalation: {net_escalation:.2f}"
            ))
        elif net_escalation < -0.3:
            signals.append(PivotSignal(
                signal="De-escalation dominant → Risk-On transition",
                status="met",
                current_value=f"Net escalation: {net_escalation:.2f}"
            ))
        else:
            signals.append(PivotSignal(
                signal="Await directional signal (net escalation still mixed)",
                status="pending",
                current_value=f"Net escalation: {net_escalation:.2f}"
            ))

    return signals


# ═══════════════════════════════════════════════════════════════
# Confidence Trend Analysis
# ═══════════════════════════════════════════════════════════════

def analyze_confidence_trend(confidence_history: List[int]) -> str:
    """Analyze confidence trajectory over recent days.

    Args:
        confidence_history: List of confidence values (most recent last)

    Returns:
        Trend description: "rising", "falling", "stable", "volatile"
    """
    if len(confidence_history) < 2:
        return "insufficient_data"

    if len(confidence_history) < 3:
        # Only 2 days: simple comparison
        if confidence_history[-1] > confidence_history[-2] + 5:
            return "rising"
        elif confidence_history[-1] < confidence_history[-2] - 5:
            return "falling"
        else:
            return "stable"

    # 3+ days: more sophisticated analysis
    recent_3 = confidence_history[-3:]

    # Check for consistent trend
    if all(recent_3[i] < recent_3[i+1] - 3 for i in range(len(recent_3)-1)):
        return "rising"
    elif all(recent_3[i] > recent_3[i+1] + 3 for i in range(len(recent_3)-1)):
        return "falling"

    # Check for volatility
    changes = [abs(recent_3[i+1] - recent_3[i]) for i in range(len(recent_3)-1)]
    if max(changes) > 15:
        return "volatile"

    # Otherwise stable
    return "stable"


# ═══════════════════════════════════════════════════════════════
# Transition Detection Logic
# ═══════════════════════════════════════════════════════════════

def detect_regime_transition(
    regime: str,
    regime_phase: str,
    net_escalation: float,
    previous_net_escalation: Optional[float],
    confidence: int,
    confidence_history: List[int],
    key_events: List[str],
) -> TransitionAnalysis:
    """Detect potential regime transitions and generate pivot signals.

    Args:
        regime: Current regime (Risk-On, Neutral, Risk-Off)
        regime_phase: Current regime phase (e.g., "Risk-Off Peak")
        net_escalation: Current net escalation score
        previous_net_escalation: Previous day's net escalation (if available)
        confidence: Current confidence level
        confidence_history: Confidence values from last 5 days
        key_events: Key events from Step 1

    Returns:
        TransitionAnalysis with probability, signals, and recommendations
    """
    # Generate pivot signals
    pivot_signals = generate_pivot_signals(regime, net_escalation, regime_phase, key_events)

    # Analyze confidence trend
    confidence_trend = analyze_confidence_trend(confidence_history)

    # Calculate transition probability
    transition_prob = 0.0
    direction = None
    early_warning = False
    recommendation = ""

    # Risk-Off transition logic
    if regime == "Risk-Off":
        # Count met pivot signals
        met_signals = sum(1 for s in pivot_signals if s.status == "met")
        total_signals = len(pivot_signals)

        if total_signals > 0:
            signal_ratio = met_signals / total_signals

            # Peak → Fading transition
            if "Peak" in regime_phase:
                # High probability if 2+ signals met and escalation declining
                if met_signals >= 2 and previous_net_escalation and net_escalation < previous_net_escalation:
                    transition_prob = 0.40
                    direction = "Risk-Off Peak → Fading"
                    early_warning = True
                    recommendation = (
                        "Transition to Fading phase likely. Begin preparing exit strategy. "
                        "Start taking profits on defensive positions at +10-12%. "
                        "Monitor for additional pivot signals before full rotation."
                    )
                elif met_signals >= 1:
                    transition_prob = 0.25
                    direction = "Risk-Off Peak → Fading"
                    recommendation = (
                        "First pivot signals appearing. Maintain current positions but tighten stops. "
                        "Prepare to reduce extreme defensive positions if more signals flip."
                    )
                else:
                    transition_prob = 0.10
                    recommendation = (
                        "Peak phase continues. Maintain defensive positioning. "
                        "Watch for de-escalation signals or oil stabilization."
                    )

            # Fading → Recovery transition
            elif "Fading" in regime_phase:
                if met_signals >= 2:
                    transition_prob = 0.50
                    direction = "Risk-Off Fading → Recovery"
                    early_warning = True
                    recommendation = (
                        "Transition to Recovery phase imminent. Begin rotating out of defensives. "
                        "Take profits on XLP/XLU/XLV at current levels (+8-10%). "
                        "Prepare to increase cyclical exposure (XLY/XLK) on confirmation."
                    )
                else:
                    transition_prob = 0.30
                    direction = "Risk-Off Fading → Recovery"
                    recommendation = (
                        "Fading phase continues but recovery signals emerging. "
                        "Hold defensive positions but prepare rotation strategy. "
                        "Watch for credit spread normalization."
                    )

            # Building/Active → Peak transition (backwards direction, confidence falling)
            elif "Building" in regime_phase or "Active" in regime_phase:
                if confidence_trend == "falling" and previous_net_escalation and net_escalation < previous_net_escalation:
                    transition_prob = 0.35
                    direction = "Risk-Off Building → Peak (deceleration detected)"
                    recommendation = (
                        "Escalation decelerating. Approaching peak. "
                        "Maintain current defensive positions. "
                        "Prepare for potential pivot in 1-2 weeks."
                    )
                else:
                    transition_prob = 0.05
                    recommendation = (
                        "Risk-Off continues building. Strengthen defensive positions. "
                        "No immediate transition expected."
                    )

        # Confidence trend overlay
        if confidence_trend == "falling" and confidence < 50:
            transition_prob = min(1.0, transition_prob + 0.15)
            recommendation += " Note: Falling confidence increases transition uncertainty."

    # Risk-On transition logic
    elif regime == "Risk-On":
        # Check for escalation emergence
        if net_escalation > 0.3:
            met_signals = sum(1 for s in pivot_signals if s.status == "met")
            transition_prob = 0.25 + (met_signals * 0.15)
            direction = "Risk-On → Neutral (escalation emerging)"
            early_warning = met_signals >= 2
            recommendation = (
                "Escalation signals emerging. Consider reducing growth overweight. "
                "Monitor for further risk-off signals before full rotation."
            )
        else:
            transition_prob = 0.05
            recommendation = "Risk-On environment stable. Maintain growth positioning."

    # Neutral transition logic
    else:  # Neutral
        if net_escalation > 0.4:
            transition_prob = 0.40
            direction = "Neutral → Risk-Off"
            early_warning = True
            recommendation = (
                "Clear Risk-Off signals. Rotate to defensive positioning. "
                "Reduce XLK/XLY/XLC, increase XLP/XLU/XLV."
            )
        elif net_escalation < -0.3:
            transition_prob = 0.40
            direction = "Neutral → Risk-On"
            early_warning = True
            recommendation = (
                "Clear Risk-On signals. Rotate to growth positioning. "
                "Increase XLK/XLY/XLC, reduce defensives."
            )
        else:
            transition_prob = 0.10
            recommendation = "Neutral range-bound. Maintain balanced allocation."

    return TransitionAnalysis(
        transition_probability=min(1.0, transition_prob),
        direction=direction,
        pivot_signals=pivot_signals,
        confidence_trend=confidence_trend,
        early_warning=early_warning,
        recommendation=recommendation,
    )


# ═══════════════════════════════════════════════════════════════
# Database Helper Functions
# ═══════════════════════════════════════════════════════════════

def get_confidence_history(db, target_date: date, days: int = 5) -> List[int]:
    """Retrieve confidence history from database.

    Args:
        db: Database session
        target_date: Current date
        days: Number of historical days to retrieve

    Returns:
        List of confidence values (oldest to newest)
    """
    from app.db.models import DailyDecision
    import json

    history = []
    for i in range(days, 0, -1):
        check_date = target_date - timedelta(days=i)
        row = db.query(DailyDecision).filter_by(date=check_date).first()
        if row and row.step1_macro_result:
            try:
                data = json.loads(row.step1_macro_result)
                confidence = data.get("confidence")
                if confidence is not None:
                    history.append(int(confidence))
            except (json.JSONDecodeError, KeyError, TypeError):
                continue

    return history
