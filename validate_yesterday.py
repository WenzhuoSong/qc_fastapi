"""
Phase 5a: Daily Accuracy Validation Script

Validates yesterday's regime prediction against actual market behavior.
Runs T+1: validates (T-1) prediction using T market data.

Usage:
    python validate_yesterday.py              # Validate yesterday
    python validate_yesterday.py 2026-03-20   # Validate specific date
    python validate_yesterday.py --backfill   # Validate all unvalidated dates

Logic:
    - Fetch yesterday's AI regime prediction from DecisionLog
    - Calculate SPY next-day return using yfinance
    - Map return to market direction:
        * Risk-Off: SPY < -0.5%
        * Neutral: SPY in [-0.5%, +0.5%]
        * Risk-On: SPY > +0.5%
    - Compare prediction vs actual direction
    - Store validation in DailyAccuracy table

Expected accuracy baseline: ~60% (better than random 33%)
Target accuracy: 70%+ with confidence weighting
"""

import sys
from datetime import date, timedelta, datetime
from typing import Optional

import yfinance as yf
from sqlalchemy.orm import Session

from app.config import settings
from app.db.database import get_db, init_db
from app.db.models import DecisionLog, DailyAccuracy


# Market direction thresholds
RISK_OFF_THRESHOLD = -0.005  # < -0.5% = Risk-Off
RISK_ON_THRESHOLD = 0.005     # > +0.5% = Risk-On
# Between these = Neutral


def get_spy_return(prediction_date: date) -> Optional[float]:
    """Fetch next-day SPY return using yfinance.

    Returns:
        1-day forward return as decimal (e.g., 0.015 = +1.5%)
        None if data unavailable
    """
    next_day = prediction_date + timedelta(days=1)

    # Download 3 days to handle weekends
    start = prediction_date
    end = next_day + timedelta(days=3)

    try:
        spy = yf.download("SPY", start=start, end=end, progress=False)

        if spy.empty or len(spy) < 2:
            print(f"⚠️  Insufficient SPY data for {prediction_date}")
            return None

        # Handle different yfinance data structures
        # Single ticker can return either 'Close' or ('Close', 'SPY') column
        if 'Close' in spy.columns:
            close_col = spy['Close']
        elif ('Close', 'SPY') in spy.columns:
            close_col = spy[('Close', 'SPY')]
        else:
            print(f"⚠️  Unexpected SPY data structure: {spy.columns}")
            return None

        # Get closing prices
        close_t = float(close_col.iloc[0])
        close_t1 = float(close_col.iloc[1])

        return_1d = (close_t1 - close_t) / close_t

        print(f"📊 SPY: {prediction_date} ${close_t:.2f} → {next_day} ${close_t1:.2f} ({return_1d:+.2%})")
        return float(return_1d)

    except Exception as e:
        print(f"❌ Error fetching SPY data: {e}")
        return None


def classify_market_direction(spy_return: float) -> str:
    """Map SPY return to market regime direction.

    Args:
        spy_return: 1-day forward return as decimal

    Returns:
        "Risk-Off", "Neutral", or "Risk-On"
    """
    if spy_return < RISK_OFF_THRESHOLD:
        return "Risk-Off"
    elif spy_return > RISK_ON_THRESHOLD:
        return "Risk-On"
    else:
        return "Neutral"


def validate_prediction(
    prediction_date: date,
    db: Session,
    force: bool = False,
) -> bool:
    """Validate a single prediction.

    Args:
        prediction_date: Date of the prediction to validate
        db: Database session
        force: Re-validate even if already validated

    Returns:
        True if validation succeeded, False otherwise
    """
    # Check if already validated
    existing = db.query(DailyAccuracy).filter_by(date=prediction_date).first()
    if existing and not force:
        print(f"⏭️  {prediction_date} already validated")
        return True

    # Fetch prediction from DecisionLog
    decision = db.query(DecisionLog).filter_by(date=prediction_date).first()
    if not decision or not decision.ai_regime:
        print(f"⚠️  No AI regime prediction for {prediction_date}")
        return False

    print(f"\n{'='*70}")
    print(f"Validating: {prediction_date}")
    print(f"{'='*70}")
    print(f"Predicted Regime  : {decision.ai_regime}")
    print(f"QC Regime         : {decision.qc_regime or 'Unknown'}")
    print(f"Confidence        : {decision.confidence or 'N/A'}")
    print(f"Defense Level     : {decision.defense_level or 'N/A'}")

    # Get actual market return
    spy_return = get_spy_return(prediction_date)
    if spy_return is None:
        print(f"⚠️  Cannot validate {prediction_date} - no market data")
        return False

    # Classify actual market direction
    actual_direction = classify_market_direction(spy_return)
    print(f"Actual Direction  : {actual_direction}")

    # Check if prediction was correct
    prediction_correct = (decision.ai_regime == actual_direction)
    regime_match = (decision.ai_regime == decision.qc_regime) if decision.qc_regime else None

    # Status display
    if prediction_correct:
        print(f"✅ CORRECT - AI predicted {decision.ai_regime}, market was {actual_direction}")
    else:
        print(f"❌ WRONG - AI predicted {decision.ai_regime}, market was {actual_direction}")

    if regime_match is not None:
        match_str = "✓ Agreed" if regime_match else "✗ Disagreed"
        print(f"AI vs QC: {match_str}")

    # Store validation result
    if existing:
        existing.spy_return_1d = spy_return
        existing.actual_market_direction = actual_direction
        existing.prediction_correct = prediction_correct
        existing.regime_match = regime_match
        existing.validated_at = datetime.utcnow()
    else:
        validation = DailyAccuracy(
            date=prediction_date,
            predicted_regime=decision.ai_regime,
            qc_regime=decision.qc_regime,
            predicted_confidence=decision.confidence,
            defense_level=decision.defense_level,
            spy_return_1d=spy_return,
            actual_market_direction=actual_direction,
            prediction_correct=prediction_correct,
            regime_match=regime_match,
        )
        db.add(validation)

    db.commit()
    print(f"💾 Validation stored to DailyAccuracy table")

    return True


def backfill_unvalidated(db: Session, force: bool = False):
    """Validate all dates with DecisionLog entries but no DailyAccuracy record.

    Args:
        db: Database session
        force: Re-validate even if already validated
    """
    print("\n🔄 Backfill mode: Finding unvalidated predictions...")

    # Get all DecisionLog dates
    decisions = db.query(DecisionLog).filter(
        DecisionLog.ai_regime.isnot(None)
    ).order_by(DecisionLog.date).all()

    print(f"Found {len(decisions)} predictions in DecisionLog")

    validated_count = 0
    skipped_count = 0
    error_count = 0

    for decision in decisions:
        # Skip future dates (can't validate yet)
        if decision.date >= date.today():
            skipped_count += 1
            continue

        # Check if already validated
        if not force:
            existing = db.query(DailyAccuracy).filter_by(date=decision.date).first()
            if existing:
                skipped_count += 1
                continue

        # Validate
        success = validate_prediction(decision.date, db, force=force)
        if success:
            validated_count += 1
        else:
            error_count += 1

    print(f"\n{'='*70}")
    print("Backfill Summary:")
    print(f"  ✅ Validated: {validated_count}")
    print(f"  ⏭️  Skipped: {skipped_count}")
    print(f"  ❌ Errors: {error_count}")
    print(f"{'='*70}")


def main():
    """Main entry point."""
    init_db()
    db = next(get_db())

    # Parse arguments
    backfill_mode = "--backfill" in sys.argv
    force = "--force" in sys.argv

    if backfill_mode:
        backfill_unvalidated(db, force=force)
        return

    # Determine target date
    if len(sys.argv) > 1 and sys.argv[1] not in ["--force", "--backfill"]:
        target_date = date.fromisoformat(sys.argv[1])
    else:
        # Default: validate yesterday
        target_date = date.today() - timedelta(days=1)

    # Validate single date
    success = validate_prediction(target_date, db, force=force)

    if success:
        # Show summary stats
        total = db.query(DailyAccuracy).count()
        correct = db.query(DailyAccuracy).filter_by(prediction_correct=True).count()

        if total > 0:
            accuracy = correct / total * 100
            print(f"\n📊 Overall Accuracy: {correct}/{total} ({accuracy:.1f}%)")

        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
