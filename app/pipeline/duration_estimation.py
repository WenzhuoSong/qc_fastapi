"""
Phase 3b: Duration Estimation & Exit Strategy Generation

Classifies macro events by expected duration and provides tactical guidance
for position management.

Key concepts:
- Short-term (1-2 weeks): Temporary disruptions, emergency responses
- Medium-term (1-2 months): Structural changes, policy adjustments
- Long-term (indefinite): Paradigm shifts, new normal

Example:
    Event: "G7 backs security convoy" → 1-2 weeks (stabilization attempt)
    Event: "Iran beyond control" → 1-2 months (prolonged conflict)
    Event: "New Cold War paradigm" → Indefinite (structural shift)
"""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field


# Duration categories
DurationCategory = Literal["short_term", "medium_term", "long_term"]


class DurationSignal(BaseModel):
    """Duration signal extracted from event analysis.

    Attributes:
        category: short_term (1-2 weeks), medium_term (1-2 months), long_term (indefinite)
        confidence: Confidence level (0-100)
        key_indicators: List of keywords/phrases that influenced classification
    """
    category: DurationCategory
    confidence: int = Field(ge=0, le=100)
    key_indicators: List[str] = Field(default_factory=list)


class DurationEstimate(BaseModel):
    """Complete duration estimate with exit strategy.

    Attributes:
        primary_duration: Human-readable duration estimate
        category: Duration category classification
        confidence: Confidence in duration estimate (0-100)
        key_duration_signals: Events/keywords that informed the estimate
        exit_strategy: Tactical guidance for position management
        tactical_implications: List of actionable recommendations
    """
    primary_duration: str = Field(
        description="Human-readable duration (e.g., '1-2 weeks peak, then gradual normalization')"
    )
    category: DurationCategory
    confidence: int = Field(ge=0, le=100)
    key_duration_signals: List[str] = Field(default_factory=list)
    exit_strategy: str = Field(
        description="Specific guidance on when/how to exit positions"
    )
    tactical_implications: List[str] = Field(
        default_factory=list,
        description="List of actionable recommendations for QC"
    )


# ═══════════════════════════════════════════════════════════════
# Duration Classification Keywords
# ═══════════════════════════════════════════════════════════════

SHORT_TERM_KEYWORDS = [
    # Temporary measures
    "emergency", "temporary", "immediate response", "short-term",
    "emergency meeting", "crisis response", "temporary measure",

    # Stabilization attempts
    "backs security", "backs maritime", "g7 backs", "coalition forms",
    "emergency convoy", "security convoy", "peacekeeping",
    "stabilization", "intervention",

    # Quick resolutions
    "cease fire imminent", "talks scheduled", "agreement close",
    "temporary halt", "brief disruption",

    # Historical precedents
    "similar to 2016", "similar to 2020", "resolved quickly before",
    "precedent suggests", "historical pattern",
]

MEDIUM_TERM_KEYWORDS = [
    # Structural issues
    "structural", "prolonged", "extended", "drawn out",
    "long conflict", "protracted", "beyond control",

    # Policy changes needed
    "requires policy", "needs reform", "regulatory change",
    "diplomatic solution needed", "negotiations ongoing",

    # Supply chain
    "supply chain", "logistics", "infrastructure damage",
    "rebuilding", "repair", "reconstruction",

    # Economic adjustment
    "adjustment period", "transition", "realignment",
    "repricing", "market adjustment",
]

LONG_TERM_KEYWORDS = [
    # Paradigm shifts
    "new normal", "paradigm shift", "fundamental change",
    "structural shift", "regime change", "new era",

    # Permanent changes
    "permanent", "irreversible", "long-lasting", "indefinite",
    "systemic", "foundational",

    # Geopolitical realignment
    "cold war", "new world order", "decoupling",
    "de-globalization", "reshoring", "strategic autonomy",

    # Secular trends
    "secular", "multi-year", "decade-long", "generational",
    "long-term trend", "megatrend",
]


# ═══════════════════════════════════════════════════════════════
# Core Functions
# ═══════════════════════════════════════════════════════════════

def classify_event_duration(event: str, reasoning: str = "") -> DurationSignal:
    """Classify a single event by expected duration.

    Args:
        event: Event description string
        reasoning: Additional context (e.g., Step 1 reasoning)

    Returns:
        DurationSignal with category, confidence, and key indicators

    Strategy:
        1. Check for long-term keywords (highest priority - paradigm shifts)
        2. Check for medium-term keywords (structural issues)
        3. Check for short-term keywords (temporary measures)
        4. Default to medium-term if unclear
    """
    combined_text = (event + " " + reasoning).lower()

    # Count keyword matches
    short_matches = sum(1 for kw in SHORT_TERM_KEYWORDS if kw in combined_text)
    medium_matches = sum(1 for kw in MEDIUM_TERM_KEYWORDS if kw in combined_text)
    long_matches = sum(1 for kw in LONG_TERM_KEYWORDS if kw in combined_text)

    # Extract matched keywords for explainability
    key_indicators = []

    # Classify based on dominant signal (long-term has highest priority)
    if long_matches > 0 and long_matches >= medium_matches and long_matches >= short_matches:
        category = "long_term"
        confidence = min(100, 60 + long_matches * 10)
        key_indicators = [kw for kw in LONG_TERM_KEYWORDS if kw in combined_text][:3]

    elif short_matches > medium_matches:
        category = "short_term"
        confidence = min(100, 50 + short_matches * 10)
        key_indicators = [kw for kw in SHORT_TERM_KEYWORDS if kw in combined_text][:3]

    else:
        # Default to medium-term (most common for macro events)
        category = "medium_term"
        confidence = min(100, 50 + medium_matches * 10) if medium_matches > 0 else 50
        key_indicators = [kw for kw in MEDIUM_TERM_KEYWORDS if kw in combined_text][:3]

    return DurationSignal(
        category=category,
        confidence=confidence,
        key_indicators=key_indicators,
    )


def aggregate_duration_signals(
    key_events: List[str],
    reasoning: str,
    regime: str,
) -> DurationEstimate:
    """Aggregate duration signals from multiple events and generate exit strategy.

    Args:
        key_events: List of key events from Step 1
        reasoning: Step 1 reasoning text
        regime: Current regime (Risk-On, Neutral, Risk-Off)

    Returns:
        DurationEstimate with primary duration, exit strategy, and tactical implications

    Logic:
        1. Classify each event by duration
        2. Weight by confidence and event count
        3. Generate human-readable duration estimate
        4. Provide exit strategy based on duration category
    """
    if not key_events:
        return DurationEstimate(
            primary_duration="Unknown (no events to analyze)",
            category="medium_term",
            confidence=30,
            exit_strategy="Hold current positions pending further information",
            tactical_implications=["Monitor news flow for clarification"],
        )

    # Classify each event
    signals = [classify_event_duration(event, reasoning) for event in key_events]

    # Count by category
    short_count = sum(1 for s in signals if s.category == "short_term")
    medium_count = sum(1 for s in signals if s.category == "medium_term")
    long_count = sum(1 for s in signals if s.category == "long_term")

    total_count = len(signals)

    # Calculate weighted confidence
    avg_confidence = sum(s.confidence for s in signals) / len(signals)

    # Determine primary category (highest count, ties go to longer duration)
    if long_count > 0 and long_count >= medium_count and long_count >= short_count:
        primary_category = "long_term"
        primary_duration = "Indefinite (structural paradigm shift)"
    elif short_count > medium_count and short_count > long_count:
        primary_category = "short_term"
        primary_duration = "1-2 weeks (temporary disruption)"
    else:
        primary_category = "medium_term"
        primary_duration = "1-2 months (prolonged adjustment period)"

    # Refine duration if mixed signals
    if total_count >= 3:
        if short_count > 0 and medium_count > 0 and long_count == 0:
            # Mix of short and medium → "2-4 weeks"
            primary_duration = "2-4 weeks (temporary with lingering effects)"
        elif medium_count > 0 and long_count > 0 and short_count == 0:
            # Mix of medium and long → "several months to indefinite"
            primary_duration = "Several months to indefinite (structural shift underway)"
        elif short_count > 0 and long_count > 0:
            # Mix of short and long → contradictory signals
            primary_duration = "Uncertain (contradictory duration signals)"
            avg_confidence = max(30, avg_confidence - 20)

    # Collect all key indicators
    all_indicators = []
    for signal in signals:
        all_indicators.extend(signal.key_indicators)
    # Deduplicate and limit
    key_duration_signals = list(dict.fromkeys(all_indicators))[:5]

    # Generate exit strategy based on category and regime
    exit_strategy = _generate_exit_strategy(
        category=primary_category,
        regime=regime,
        confidence=int(avg_confidence),
    )

    # Generate tactical implications
    tactical_implications = _generate_tactical_implications(
        category=primary_category,
        regime=regime,
        short_count=short_count,
        medium_count=medium_count,
        long_count=long_count,
    )

    return DurationEstimate(
        primary_duration=primary_duration,
        category=primary_category,
        confidence=int(avg_confidence),
        key_duration_signals=key_duration_signals,
        exit_strategy=exit_strategy,
        tactical_implications=tactical_implications,
    )


def _generate_exit_strategy(category: DurationCategory, regime: str, confidence: int) -> str:
    """Generate specific exit strategy based on duration and regime."""

    if regime == "Risk-Off":
        if category == "short_term":
            return (
                "Aggressive profit-taking strategy: Take profits on defensive positions "
                "at +8-10% gains. Short-term spike expected to normalize within 1-2 weeks. "
                "Prepare to rotate back to growth sectors once stabilization signals appear."
            )
        elif category == "medium_term":
            return (
                "Moderate holding period: Hold defensive positions for +12-15% targets. "
                "Prolonged risk-off environment (1-2 months) supports defensive sectors. "
                "Begin reducing exposure when 2-3 pivot signals (oil stabilization, credit spreads) appear."
            )
        else:  # long_term
            return (
                "Strategic reallocation: This is a structural shift, not a cyclical dip. "
                "Hold defensive/energy positions for +16-20%+ targets. Consider this the new "
                "baseline allocation. Only exit on regime change confirmation (not just stabilization signals)."
            )

    elif regime == "Risk-On":
        if category == "short_term":
            return (
                "Ride the momentum: Short-term bullish catalyst supports growth sectors. "
                "Hold growth positions for quick gains (+5-8%). Monitor for reversal signals "
                "as temporary boost fades in 1-2 weeks."
            )
        elif category == "medium_term":
            return (
                "Sustained growth positioning: Medium-term bullish trend (1-2 months) supports "
                "overweight in XLK/XLY. Target +10-15% gains. Reduce exposure if credit markets "
                "or technical indicators show deterioration."
            )
        else:  # long_term
            return (
                "Long-term growth cycle: Structural bull market conditions. Hold growth positions "
                "for multi-month gains (+20%+). Only reduce on clear risk-off signals (VIX spike, "
                "credit stress). This is not a short-term trade."
            )

    else:  # Neutral
        if category == "short_term":
            return (
                "Wait-and-see: Short-term uncertainty (1-2 weeks) suggests neutral positioning. "
                "Hold balanced allocation. Prepare to pivot once direction clarifies."
            )
        elif category == "medium_term":
            return (
                "Range-bound strategy: Medium-term chop (1-2 months) expected. "
                "Use 70% equity exposure. Take profits on sector rotations at +8-10%. "
                "Avoid large directional bets until clearer trend emerges."
            )
        else:  # long_term
            return (
                "Structural uncertainty: Long-term mixed signals suggest secular stagnation or "
                "regime transition. Maintain diversified allocation. Focus on quality over momentum. "
                "Avoid aggressive bets until new regime stabilizes."
            )


def _generate_tactical_implications(
    category: DurationCategory,
    regime: str,
    short_count: int,
    medium_count: int,
    long_count: int,
) -> List[str]:
    """Generate list of actionable tactical implications."""

    implications = []

    # Duration-specific guidance
    if category == "short_term":
        implications.append("Tighten profit targets (lower profit_target_multiplier to 1.0x)")
        implications.append("Monitor daily for stabilization signals")
        implications.append("Prepare rotation strategy back to neutral/growth sectors")
    elif category == "medium_term":
        implications.append("Standard profit targets (profit_target_multiplier = 1.5x)")
        implications.append("Track pivot signals: oil stabilization, credit spreads, VIX normalization")
        implications.append("Position for 1-2 month hold period")
    else:  # long_term
        implications.append("Extended profit targets (profit_target_multiplier = 2.0x)")
        implications.append("This is structural, not cyclical - adjust base case expectations")
        implications.append("Only exit on regime change confirmation (not noise)")

    # Regime-specific guidance
    if regime == "Risk-Off":
        implications.append("Overweight defensives (XLP/XLU/XLV) and beneficiaries (XLE if oil shock)")
        implications.append("Underweight cyclicals (XLY/XLK/XLRE)")
    elif regime == "Risk-On":
        implications.append("Overweight growth (XLK/XLY/XLC)")
        implications.append("Reduce defensives to minimum allocation")

    # Mixed signal guidance
    if short_count > 0 and long_count > 0:
        implications.append("⚠️ Contradictory duration signals - use wider stops and lower position sizes")

    return implications
