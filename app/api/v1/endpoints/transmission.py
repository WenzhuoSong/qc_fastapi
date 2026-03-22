"""
Transmission Monitoring Endpoint (Phase 2 Week 4)

Displays the causal chain from macro events to final weights:
  Macro Events → Transmission Vector → Sector Scores → Final Weights

Usage:
    GET /api/v1/transmission/?date=2026-03-20
    GET /api/v1/transmission/              # Latest record
"""

from datetime import date
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.security import verify_token
from app.db.database import get_db
from app.db.models import DailyDecision, EventTransmission, DecisionLog
from pydantic import BaseModel

router = APIRouter()


# ═══════════════════════════════════════════════════════════════
# Response Schema
# ═══════════════════════════════════════════════════════════════

class TransmissionAnalysis(BaseModel):
    """Complete causal chain analysis for a single date."""
    date: str
    status: str

    # Step 1: Macro events
    macro_regime: Optional[str] = None
    macro_confidence: Optional[int] = None
    key_events: List[str] = []

    # Step 2: Transmission vector
    event_type: Optional[str] = None
    transmission_vector: Optional[Dict[str, float]] = None
    validated: bool = False
    accuracy_score: Optional[float] = None

    # Step 3: Sector scores (from Step 2 output)
    sector_scores: Optional[Dict[str, int]] = None

    # Step 4: Final weights
    final_weights: Optional[Dict[str, float]] = None
    defense_level: Optional[str] = None

    # Insights
    correlation_analysis: Optional[str] = None


# ═══════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════

def _extract_sector_scores(step2_result: str) -> Dict[str, int]:
    """Extract sector scores from Step 2 JSON string."""
    if not step2_result:
        return {}

    try:
        import json
        data = json.loads(step2_result)

        # Extract numeric scores for 11 sectors
        sectors = ["XLE", "XLF", "XLV", "XLI", "XLP", "XLU", "XLY", "XLK", "XLC", "XLRE", "XLB"]
        scores = {}
        for sector in sectors:
            if sector in data and isinstance(data[sector], (int, float)):
                scores[sector] = int(data[sector])

        return scores
    except (json.JSONDecodeError, ValueError):
        return {}


def _analyze_correlation(
    transmission: Optional[Dict[str, float]],
    scores: Optional[Dict[str, int]],
    weights: Optional[Dict[str, float]],
) -> str:
    """Generate correlation analysis between transmission, scores, and weights."""
    if not transmission or not scores:
        return "Insufficient data for correlation analysis"

    # Find top 3 transmission signals
    sorted_trans = sorted(transmission.items(), key=lambda x: -abs(x[1]))[:3]

    insights = []
    for sector, trans_strength in sorted_trans:
        score = scores.get(sector)
        weight = weights.get(sector, 0.0) if weights else 0.0

        if score is None:
            continue

        # Check alignment
        if trans_strength > 0.5 and score >= 7:
            insights.append(f"✓ {sector}: Strong positive signal aligned (trans={trans_strength:+.2f}, score={score})")
        elif trans_strength < -0.5 and score <= 4:
            insights.append(f"✓ {sector}: Strong negative signal aligned (trans={trans_strength:+.2f}, score={score})")
        elif abs(trans_strength) > 0.5:
            insights.append(f"? {sector}: Signal mismatch (trans={trans_strength:+.2f}, score={score})")

    return "\n".join(insights) if insights else "No strong transmission signals (all < 0.5)"


# ═══════════════════════════════════════════════════════════════
# Endpoint
# ═══════════════════════════════════════════════════════════════

@router.get("/", response_model=TransmissionAnalysis)
async def get_transmission_analysis(
    target_date: Optional[str] = Query(None, description="YYYY-MM-DD format"),
    _token: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """Return transmission causal chain analysis for a date.

    If no date provided, returns latest READY record.
    """
    if target_date:
        # Parse target date
        try:
            from datetime import datetime
            parsed_date = datetime.strptime(target_date, "%Y-%m-%d").date()
        except ValueError:
            return TransmissionAnalysis(
                date=target_date,
                status="ERROR",
                correlation_analysis=f"Invalid date format: {target_date}. Use YYYY-MM-DD."
            )

        decision = db.query(DailyDecision).filter_by(date=parsed_date).first()
    else:
        # Use latest READY record
        decision = (
            db.query(DailyDecision)
            .filter_by(status="READY")
            .order_by(desc(DailyDecision.date))
            .first()
        )

    if not decision:
        return TransmissionAnalysis(
            date=target_date or str(date.today()),
            status="NO_DATA",
            correlation_analysis="No decision record found for this date"
        )

    # Get related records
    transmission = db.query(EventTransmission).filter_by(date=decision.date).first()
    log = db.query(DecisionLog).filter_by(date=decision.date).first()

    # Parse Step 1 output
    key_events = []
    macro_regime = None
    macro_confidence = None

    if decision.step1_macro_result:
        try:
            import json
            step1_data = json.loads(decision.step1_macro_result)
            macro_regime = step1_data.get("regime")
            macro_confidence = step1_data.get("confidence")
            key_events = step1_data.get("key_events", [])
        except json.JSONDecodeError:
            pass

    # Extract sector scores from Step 2
    sector_scores = _extract_sector_scores(decision.step2_micro_result)

    # Analyze correlation
    correlation_text = _analyze_correlation(
        transmission.transmission_vector if transmission else None,
        sector_scores,
        decision.final_weights
    )

    return TransmissionAnalysis(
        date=str(decision.date),
        status=decision.status,
        macro_regime=macro_regime,
        macro_confidence=macro_confidence,
        key_events=key_events,
        event_type=transmission.event_type if transmission else None,
        transmission_vector=transmission.transmission_vector if transmission else None,
        validated=transmission.validated if transmission else False,
        accuracy_score=transmission.accuracy_score if transmission else None,
        sector_scores=sector_scores,
        final_weights=decision.final_weights,
        defense_level=log.defense_level if log else None,
        correlation_analysis=correlation_text,
    )
