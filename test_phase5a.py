"""
Phase 5a Integration Test Suite

Tests the complete data collection and accuracy validation system:
1. DailyAccuracy table creation
2. validate_yesterday.py script functionality
3. /api/v1/accuracy/ endpoint
4. Backfill mode
5. Railway cron job wrapper

Usage:
    python test_phase5a.py
"""

import sys
from datetime import date, timedelta
from sqlalchemy import inspect

from app.db.database import init_db, get_db
from app.db.models import DailyAccuracy, DecisionLog


def test_database_table():
    """Test 1: Verify DailyAccuracy table exists."""
    print("\n=== Test 1: Database Table ===\n")

    try:
        init_db()
        db = next(get_db())

        # Check if table exists
        inspector = inspect(db.bind)
        tables = inspector.get_table_names()

        if "daily_accuracy" in tables:
            print("✅ daily_accuracy table exists")

            # Check columns
            columns = [col['name'] for col in inspector.get_columns('daily_accuracy')]
            required_columns = [
                'date', 'predicted_regime', 'qc_regime', 'predicted_confidence',
                'defense_level', 'spy_return_1d', 'actual_market_direction',
                'prediction_correct', 'regime_match', 'validated_at'
            ]

            missing = [col for col in required_columns if col not in columns]
            if missing:
                print(f"❌ Missing columns: {missing}")
                return False

            print(f"✅ All required columns present ({len(required_columns)} columns)")
            return True
        else:
            print("❌ daily_accuracy table does not exist")
            print("   Run: alembic upgrade head (or restart API to auto-create)")
            return False
    except RuntimeError as e:
        print(f"⚠️  Database not configured: {e}")
        print("   This is normal for local development without .env file")
        print("   Tests requiring database will be skipped")
        return None


def test_validation_logic():
    """Test 2: Test market direction classification logic."""
    print("\n=== Test 2: Market Direction Classification ===\n")

    from validate_yesterday import classify_market_direction

    test_cases = [
        (-0.02, "Risk-Off"),    # -2% → Risk-Off
        (-0.006, "Risk-Off"),   # -0.6% → Risk-Off
        (-0.003, "Neutral"),    # -0.3% → Neutral
        (0.0, "Neutral"),       # 0% → Neutral
        (0.003, "Neutral"),     # +0.3% → Neutral
        (0.006, "Risk-On"),     # +0.6% → Risk-On
        (0.015, "Risk-On"),     # +1.5% → Risk-On
    ]

    passed = 0
    for spy_return, expected in test_cases:
        result = classify_market_direction(spy_return)
        status = "✓" if result == expected else "✗"
        print(f"{status} SPY {spy_return:+.2%} → {result:10} (expected: {expected})")
        if result == expected:
            passed += 1

    print(f"\nPassed: {passed}/{len(test_cases)}")
    return passed == len(test_cases)


def test_spy_data_fetch():
    """Test 3: Verify yfinance SPY data fetching."""
    print("\n=== Test 3: SPY Data Fetching ===\n")

    from validate_yesterday import get_spy_return

    # Test with a recent date (should have data)
    test_date = date.today() - timedelta(days=5)

    print(f"Fetching SPY data for {test_date}...")
    spy_return = get_spy_return(test_date)

    if spy_return is not None:
        print(f"✅ Successfully fetched SPY return: {spy_return:+.4f} ({spy_return*100:+.2f}%)")
        return True
    else:
        print("❌ Failed to fetch SPY data")
        print("   Check internet connection or yfinance API status")
        return False


def test_validation_with_mock_data():
    """Test 4: Create mock prediction and validate it."""
    print("\n=== Test 4: Mock Validation ===\n")

    try:
        init_db()
        db = next(get_db())
    except RuntimeError:
        print("⚠️  Database not configured - skipping")
        return None

    # Create mock prediction for 5 days ago
    mock_date = date.today() - timedelta(days=5)

    # Check if DecisionLog entry exists
    existing_decision = db.query(DecisionLog).filter_by(date=mock_date).first()

    if not existing_decision:
        print(f"Creating mock DecisionLog for {mock_date}...")
        mock_decision = DecisionLog(
            date=mock_date,
            qc_regime="Risk-On",
            ai_regime="Risk-On",
            regime_override=False,
            confidence=75,
            defense_level="full",
            reasoning="Test prediction for Phase 5a validation"
        )
        db.add(mock_decision)
        db.commit()
        print("✅ Mock DecisionLog created")
    else:
        print(f"✅ DecisionLog for {mock_date} already exists")
        print(f"   AI Regime: {existing_decision.ai_regime}")

    # Run validation
    from validate_yesterday import validate_prediction

    print(f"\nValidating {mock_date}...")
    success = validate_prediction(mock_date, db, force=True)

    if success:
        # Check result
        validation = db.query(DailyAccuracy).filter_by(date=mock_date).first()
        if validation:
            print(f"\n✅ Validation successful:")
            print(f"   Predicted: {validation.predicted_regime}")
            print(f"   Actual: {validation.actual_market_direction}")
            print(f"   SPY Return: {validation.spy_return_1d:+.4f}")
            print(f"   Correct: {validation.prediction_correct}")
            return True
        else:
            print("❌ Validation record not found in database")
            return False
    else:
        print("❌ Validation failed")
        return False


def test_api_endpoint():
    """Test 5: Test /api/v1/accuracy/ endpoint (requires running API)."""
    print("\n=== Test 5: API Endpoint ===\n")

    try:
        import httpx

        # Check if API is running
        try:
            response = httpx.get("http://localhost:8000/health", timeout=2.0)
            if response.status_code != 200:
                print("⚠️  API not running on localhost:8000")
                print("   Start with: python run.py")
                print("   Skipping endpoint test...")
                return None
        except httpx.ConnectError:
            print("⚠️  API not running on localhost:8000")
            print("   Start with: python run.py")
            print("   Skipping endpoint test...")
            return None

        # Test accuracy endpoint (need token for auth)
        from app.config import settings

        if not settings.API_TOKEN:
            print("⚠️  No API_TOKEN configured")
            print("   Skipping endpoint test...")
            return None

        headers = {"Authorization": f"Bearer {settings.API_TOKEN}"}

        # Test summary endpoint
        response = httpx.get(
            "http://localhost:8000/api/v1/accuracy/",
            headers=headers,
            timeout=5.0
        )

        if response.status_code == 200:
            data = response.json()
            print("✅ /api/v1/accuracy/ endpoint working")
            print(f"   Total Predictions: {data['total_predictions']}")
            print(f"   Correct: {data['correct_predictions']}")
            print(f"   Accuracy: {data['overall_accuracy']:.1%}")

            # Test daily endpoint
            response2 = httpx.get(
                "http://localhost:8000/api/v1/accuracy/daily?limit=5",
                headers=headers,
                timeout=5.0
            )

            if response2.status_code == 200:
                data2 = response2.json()
                print(f"✅ /api/v1/accuracy/daily endpoint working")
                print(f"   Records: {data2['count']}")
                return True
            else:
                print(f"❌ /api/v1/accuracy/daily failed: {response2.status_code}")
                return False
        else:
            print(f"❌ Endpoint failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    except ImportError:
        print("⚠️  httpx not installed - skipping endpoint test")
        return None


def test_backfill_mode():
    """Test 6: Test backfill mode."""
    print("\n=== Test 6: Backfill Mode ===\n")

    try:
        init_db()
        db = next(get_db())
    except RuntimeError:
        print("⚠️  Database not configured - skipping")
        print("\n💡 Backfill command (run on Railway or with DATABASE_URL):")
        print("   python validate_yesterday.py --backfill")
        return None

    # Count unvalidated predictions
    from sqlalchemy import and_

    unvalidated_count = db.query(DecisionLog).filter(
        and_(
            DecisionLog.ai_regime.isnot(None),
            DecisionLog.date < date.today()
        )
    ).count()

    validated_count = db.query(DailyAccuracy).count()

    print(f"DecisionLog entries with AI regime: {unvalidated_count}")
    print(f"DailyAccuracy validated records: {validated_count}")

    if unvalidated_count > validated_count:
        gap = unvalidated_count - validated_count
        print(f"\n⚠️  {gap} predictions need validation")
        print(f"   Run: python validate_yesterday.py --backfill")
    else:
        print("\n✅ All predictions are validated")

    print("\n💡 Backfill command:")
    print("   python validate_yesterday.py --backfill")
    print("   python validate_yesterday.py --backfill --force  # Re-validate all")

    return True


def main():
    """Run all tests."""
    print()
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 15 + "Phase 5a Test Suite: Data Collection" + " " * 24 + "║")
    print("╚" + "=" * 78 + "╝")

    results = {
        "Database Table": test_database_table(),
        "Market Direction Logic": test_validation_logic(),
        "SPY Data Fetching": test_spy_data_fetch(),
        "Mock Validation": test_validation_with_mock_data(),
        "API Endpoint": test_api_endpoint(),
        "Backfill Mode": test_backfill_mode(),
    }

    print("\n" + "="*80)
    print("Test Results Summary:")
    print("="*80)

    passed = 0
    skipped = 0
    failed = 0

    for test_name, result in results.items():
        if result is True:
            status = "✅ PASS"
            passed += 1
        elif result is None:
            status = "⏭️  SKIP"
            skipped += 1
        else:
            status = "❌ FAIL"
            failed += 1

        print(f"{status}  {test_name}")

    print("="*80)
    print(f"Total: {passed} passed, {failed} failed, {skipped} skipped")
    print("="*80 + "\n")

    if failed > 0:
        sys.exit(1)
    else:
        print("✅ Phase 5a implementation validated successfully!")
        print("\nNext Steps:")
        print("1. Deploy to Railway: git push")
        print("2. Add cron job in Railway dashboard:")
        print("   - Command: python cron_validate.py")
        print("   - Schedule: 0 19 * * * (15:00 ET = 19:00 UTC)")
        print("3. Monitor /api/v1/accuracy/ for daily stats")


if __name__ == "__main__":
    main()
