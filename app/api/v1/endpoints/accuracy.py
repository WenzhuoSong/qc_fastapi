"""
Phase 5a: Accuracy Summary Endpoint

Provides regime prediction accuracy metrics for monitoring and analysis.

Metrics tracked:
- Overall accuracy (correct predictions / total predictions)
- Per-regime accuracy (Risk-Off, Neutral, Risk-On breakdown)
- Confidence calibration (high-confidence predictions more accurate?)
- AI vs QC agreement rate
- Recent performance (last 7/30 days)
"""

from datetime import date, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from app.core.security import verify_token
from app.db.database import get_db
from app.db.models import DailyAccuracy


router = APIRouter()


class RegimeAccuracy(BaseModel):
    """Accuracy breakdown for a single regime."""
    regime: str
    total: int
    correct: int
    accuracy: float


class ConfidenceBucket(BaseModel):
    """Accuracy by confidence level."""
    confidence_range: str
    total: int
    correct: int
    accuracy: float


class AccuracySummary(BaseModel):
    """Overall accuracy summary response."""
    total_predictions: int
    correct_predictions: int
    overall_accuracy: float

    # Per-regime breakdown
    by_regime: List[RegimeAccuracy]

    # Confidence calibration
    by_confidence: List[ConfidenceBucket]

    # AI vs QC agreement
    qc_agreement_rate: Optional[float] = None
    qc_agreed_accuracy: Optional[float] = None
    qc_disagreed_accuracy: Optional[float] = None

    # Recent performance
    last_7_days_accuracy: Optional[float] = None
    last_30_days_accuracy: Optional[float] = None

    # Date range
    date_range: Dict[str, str]


def calculate_regime_accuracy(db: Session) -> List[RegimeAccuracy]:
    """Calculate accuracy breakdown by regime."""
    regimes = ["Risk-Off", "Neutral", "Risk-On"]
    results = []

    for regime in regimes:
        total = db.query(DailyAccuracy).filter_by(predicted_regime=regime).count()
        if total == 0:
            continue

        correct = db.query(DailyAccuracy).filter(
            and_(
                DailyAccuracy.predicted_regime == regime,
                DailyAccuracy.prediction_correct == True
            )
        ).count()

        results.append(RegimeAccuracy(
            regime=regime,
            total=total,
            correct=correct,
            accuracy=correct / total if total > 0 else 0.0
        ))

    return results


def calculate_confidence_buckets(db: Session) -> List[ConfidenceBucket]:
    """Calculate accuracy by confidence level.

    Buckets: [0-60), [60-75), [75-85), [85-100]
    """
    buckets = [
        ("0-60", 0, 60),
        ("60-75", 60, 75),
        ("75-85", 75, 85),
        ("85-100", 85, 100),
    ]

    results = []

    for label, low, high in buckets:
        query = db.query(DailyAccuracy).filter(
            and_(
                DailyAccuracy.predicted_confidence >= low,
                DailyAccuracy.predicted_confidence < high if high < 100 else DailyAccuracy.predicted_confidence <= high
            )
        )

        total = query.count()
        if total == 0:
            continue

        correct = query.filter(DailyAccuracy.prediction_correct == True).count()

        results.append(ConfidenceBucket(
            confidence_range=label,
            total=total,
            correct=correct,
            accuracy=correct / total if total > 0 else 0.0
        ))

    return results


def calculate_qc_agreement_stats(db: Session) -> Dict[str, Optional[float]]:
    """Calculate accuracy when AI agrees vs disagrees with QC."""
    # Agreement rate
    total_with_qc = db.query(DailyAccuracy).filter(
        DailyAccuracy.qc_regime.isnot(None)
    ).count()

    if total_with_qc == 0:
        return {
            "qc_agreement_rate": None,
            "qc_agreed_accuracy": None,
            "qc_disagreed_accuracy": None,
        }

    agreed_count = db.query(DailyAccuracy).filter(
        DailyAccuracy.regime_match == True
    ).count()

    agreement_rate = agreed_count / total_with_qc if total_with_qc > 0 else None

    # Accuracy when agreed
    agreed_correct = db.query(DailyAccuracy).filter(
        and_(
            DailyAccuracy.regime_match == True,
            DailyAccuracy.prediction_correct == True
        )
    ).count()

    agreed_accuracy = agreed_correct / agreed_count if agreed_count > 0 else None

    # Accuracy when disagreed
    disagreed_count = db.query(DailyAccuracy).filter(
        DailyAccuracy.regime_match == False
    ).count()

    disagreed_correct = db.query(DailyAccuracy).filter(
        and_(
            DailyAccuracy.regime_match == False,
            DailyAccuracy.prediction_correct == True
        )
    ).count()

    disagreed_accuracy = disagreed_correct / disagreed_count if disagreed_count > 0 else None

    return {
        "qc_agreement_rate": agreement_rate,
        "qc_agreed_accuracy": agreed_accuracy,
        "qc_disagreed_accuracy": disagreed_accuracy,
    }


def calculate_recent_accuracy(db: Session, days: int) -> Optional[float]:
    """Calculate accuracy for last N days."""
    cutoff = date.today() - timedelta(days=days)

    total = db.query(DailyAccuracy).filter(
        DailyAccuracy.date >= cutoff
    ).count()

    if total == 0:
        return None

    correct = db.query(DailyAccuracy).filter(
        and_(
            DailyAccuracy.date >= cutoff,
            DailyAccuracy.prediction_correct == True
        )
    ).count()

    return correct / total if total > 0 else None


@router.get("/", response_model=AccuracySummary)
async def get_accuracy_summary(
    _token: str = Depends(verify_token),
    db: Session = Depends(get_db),
):
    """Return regime prediction accuracy summary.

    Provides:
    - Overall accuracy rate
    - Per-regime breakdown
    - Confidence calibration analysis
    - AI vs QC agreement metrics
    - Recent performance (7/30 days)
    """
    # Overall stats
    total = db.query(DailyAccuracy).count()

    if total == 0:
        return AccuracySummary(
            total_predictions=0,
            correct_predictions=0,
            overall_accuracy=0.0,
            by_regime=[],
            by_confidence=[],
            date_range={"start": "N/A", "end": "N/A"},
        )

    correct = db.query(DailyAccuracy).filter_by(prediction_correct=True).count()
    overall_accuracy = correct / total if total > 0 else 0.0

    # Date range
    min_date = db.query(func.min(DailyAccuracy.date)).scalar()
    max_date = db.query(func.max(DailyAccuracy.date)).scalar()

    # Regime breakdown
    by_regime = calculate_regime_accuracy(db)

    # Confidence buckets
    by_confidence = calculate_confidence_buckets(db)

    # QC agreement
    qc_stats = calculate_qc_agreement_stats(db)

    # Recent performance
    last_7_days = calculate_recent_accuracy(db, 7)
    last_30_days = calculate_recent_accuracy(db, 30)

    return AccuracySummary(
        total_predictions=total,
        correct_predictions=correct,
        overall_accuracy=overall_accuracy,
        by_regime=by_regime,
        by_confidence=by_confidence,
        qc_agreement_rate=qc_stats["qc_agreement_rate"],
        qc_agreed_accuracy=qc_stats["qc_agreed_accuracy"],
        qc_disagreed_accuracy=qc_stats["qc_disagreed_accuracy"],
        last_7_days_accuracy=last_7_days,
        last_30_days_accuracy=last_30_days,
        date_range={
            "start": str(min_date) if min_date else "N/A",
            "end": str(max_date) if max_date else "N/A",
        },
    )


@router.get("/daily")
async def get_daily_accuracy(
    _token: str = Depends(verify_token),
    db: Session = Depends(get_db),
    limit: int = Query(default=30, le=365),
):
    """Return daily accuracy records for detailed analysis.

    Args:
        limit: Number of recent records to return (default 30)
    """
    records = db.query(DailyAccuracy).order_by(
        DailyAccuracy.date.desc()
    ).limit(limit).all()

    return {
        "count": len(records),
        "records": [
            {
                "date": str(r.date),
                "predicted_regime": r.predicted_regime,
                "actual_direction": r.actual_market_direction,
                "spy_return_1d": f"{r.spy_return_1d:.4f}" if r.spy_return_1d else None,
                "prediction_correct": r.prediction_correct,
                "confidence": r.predicted_confidence,
                "qc_regime": r.qc_regime,
                "regime_match": r.regime_match,
            }
            for r in records
        ]
    }
