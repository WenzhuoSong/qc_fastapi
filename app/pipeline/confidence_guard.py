"""
Confidence Guard: Four-Level State Machine

Handles extreme confidence scenarios with defined behaviors:
- CRITICAL (0-19): Circuit breaker - maintain prior allocation
- LOW (20-39): Force defensive - 20% cash + defensive boost
- MEDIUM (40-69): Light defensive - 70% equity exposure
- NORMAL (70-100): Normal operation

Prevents undefined system behavior when confidence drops too low.
"""

from typing import Dict, Literal, Tuple
from enum import Enum


class ConfidenceLevel(str, Enum):
    """Four confidence levels with defined behaviors."""
    CRITICAL = "circuit_breaker"   # < 20: Stop issuing new signals
    LOW = "force_defensive"        # 20-39: Heavy defense
    MEDIUM = "light_defensive"     # 40-69: Moderate defense
    NORMAL = "normal"              # 70+: Standard operation


CONFIDENCE_THRESHOLDS = {
    ConfidenceLevel.CRITICAL: (0, 19),
    ConfidenceLevel.LOW: (20, 39),
    ConfidenceLevel.MEDIUM: (40, 69),
    ConfidenceLevel.NORMAL: (70, 100),
}


class ConfidenceGuard:
    """Confidence guard with four-level state machine."""

    @staticmethod
    def classify_confidence(confidence: int) -> ConfidenceLevel:
        """Classify confidence into one of four levels.

        Args:
            confidence: 0-100

        Returns:
            ConfidenceLevel enum
        """
        confidence = max(0, min(100, confidence))  # Clip [0, 100]

        for level, (low, high) in CONFIDENCE_THRESHOLDS.items():
            if low <= confidence <= high:
                return level

        return ConfidenceLevel.NORMAL  # Fallback

    @staticmethod
    def apply_adjustment(
        base_confidence: int,
        adjustment: int
    ) -> Tuple[int, ConfidenceLevel, str]:
        """Apply confidence adjustment and determine action.

        Args:
            base_confidence: Current confidence (0-100)
            adjustment: Adjustment from LLM (-50 to +20)

        Returns:
            (final_confidence, confidence_level, action_description)
        """
        raw = base_confidence + adjustment
        final = max(0, min(100, raw))  # Clip [0, 100]

        level = ConfidenceGuard.classify_confidence(final)

        # Action descriptions
        actions = {
            ConfidenceLevel.CRITICAL: (
                "CIRCUIT BREAKER: Confidence critical (<20). "
                "Maintaining prior day allocation, no new signals issued."
            ),
            ConfidenceLevel.LOW: (
                "FORCE DEFENSIVE: Confidence low (20-39). "
                "Implementing 20% cash position + defensive sector boost."
            ),
            ConfidenceLevel.MEDIUM: (
                "LIGHT DEFENSIVE: Confidence medium (40-69). "
                "Reducing equity exposure to 70%."
            ),
            ConfidenceLevel.NORMAL: (
                "NORMAL OPERATION: Confidence healthy (70+). "
                "Standard allocation strategy."
            ),
        }

        action_desc = actions[level]

        return final, level, action_desc

    @staticmethod
    def should_trigger_circuit_breaker(
        confidence: int,
        confidence_level: ConfidenceLevel
    ) -> bool:
        """Check if circuit breaker should be triggered.

        Circuit breaker triggers when:
        - Confidence < 20 (CRITICAL level)

        Returns:
            True if should maintain prior allocation, False otherwise
        """
        return confidence_level == ConfidenceLevel.CRITICAL


def apply_confidence_posture(
    weights: Dict[str, float],
    confidence_level: ConfidenceLevel,
    prior_weights: Dict[str, float] | None = None,
) -> Dict[str, float]:
    """Apply confidence-based posture adjustments to weights.

    Args:
        weights: Proposed sector weights (sum=1.0)
        confidence_level: Current confidence level
        prior_weights: Previous day's weights (for circuit breaker)

    Returns:
        Adjusted weights based on confidence posture
    """
    if confidence_level == ConfidenceLevel.CRITICAL:
        # Circuit breaker: maintain prior allocation
        if prior_weights:
            return prior_weights
        else:
            # Fallback: force max defensive if no prior weights
            return _force_max_defensive(weights)

    elif confidence_level == ConfidenceLevel.LOW:
        # Force defensive: 20% cash + defensive boost
        return _force_defensive(weights, cash_pct=0.20, defensive_boost=1.3)

    elif confidence_level == ConfidenceLevel.MEDIUM:
        # Light defensive: scale to 70% equity
        return _scale_equity_exposure(weights, target=0.70)

    else:  # NORMAL
        return weights


def _force_max_defensive(weights: Dict[str, float]) -> Dict[str, float]:
    """Emergency defensive posture (circuit breaker fallback).

    Strategy:
    - XLV (Healthcare): 25%
    - XLP (Consumer Staples): 25%
    - XLU (Utilities): 20%
    - XLF (Financials): 15%
    - Rest: 15% distributed
    """
    return {
        "XLV": 0.25,
        "XLP": 0.25,
        "XLU": 0.20,
        "XLF": 0.15,
        "XLE": 0.05,
        "XLI": 0.03,
        "XLK": 0.02,
        "XLY": 0.02,
        "XLC": 0.01,
        "XLRE": 0.01,
        "XLB": 0.01,
    }


def _force_defensive(
    weights: Dict[str, float],
    cash_pct: float = 0.20,
    defensive_boost: float = 1.3
) -> Dict[str, float]:
    """Force defensive posture: cash + defensive boost.

    Args:
        weights: Original weights
        cash_pct: Cash allocation (0.0-0.5)
        defensive_boost: Multiplier for defensive sectors (1.0-2.0)

    Returns:
        Adjusted weights with cash + defensive bias
    """
    DEFENSIVE_SECTORS = {"XLV", "XLP", "XLU"}

    # Scale all weights down by (1 - cash_pct)
    equity_pct = 1.0 - cash_pct
    adjusted = {sector: w * equity_pct for sector, w in weights.items()}

    # Boost defensive sectors
    for sector in DEFENSIVE_SECTORS:
        if sector in adjusted:
            adjusted[sector] *= defensive_boost

    # Renormalize to sum=1.0
    total = sum(adjusted.values())
    if total > 0:
        adjusted = {sector: w / total for sector, w in adjusted.items()}

    return adjusted


def _scale_equity_exposure(
    weights: Dict[str, float],
    target: float = 0.70
) -> Dict[str, float]:
    """Scale equity exposure to target level.

    Args:
        weights: Original weights (sum=1.0)
        target: Target equity exposure (0.0-1.0)

    Returns:
        Scaled weights (sum=target)
    """
    scaled = {sector: w * target for sector, w in weights.items()}

    # Renormalize to sum=1.0
    total = sum(scaled.values())
    if total > 0:
        scaled = {sector: w / total for sector, w in scaled.items()}

    return scaled
