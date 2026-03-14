"""
Step 4 — Normalize Scores into Portfolio Weights

Pure Python, no LLM call. Converts raw scores into a weights dict
that sums to 1.0 and respects the max-concentration cap.
"""

import json
from typing import Dict, List


MAX_SINGLE_WEIGHT = 0.40

EXPECTED_TICKERS = {
    "XLK", "XLF", "XLV", "XLE", "XLI",
    "XLP", "XLU", "XLY", "XLC", "XLRE", "XLB",
}


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
    """Extract ticker→score JSON from LLM output.

    Finds ALL JSON objects in the text, scores each by how many
    recognised ETF tickers it contains, and returns the best match.
    """
    candidates = _find_all_json_objects(text)

    best: Dict[str, float] = {}
    best_ticker_count = 0

    for raw in candidates:
        numeric = {}
        ticker_hits = 0
        for k, v in raw.items():
            try:
                numeric[k] = float(v)
                if k.upper() in EXPECTED_TICKERS:
                    ticker_hits += 1
            except (TypeError, ValueError):
                continue

        if not numeric:
            continue

        if ticker_hits > best_ticker_count:
            best = numeric
            best_ticker_count = ticker_hits

    if best:
        return best

    if candidates:
        for raw in candidates:
            numeric = {k: float(v) for k, v in raw.items()
                       if isinstance(v, (int, float))}
            if len(numeric) >= 5:
                return numeric

    return {}


def _find_all_json_objects(text: str) -> List[dict]:
    """Find all top-level JSON objects in text, including nested braces."""
    results = []
    i = 0
    while i < len(text):
        if text[i] == '{':
            depth = 0
            start = i
            for j in range(i, len(text)):
                if text[j] == '{':
                    depth += 1
                elif text[j] == '}':
                    depth -= 1
                    if depth == 0:
                        try:
                            obj = json.loads(text[start:j + 1])
                            if isinstance(obj, dict):
                                results.append(obj)
                        except json.JSONDecodeError:
                            pass
                        i = j + 1
                        break
            else:
                i += 1
        else:
            i += 1
    return results


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
