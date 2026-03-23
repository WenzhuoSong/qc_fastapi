"""
Phase 3a: Event Direction Analysis & Signal Contradiction Handling

This module classifies macro events into escalation/de-escalation/neutral
directions and calculates net escalation scores to detect signal contradictions.

Key concepts:
- Escalation events: war, attack, crisis deepens, sanctions
- De-escalation events: ceasefire, dialogue, stabilization, backs security
- Net escalation score: weighted sum in range [-1.0, 1.0]
- Regime phase: Building, Peak, Fading, Recovery

Example:
    2026-03-20: 4 escalation events (weight=0.8 avg) + 1 de-escalation (weight=0.3)
    → Net escalation = (4*0.8 - 1*0.3) / 5 = 0.58 (still escalating but decelerating)
    → Regime phase = "Risk-Off Peak (first signs of deceleration)"
"""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field


# Event direction classification
EventDirection = Literal["escalation", "de-escalation", "neutral"]


class EventWithDirection(BaseModel):
    """Single event with direction and weight.

    Attributes:
        event: Original event description (e.g., "Iran threatens oil blockade")
        direction: Classification (escalation/de-escalation/neutral)
        weight: Impact strength [0.0, 1.0], higher = more significant
    """
    event: str
    direction: EventDirection
    weight: float = Field(ge=0.0, le=1.0, default=0.5)


class EventDirectionAnalysis(BaseModel):
    """Complete event direction analysis output.

    This extends Step1Output with direction-aware fields for Phase 3a.
    """
    key_events_tagged: List[EventWithDirection]
    net_escalation_score: float = Field(
        ge=-1.0, le=1.0,
        description="Net escalation score: +1.0 = full escalation, -1.0 = full de-escalation, 0.0 = balanced"
    )
    regime_phase: Optional[str] = Field(
        default=None,
        description="Regime evolution phase: Building, Peak, Fading, Recovery"
    )
    confidence_adjustment: int = Field(
        default=0,
        description="Confidence adjustment based on signal contradictions (-20 to +10)"
    )
    reasoning: str = Field(
        description="Explanation of direction classification and phase detection"
    )


# ═══════════════════════════════════════════════════════════════
# Direction Classification Keywords
# ═══════════════════════════════════════════════════════════════

ESCALATION_KEYWORDS = [
    # Military action
    "attack", "strike", "bombing", "missile", "drone strike", "invasion",
    "escalate", "escalation", "escalating", "military action", "war", "conflict",
    "deployed", "deployment", "submarine deployed",

    # Crisis deepening
    "crisis deepens", "worsens", "deteriorates", "beyond control",
    "out of control", "spiraling", "intensifies", "threatens",

    # Supply disruption
    "blockade", "embargo", "closure", "halt", "suspend", "cut off",
    "supply disruption", "shortage", "disruption",

    # Sanctions & retaliation
    "sanctions", "expel diplomats", "expels", "retaliates", "retaliation",
    "counter-attack", "response strike", "vows revenge",

    # Diplomatic breakdown
    "talks collapse", "negotiations fail", "withdraw diplomats",
    "break ties", "ultimatum", "deadline expires",
]

DE_ESCALATION_KEYWORDS = [
    # Diplomatic progress
    "ceasefire", "truce", "peace talks", "dialogue", "negotiations",
    "diplomatic breakthrough", "agreement", "treaty", "accord",

    # Stabilization efforts
    "stabilization", "backs security", "backs safety", "backs maritime",
    "G7 backs", "g7 backs", "international support", "coalition forms",
    "peacekeeping", "convoy plan", "security convoy",

    # Service restoration
    "exports resume", "resumes", "restarts", "restores", "reopens",
    "normalizes", "flows resume", "operations restart", "after halt",

    # De-escalation signals
    "de-escalate", "cooling", "tensions ease", "calm", "pullback",
    "withdraw forces", "stands down", "reduces presence",

    # Emergency response
    "emergency convoy", "humanitarian corridor", "safe passage",
    "protection measures", "security guarantee",
]

NEUTRAL_KEYWORDS = [
    # Monitoring/assessment
    "monitor", "assess", "evaluate", "watch", "track",

    # Statements without action
    "says", "claims", "reports", "states", "announces",

    # Market reactions (descriptive, not causal)
    "prices react", "markets respond", "volatility rises",
]


# ═══════════════════════════════════════════════════════════════
# Core Functions
# ═══════════════════════════════════════════════════════════════

def classify_event_direction(event: str) -> tuple[EventDirection, float]:
    """Classify a single event into escalation/de-escalation/neutral.

    Args:
        event: Event description string

    Returns:
        (direction, weight) tuple
        - direction: "escalation", "de-escalation", or "neutral"
        - weight: 0.0-1.0, higher for more significant events

    Strategy:
        1. Check for strong de-escalation phrases first (resume, backs security)
        2. Check escalation keywords
        3. Check remaining de-escalation keywords
        4. Default to neutral if no strong match
        5. Weight based on keyword strength and event phrasing
    """
    event_lower = event.lower()

    # Priority check: Strong de-escalation phrases that should override escalation keywords
    strong_deescalation_phrases = [
        "resume", "resumes", "backs security", "backs maritime",
        "ceasefire", "peace talks", "g7 backs", "convoy plan"
    ]
    if any(phrase in event_lower for phrase in strong_deescalation_phrases):
        # This is de-escalation even if escalation keywords present
        if any(kw in event_lower for kw in ["ceasefire", "peace talks", "agreement"]):
            weight = 0.6
        elif any(kw in event_lower for kw in ["resume", "backs security", "backs maritime"]):
            weight = 0.5
        else:
            weight = 0.4
        return "de-escalation", weight

    # Count keyword matches for remaining cases
    escalation_matches = sum(1 for kw in ESCALATION_KEYWORDS if kw in event_lower)
    deescalation_matches = sum(1 for kw in DE_ESCALATION_KEYWORDS if kw in event_lower)

    # Classify based on dominant signal
    if escalation_matches > deescalation_matches:
        direction = "escalation"
        # Weight: 0.8 for strong keywords (attack, war), 0.6 for medium (threatens)
        if any(kw in event_lower for kw in ["attack", "bombing", "invasion", "war", "beyond control"]):
            weight = 0.8
        elif any(kw in event_lower for kw in ["escalate", "escalating", "threatens", "crisis deepens"]):
            weight = 0.7
        else:
            weight = 0.6

    elif deescalation_matches > escalation_matches:
        direction = "de-escalation"
        # Weight: 0.7 for strong (ceasefire), 0.4 for weak (monitoring)
        if any(kw in event_lower for kw in ["ceasefire", "peace talks", "agreement"]):
            weight = 0.6
        elif any(kw in event_lower for kw in ["backs security", "stabilization", "emergency convoy"]):
            weight = 0.5
        else:
            weight = 0.4

    else:
        direction = "neutral"
        weight = 0.3

    return direction, weight


def calculate_net_escalation(events: List[EventWithDirection]) -> float:
    """Calculate net escalation score from tagged events.

    Args:
        events: List of events with direction and weight

    Returns:
        Net escalation score in [-1.0, 1.0]
        - +1.0: Pure escalation (all events are escalation with high weight)
        - 0.0: Balanced or neutral
        - -1.0: Pure de-escalation

    Formula:
        score = sum(weight * direction_multiplier) / len(events)
        where direction_multiplier: escalation=+1, de-escalation=-1, neutral=0
    """
    if not events:
        return 0.0

    total_score = 0.0
    for event in events:
        if event.direction == "escalation":
            total_score += event.weight
        elif event.direction == "de-escalation":
            total_score -= event.weight
        # neutral contributes 0

    # Normalize by number of events to keep in [-1.0, 1.0] range
    net_score = total_score / len(events)

    # Clamp to valid range
    return max(-1.0, min(1.0, net_score))


def detect_regime_phase(
    current_events: List[EventWithDirection],
    confidence: int,
    regime: str,
    previous_net_escalation: Optional[float] = None,
) -> str:
    """Detect regime evolution phase based on current and historical signals.

    Args:
        current_events: Tagged events for current day
        confidence: Current confidence level (0-100)
        regime: Current regime (Risk-On, Neutral, Risk-Off)
        previous_net_escalation: Net escalation score from previous day (if available)

    Returns:
        Regime phase string describing evolution stage

    Phases:
        - "Risk-Off Building": Escalation accelerating, confidence rising
        - "Risk-Off Peak (first signs of deceleration)": High escalation but decelerating
        - "Risk-Off Fading": Escalation declining significantly
        - "Recovery Phase": De-escalation dominant
        - "Risk-On Active": Risk-on regime with no deceleration
        - "Neutral Balanced": No clear trend
    """
    current_net = calculate_net_escalation(current_events)

    # Risk-Off phases
    if regime == "Risk-Off":
        # Check for deceleration first (applies to all escalation levels)
        if previous_net_escalation is not None and current_net < previous_net_escalation:
            deceleration_magnitude = previous_net_escalation - current_net

            # High escalation (> 0.4) with deceleration
            if current_net > 0.4 and confidence >= 70:
                return "Risk-Off Peak (first signs of deceleration)"
            # Moderate escalation with significant deceleration
            elif current_net > 0.2 and deceleration_magnitude > 0.2:
                return "Risk-Off Fading"
            # Low escalation, entering recovery
            elif current_net < 0.2:
                return "Recovery Phase (de-escalation emerging)"

        # No deceleration detected or no previous data
        # High escalation (> 0.6) with high confidence
        if confidence >= 80 and current_net > 0.6:
            return "Risk-Off Building"

        # Moderate escalation (0.3-0.6)
        elif current_net > 0.3:
            return "Risk-Off Active"

        # Low or negative escalation
        elif current_net < 0.0:
            return "Recovery Phase (de-escalation dominant)"
        else:
            return "Risk-Off Stabilizing"

    # Risk-On phases
    elif regime == "Risk-On":
        if current_net < -0.3:
            return "Risk-On Strengthening"
        elif current_net > 0.3:
            return "Risk-On Weakening (escalation signals emerging)"
        else:
            return "Risk-On Active"

    # Neutral phases
    else:
        if abs(current_net) < 0.2:
            return "Neutral Balanced"
        elif current_net > 0.4:
            return "Neutral Tilting Risk-Off"
        else:
            return "Neutral Tilting Risk-On"


def calculate_confidence_adjustment(
    events: List[EventWithDirection],
    net_escalation: float,
    base_confidence: int,
) -> tuple[int, str]:
    """Calculate confidence adjustment based on signal contradictions.

    Args:
        events: Tagged events
        net_escalation: Calculated net escalation score
        base_confidence: Original confidence from Step 1

    Returns:
        (adjustment, reasoning) tuple
        - adjustment: -20 to +10 points
        - reasoning: Explanation of adjustment

    Logic:
        - Strong contradictions (escalation + de-escalation mixed) → lower confidence
        - Pure directional signals (all escalation or all de-escalation) → raise confidence
        - Many neutral events → lower confidence (unclear picture)
    """
    if not events:
        return 0, "No events to assess"

    # Count event types
    escalation_count = sum(1 for e in events if e.direction == "escalation")
    deescalation_count = sum(1 for e in events if e.direction == "de-escalation")
    neutral_count = sum(1 for e in events if e.direction == "neutral")

    total_count = len(events)

    # Case 1: Strong contradictions (both escalation and de-escalation present)
    if escalation_count > 0 and deescalation_count > 0:
        # Calculate contradiction strength
        minority = min(escalation_count, deescalation_count)
        contradiction_ratio = minority / total_count

        if contradiction_ratio >= 0.3:  # 30%+ minority signals
            adjustment = -15
            reasoning = (
                f"Strong signal contradiction: {escalation_count} escalation + "
                f"{deescalation_count} de-escalation events. Confidence lowered due to mixed signals."
            )
        elif contradiction_ratio >= 0.2:  # 20-30% minority
            adjustment = -10
            reasoning = (
                f"Moderate signal contradiction: {escalation_count} escalation + "
                f"{deescalation_count} de-escalation events. Some uncertainty."
            )
        else:  # < 20% minority
            adjustment = -5
            reasoning = (
                f"Minor signal contradiction: {escalation_count} escalation + "
                f"{deescalation_count} de-escalation events, but clear dominant direction."
            )

    # Case 2: Pure directional signals (all same direction)
    elif escalation_count == total_count or deescalation_count == total_count:
        adjustment = +5
        direction = "escalation" if escalation_count == total_count else "de-escalation"
        reasoning = (
            f"Pure directional signal: all {total_count} events are {direction}. "
            f"Confidence boosted by signal consistency."
        )

    # Case 3: Too many neutral events (unclear picture)
    elif neutral_count / total_count > 0.5:
        adjustment = -10
        reasoning = (
            f"Weak signal clarity: {neutral_count}/{total_count} events are neutral. "
            f"Confidence lowered due to lack of clear directional information."
        )

    # Case 4: Normal case (some directional bias, no major issues)
    else:
        adjustment = 0
        reasoning = "Normal signal distribution, no confidence adjustment needed."

    # Ensure confidence stays within bounds
    final_confidence = max(0, min(100, base_confidence + adjustment))
    actual_adjustment = final_confidence - base_confidence

    return actual_adjustment, reasoning


def analyze_event_directions(
    key_events: List[str],
    regime: str,
    confidence: int,
    previous_net_escalation: Optional[float] = None,
) -> EventDirectionAnalysis:
    """Main entry point: analyze event directions and detect contradictions.

    Args:
        key_events: Raw event strings from Step 1
        regime: Current regime classification
        confidence: Base confidence from Step 1
        previous_net_escalation: Optional net escalation from previous day

    Returns:
        EventDirectionAnalysis with tagged events and phase detection
    """
    # Step 1: Tag each event with direction
    tagged_events = []
    for event in key_events:
        direction, weight = classify_event_direction(event)
        tagged_events.append(EventWithDirection(
            event=event,
            direction=direction,
            weight=weight
        ))

    # Step 2: Calculate net escalation score
    net_escalation = calculate_net_escalation(tagged_events)

    # Step 3: Detect regime phase
    regime_phase = detect_regime_phase(
        current_events=tagged_events,
        confidence=confidence,
        regime=regime,
        previous_net_escalation=previous_net_escalation,
    )

    # Step 4: Calculate confidence adjustment
    confidence_adj, adj_reasoning = calculate_confidence_adjustment(
        events=tagged_events,
        net_escalation=net_escalation,
        base_confidence=confidence,
    )

    # Step 5: Generate overall reasoning
    escalation_count = sum(1 for e in tagged_events if e.direction == "escalation")
    deescalation_count = sum(1 for e in tagged_events if e.direction == "de-escalation")
    neutral_count = sum(1 for e in tagged_events if e.direction == "neutral")

    reasoning = (
        f"Event breakdown: {escalation_count} escalation, {deescalation_count} de-escalation, "
        f"{neutral_count} neutral. Net escalation score: {net_escalation:.2f}. "
        f"Regime phase: {regime_phase}. {adj_reasoning}"
    )

    return EventDirectionAnalysis(
        key_events_tagged=tagged_events,
        net_escalation_score=net_escalation,
        regime_phase=regime_phase,
        confidence_adjustment=confidence_adj,
        reasoning=reasoning,
    )
