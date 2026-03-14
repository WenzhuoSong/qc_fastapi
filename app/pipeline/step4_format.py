"""
Step 4 — Normalize Scores into Portfolio Weights

Pure Python, no LLM call. Converts raw scores into a weights dict
that sums to 1.0 and respects the max-concentration cap.
"""

import json
import re
from typing import Dict


MAX_SINGLE_WEIGHT = 0.40


def normalize_to_weights(micro_result: str, risk_result: str) -> Dict[str, float]:
    """Parse raw scores from Step 2/3 and convert to portfolio weights.

    Falls back to equal-weight if parsing fails.
    """
    scores = _extract_scores(micro_result)
    if not scores:
        scores = _extract_scores(risk_result)
    if not scores:
        return _equal_weight_fallback()

    total = sum(scores.values())
    if total <= 0:
        return _equal_weight_fallback()

    weights = {ticker: score / total for ticker, score in scores.items()}

    weights = _apply_cap(weights, MAX_SINGLE_WEIGHT)

    return {k: round(v, 4) for k, v in weights.items() if v > 0.001}


def _extract_scores(text: str) -> Dict[str, float]:
    """Try to pull a JSON object of ticker→score from LLM output."""
    json_match = re.search(r"\{[^{}]+\}", text)
    if json_match:
        try:
            raw = json.loads(json_match.group())
            return {k: float(v) for k, v in raw.items() if isinstance(v, (int, float))}
        except (json.JSONDecodeError, ValueError):
            pass
    return {}


def _apply_cap(weights: Dict[str, float], cap: float) -> Dict[str, float]:
    """Redistribute excess weight from capped positions."""
    capped: Dict[str, float] = {}
    excess = 0.0

    for ticker, w in weights.items():
        if w > cap:
            excess += w - cap
            capped[ticker] = cap
        else:
            capped[ticker] = w

    uncapped = {t: w for t, w in capped.items() if w < cap}
    uncapped_total = sum(uncapped.values())

    if uncapped_total > 0 and excess > 0:
        for t in uncapped:
            capped[t] += excess * (capped[t] / uncapped_total)

    return capped


def _equal_weight_fallback() -> Dict[str, float]:
    """Safety net: equal weight across core sector ETFs."""
    tickers = ["XLK", "XLF", "XLV", "XLE", "XLI", "XLP", "XLU", "XLY", "XLC", "XLRE", "XLB"]
    w = round(1.0 / len(tickers), 4)
    return {t: w for t in tickers}
