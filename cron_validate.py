"""
Phase 5a: Railway Cron Job for Daily Accuracy Validation

Runs T+1 validation: validates yesterday's prediction using today's market data.
Designed to run after cron_pipeline.py completes.

Schedule: 15:00 ET (after main pipeline at 14:00 ET)

This is a lightweight wrapper around validate_yesterday.py that adds Railway-specific
error handling and logging.
"""

import sys
from datetime import date, timedelta

from app.db.database import init_db, get_db
from app.db.models import DailyAccuracy, DecisionLog


def main():
    """Run daily accuracy validation."""
    print("\n" + "="*70)
    print("Phase 5a: Daily Accuracy Validation (Railway Cron)")
    print("="*70 + "\n")

    init_db()
    db = next(get_db())

    # Validate yesterday (T+1 validation)
    yesterday = date.today() - timedelta(days=1)

    print(f"Target Date: {yesterday}")
    print(f"Validation Date: {date.today()}")
    print()

    # Import trading day checker
    from validate_yesterday import is_trading_day

    # Check if yesterday was a trading day
    if not is_trading_day(yesterday):
        weekday_name = yesterday.strftime("%A")
        print(f"⏭️  {yesterday} ({weekday_name}) is not a trading day")
        print(f"    Market closed - no validation needed")
        sys.exit(0)

    # Check if yesterday has a prediction
    decision = db.query(DecisionLog).filter_by(date=yesterday).first()
    if not decision or not decision.ai_regime:
        print(f"⚠️  No prediction for {yesterday} - nothing to validate")
        print(f"    (This is unexpected for a trading day - check pipeline logs)")
        sys.exit(0)

    # Check if already validated
    existing = db.query(DailyAccuracy).filter_by(date=yesterday).first()
    if existing:
        print(f"✅ {yesterday} already validated")
        print(f"   Prediction: {existing.predicted_regime}")
        print(f"   Actual: {existing.actual_market_direction}")
        print(f"   Correct: {existing.prediction_correct}")
        sys.exit(0)

    # Import and run validation (avoid circular imports)
    from validate_yesterday import validate_prediction

    print("Running validation...")
    success = validate_prediction(yesterday, db, force=False)

    if not success:
        print("\n❌ Validation failed - see errors above")
        sys.exit(1)

    # Show summary stats
    total = db.query(DailyAccuracy).count()
    correct = db.query(DailyAccuracy).filter_by(prediction_correct=True).count()

    if total > 0:
        accuracy = correct / total * 100
        print(f"\n{'='*70}")
        print(f"Overall Accuracy: {correct}/{total} ({accuracy:.1f}%)")
        print(f"{'='*70}\n")

    print("✅ Daily validation complete")
    sys.exit(0)


if __name__ == "__main__":
    # Apply Railway IPv4 patch (same as cron_pipeline.py)
    import socket
    original_getaddrinfo = socket.getaddrinfo

    def getaddrinfo_ipv4_only(*args, **kwargs):
        kwargs['family'] = socket.AF_INET
        return original_getaddrinfo(*args, **kwargs)

    socket.getaddrinfo = getaddrinfo_ipv4_only

    main()
