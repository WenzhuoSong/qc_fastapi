"""
Phase 2: Canonical Event Transmission Rules

Defines macro event → sector transmission patterns. Each pattern maps
an event type to a transmission vector (11 sector impact strengths).

Transmission strength scale:
    1.0  = Full direct beneficiary (oil spike → XLE)
    0.5-0.8 = Strong secondary effect
    0.2-0.4 = Weak indirect effect
    0.0  = Neutral
    -0.2 to -1.0 = Negative impact (losers)

Usage:
    from app.pipeline.transmission_rules import match_event_to_pattern

    transmission = match_event_to_pattern(
        key_events=["Strait of Hormuz closure", "Oil supply disruption"],
        reasoning="Iran threatens to block oil shipments..."
    )
    # Returns: {"XLE": 0.95, "XLY": -0.75, ...}
"""

from typing import List, Dict, Optional, Tuple


# ═══════════════════════════════════════════════════════════════
# Canonical Transmission Patterns
# ═══════════════════════════════════════════════════════════════

CANONICAL_TRANSMISSIONS = {
    "supply_shock_oil": {
        "description": "Oil/energy supply disruption (embargo, OPEC cut, Hormuz closure)",
        "keywords": [
            "oil spike", "oil surge", "crude", "$200 oil",
            "hormuz", "strait", "iran", "embargo",
            "opec cut", "supply disruption", "saudi", "energy crisis"
        ],
        "vector": {
            "XLE": 0.95,   # Energy producers WIN (direct beneficiary)
            "XLB": 0.60,   # Materials (commodity prices rise)
            "XLI": 0.70,   # Industrials (defense contractors benefit from war premium)
            "XLY": -0.75,  # Consumer Discretionary LOSE (demand destruction)
            "XLK": -0.50,  # Tech LOSE (inflation hurts growth)
            "XLF": -0.30,  # Financials (credit stress from oil shock)
            "XLP": 0.10,   # Consumer Staples (defensive, mildly benefit)
            "XLV": 0.15,   # Healthcare (defensive, slightly positive)
            "XLU": -0.20,  # Utilities (hurt by input costs)
            "XLC": -0.40,  # Communication Services (ad spending declines)
            "XLRE": -0.60, # Real Estate (hurt by inflation)
        }
    },

    "war_geopolitical": {
        "description": "War, military conflict, geopolitical crisis",
        "keywords": [
            "war", "invasion", "attack", "missile", "bombing", "military strike",
            "iran", "russia", "ukraine", "israel", "hamas",
            "sanctions", "conflict", "escalation"
        ],
        "vector": {
            "XLI": 0.90,   # Industrials WIN (defense contractors)
            "XLE": 0.80,   # Energy (war premium on oil)
            "XLB": 0.50,   # Materials (commodity demand)
            "XLY": -0.70,  # Consumer Discretionary LOSE
            "XLF": -0.50,  # Financials (risk-off)
            "XLK": -0.45,  # Tech (growth hurt)
            "XLV": 0.30,   # Healthcare (defensive)
            "XLP": 0.25,   # Consumer Staples (defensive)
            "XLU": 0.20,   # Utilities (defensive)
            "XLRE": -0.40, # Real Estate (risk-off)
            "XLC": -0.35,  # Communication (risk-off)
        }
    },

    "rate_shock_hawkish": {
        "description": "Interest rate spike, Fed hawkish, yields surge",
        "keywords": [
            "rate hike", "fed hawkish", "yields surge", "higher for longer",
            "real rates", "australia hike", "10-year yield",
            "bond selloff", "tightening"
        ],
        "vector": {
            "XLF": 0.70,   # Financials WIN (banks benefit from higher rates)
            "XLE": 0.30,   # Energy (neutral to mildly positive)
            "XLB": 0.20,   # Materials (mild benefit)
            "XLK": -0.80,  # Tech LOSE (long-duration assets crash)
            "XLRE": -0.90, # Real Estate LOSE (REITs crushed)
            "XLU": -0.60,  # Utilities LOSE (bond proxy)
            "XLY": -0.50,  # Consumer Discretionary (borrowing costs rise)
            "XLP": -0.10,  # Consumer Staples (mild headwind)
            "XLV": 0.10,   # Healthcare (defensive, slightly positive)
            "XLC": -0.40,  # Communication (growth hurt)
            "XLI": 0.10,   # Industrials (neutral)
        }
    },

    "risk_off_credit_stress": {
        "description": "Broad risk-off, financial stress, credit crisis",
        "keywords": [
            "credit stress", "bank crisis", "vix spike", "contagion",
            "crash", "liquidity crisis", "margin call", "deleveraging",
            "panic", "svb", "credit suisse"
        ],
        "vector": {
            "XLV": 0.85,   # Healthcare WIN (defensive)
            "XLP": 0.80,   # Consumer Staples WIN (defensive)
            "XLU": 0.70,   # Utilities WIN (flight to safety)
            "XLY": -0.85,  # Consumer Discretionary LOSE
            "XLK": -0.70,  # Tech LOSE (risk assets sold)
            "XLF": -0.70,  # Financials LOSE (credit stress)
            "XLI": -0.40,  # Industrials (cyclical hurt)
            "XLE": -0.30,  # Energy (risk-off)
            "XLB": -0.40,  # Materials (cyclical hurt)
            "XLRE": -0.60, # Real Estate (risk-off)
            "XLC": -0.50,  # Communication (risk-off)
        }
    },

    "recession_demand_collapse": {
        "description": "Recession, demand destruction, hard landing",
        "keywords": [
            "recession", "gdp miss", "pmi contraction", "mass layoffs",
            "demand destruction", "hard landing", "unemployment spike",
            "consumer collapse", "retail sales miss"
        ],
        "vector": {
            "XLV": 0.75,   # Healthcare WIN (defensive)
            "XLP": 0.70,   # Consumer Staples WIN (defensive)
            "XLU": 0.60,   # Utilities WIN (defensive)
            "XLY": -0.80,  # Consumer Discretionary LOSE (demand collapse)
            "XLI": -0.60,  # Industrials LOSE (cyclical)
            "XLE": -0.60,  # Energy LOSE (demand > supply in recession)
            "XLF": -0.50,  # Financials (credit stress)
            "XLK": -0.40,  # Tech (growth hurt)
            "XLB": -0.50,  # Materials (cyclical)
            "XLRE": -0.40, # Real Estate (cyclical)
            "XLC": -0.30,  # Communication (ad spending falls)
        }
    },

    "fed_dovish_easing": {
        "description": "Fed dovish pivot, rate cuts, QE, liquidity injection",
        "keywords": [
            "rate cut", "qe", "dovish pivot", "liquidity injection",
            "powell dovish", "fed easing", "stimulus", "emergency cut"
        ],
        "vector": {
            "XLRE": 0.80,  # Real Estate WIN (duration assets rally)
            "XLK": 0.70,   # Tech WIN (growth assets rally)
            "XLU": 0.70,   # Utilities WIN (bond proxy)
            "XLY": 0.60,   # Consumer Discretionary (borrowing cheaper)
            "XLF": 0.40,   # Financials (mixed - lower rates hurt banks)
            "XLI": 0.30,   # Industrials (mild benefit)
            "XLC": 0.40,   # Communication (growth positive)
            "XLV": 0.20,   # Healthcare (neutral to mild positive)
            "XLP": 0.10,   # Consumer Staples (neutral)
            "XLE": -0.30,  # Energy (commodity prices may fall)
            "XLB": -0.20,  # Materials (mild headwind)
        }
    },
}


# ═══════════════════════════════════════════════════════════════
# Pattern Matching Logic
# ═══════════════════════════════════════════════════════════════

def match_event_to_pattern(
    key_events: List[str],
    reasoning: str,
    min_keyword_matches: int = 2,
) -> Dict[str, float]:
    """Match Step 1 output to canonical transmission patterns.

    Args:
        key_events: List of key events from Step 1 (e.g., ["Oil supply disruption", ...])
        reasoning: Step 1 reasoning text
        min_keyword_matches: Minimum keywords required to match a pattern (default: 2)

    Returns:
        Transmission vector dict: {"XLE": 0.95, "XLY": -0.75, ...}
        Empty dict {} if no pattern matches.

    Strategy:
        1. Combine key_events and reasoning into searchable text
        2. For each pattern, count keyword matches
        3. Return highest scoring pattern if >= min_keyword_matches
        4. If multiple patterns match, blend them (sum and clip)
    """
    if not key_events and not reasoning:
        return {}

    # Combine all text, normalize to lowercase
    combined = " ".join(key_events).lower() + " " + reasoning.lower()

    # Score each pattern
    matches: List[Tuple[str, int, Dict[str, float]]] = []
    for pattern_name, pattern_def in CANONICAL_TRANSMISSIONS.items():
        score = sum(1 for kw in pattern_def["keywords"] if kw in combined)
        if score >= min_keyword_matches:
            matches.append((pattern_name, score, pattern_def["vector"]))

    if not matches:
        return {}  # No pattern matched

    # Sort by score descending
    matches.sort(key=lambda x: x[1], reverse=True)

    # If only one match, return it directly
    if len(matches) == 1:
        return matches[0][2]

    # Multiple matches: blend by summing and clipping to [-1.0, 1.0]
    blended: Dict[str, float] = {}
    for pattern_name, score, vector in matches:
        for sector, strength in vector.items():
            blended[sector] = blended.get(sector, 0.0) + strength

    # Clip to valid range
    for sector in blended:
        blended[sector] = max(-1.0, min(1.0, blended[sector]))

    return blended


def detect_event_type(key_events: List[str], reasoning: str = "") -> Optional[str]:
    """Detect primary event type from key_events and reasoning.

    Returns:
        Event type string (e.g., "supply_shock", "war_geopolitical")
        or None if no clear match.
    """
    combined = " ".join(key_events).lower() + " " + reasoning.lower()

    # Score each pattern
    best_match = None
    best_score = 0

    for pattern_name, pattern_def in CANONICAL_TRANSMISSIONS.items():
        score = sum(1 for kw in pattern_def["keywords"] if kw in combined)
        if score > best_score:
            best_score = score
            best_match = pattern_name

    return best_match if best_score >= 2 else None


def format_transmission_context(transmission_vector: Dict[str, float]) -> str:
    """Format transmission vector into human-readable context for Step 2 prompt.

    Args:
        transmission_vector: {"XLE": 0.95, "XLY": -0.75, ...}

    Returns:
        Formatted string for Step 2 prompt insertion.
    """
    if not transmission_vector:
        return ""

    trans_lines = []
    # Sort by absolute strength descending
    sorted_sectors = sorted(
        transmission_vector.items(),
        key=lambda x: -abs(x[1])
    )

    for sector, strength in sorted_sectors:
        if abs(strength) > 0.3:  # Only show significant impacts
            direction = "LONG" if strength > 0 else "SHORT"
            trans_lines.append(f"  {sector}: {direction} {abs(strength):.2f}")

    if not trans_lines:
        return ""

    return (
        "## MACRO EVENT TRANSMISSION (Phase 2 Prior)\n"
        "The following sector biases are derived from macro event analysis:\n"
        + "\n".join(trans_lines) + "\n\n"
        "INSTRUCTION: Use these as STARTING POINTS, then refine with ticker-level news.\n"
        "If ticker news strongly contradicts transmission (high credibility), ticker wins.\n\n"
    )
