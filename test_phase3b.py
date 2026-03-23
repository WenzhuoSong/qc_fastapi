"""
Test Phase 3b: Duration Estimation & Exit Strategy

Tests duration classification, exit strategy generation, and tactical implications.
"""

from app.pipeline.duration_estimation import (
    classify_event_duration,
    aggregate_duration_signals,
    DurationSignal,
)


def test_duration_classification():
    """Test individual event duration classification."""
    print("\n=== Test 1: Duration Classification ===\n")

    test_cases = [
        # Short-term events
        ("G7 backs maritime security convoy plan", "short_term"),
        ("Emergency meeting scheduled for tomorrow", "short_term"),
        ("Temporary halt in operations", "short_term"),

        # Medium-term events
        ("Structural changes needed in supply chain", "medium_term"),
        ("Iran situation beyond control, prolonged conflict expected", "medium_term"),
        ("Policy adjustment period required", "medium_term"),

        # Long-term events
        ("New cold war paradigm shift in global relations", "long_term"),
        ("Permanent decoupling from China", "long_term"),
        ("Fundamental regime change in energy markets", "long_term"),
    ]

    for event, expected_category in test_cases:
        signal = classify_event_duration(event, reasoning="")
        status = "✓" if signal.category == expected_category else "✗"
        print(f"{status} '{event[:60]}'")
        print(f"   → {signal.category} (confidence: {signal.confidence}, expected: {expected_category})")
        if signal.key_indicators:
            print(f"   Indicators: {', '.join(signal.key_indicators[:2])}")
        print()


def test_aggregate_duration_short_term():
    """Test aggregation for short-term events."""
    print("\n=== Test 2: Short-Term Duration (G7 Intervention) ===\n")

    events = [
        "G7 backs maritime security convoy",
        "Emergency stabilization measures announced",
        "Temporary disruption expected to normalize in weeks",
    ]

    result = aggregate_duration_signals(
        key_events=events,
        reasoning="International intervention to stabilize situation",
        regime="Risk-Off",
    )

    print(f"Primary Duration: {result.primary_duration}")
    print(f"Category: {result.category}")
    print(f"Confidence: {result.confidence}")
    print()
    print(f"Exit Strategy:\n{result.exit_strategy}")
    print()
    print("Tactical Implications:")
    for impl in result.tactical_implications:
        print(f"  - {impl}")

    # Validation
    print()
    checks = [
        (result.category == "short_term", f"Category is short_term: {result.category}"),
        ("1-2 weeks" in result.primary_duration.lower() or "temporary" in result.primary_duration.lower(),
         f"Duration mentions short timeframe: '{result.primary_duration}'"),
        ("8-10%" in result.exit_strategy or "aggressive" in result.exit_strategy.lower(),
         "Exit strategy mentions aggressive profit-taking"),
    ]

    for passed, message in checks:
        status = "✓" if passed else "✗"
        print(f"{status} {message}")


def test_aggregate_duration_medium_term():
    """Test aggregation for medium-term events."""
    print("\n=== Test 3: Medium-Term Duration (Prolonged Conflict) ===\n")

    events = [
        "Iran situation beyond control",
        "Structural supply chain disruption",
        "Extended conflict expected, negotiations ongoing",
    ]

    result = aggregate_duration_signals(
        key_events=events,
        reasoning="Prolonged geopolitical tension requires policy changes",
        regime="Risk-Off",
    )

    print(f"Primary Duration: {result.primary_duration}")
    print(f"Category: {result.category}")
    print(f"Confidence: {result.confidence}")
    print()
    print(f"Exit Strategy:\n{result.exit_strategy}")
    print()
    print("Tactical Implications:")
    for impl in result.tactical_implications:
        print(f"  - {impl}")

    # Validation
    print()
    checks = [
        (result.category == "medium_term", f"Category is medium_term: {result.category}"),
        ("1-2 months" in result.primary_duration.lower() or "prolonged" in result.primary_duration.lower(),
         f"Duration mentions medium timeframe: '{result.primary_duration}'"),
        ("12-15%" in result.exit_strategy or "moderate" in result.exit_strategy.lower(),
         "Exit strategy mentions moderate holding period"),
    ]

    for passed, message in checks:
        status = "✓" if passed else "✗"
        print(f"{status} {message}")


def test_aggregate_duration_long_term():
    """Test aggregation for long-term events."""
    print("\n=== Test 4: Long-Term Duration (Paradigm Shift) ===\n")

    events = [
        "New cold war paradigm shift",
        "Permanent decoupling from China",
        "Fundamental regime change in energy markets",
    ]

    result = aggregate_duration_signals(
        key_events=events,
        reasoning="Structural shift in global order, new normal emerging",
        regime="Risk-Off",
    )

    print(f"Primary Duration: {result.primary_duration}")
    print(f"Category: {result.category}")
    print(f"Confidence: {result.confidence}")
    print()
    print(f"Exit Strategy:\n{result.exit_strategy}")
    print()
    print("Tactical Implications:")
    for impl in result.tactical_implications:
        print(f"  - {impl}")

    # Validation
    print()
    checks = [
        (result.category == "long_term", f"Category is long_term: {result.category}"),
        ("indefinite" in result.primary_duration.lower() or "structural" in result.primary_duration.lower(),
         f"Duration mentions indefinite timeframe: '{result.primary_duration}'"),
        ("16-20%" in result.exit_strategy or "strategic" in result.exit_strategy.lower(),
         "Exit strategy mentions strategic reallocation"),
    ]

    for passed, message in checks:
        status = "✓" if passed else "✗"
        print(f"{status} {message}")


def test_mixed_duration_signals():
    """Test handling of mixed duration signals."""
    print("\n=== Test 5: Mixed Duration Signals ===\n")

    # Mix of short and medium-term signals
    events = [
        "G7 emergency intervention (short-term)",
        "Structural supply issues (medium-term)",
        "Temporary stabilization measures (short-term)",
    ]

    result = aggregate_duration_signals(
        key_events=events,
        reasoning="Mixed signals: immediate stabilization but underlying structural issues",
        regime="Risk-Off",
    )

    print(f"Primary Duration: {result.primary_duration}")
    print(f"Category: {result.category}")
    print(f"Confidence: {result.confidence}")
    print()
    print(f"Exit Strategy:\n{result.exit_strategy}")

    # Validation
    print()
    checks = [
        (result.category in ["short_term", "medium_term"],
         f"Category is short or medium: {result.category}"),
        ("2-4 weeks" in result.primary_duration.lower() or "lingering" in result.primary_duration.lower(),
         f"Duration reflects mixed signals: '{result.primary_duration}'"),
    ]

    for passed, message in checks:
        status = "✓" if passed else "✗"
        print(f"{status} {message}")


def test_regime_specific_exit_strategies():
    """Test that exit strategies vary by regime."""
    print("\n=== Test 6: Regime-Specific Exit Strategies ===\n")

    events = ["Prolonged conflict expected"]

    # Test Risk-Off
    result_off = aggregate_duration_signals(
        key_events=events,
        reasoning="Risk-off environment",
        regime="Risk-Off",
    )

    # Test Risk-On
    result_on = aggregate_duration_signals(
        key_events=events,
        reasoning="Risk-on environment",
        regime="Risk-On",
    )

    print("Risk-Off Exit Strategy:")
    print(f"  {result_off.exit_strategy[:100]}...")
    print()
    print("Risk-On Exit Strategy:")
    print(f"  {result_on.exit_strategy[:100]}...")

    # Validation
    print()
    checks = [
        ("defensive" in result_off.exit_strategy.lower() or "XLP" in result_off.exit_strategy,
         "Risk-Off mentions defensive sectors"),
        ("growth" in result_on.exit_strategy.lower() or "XLK" in result_on.exit_strategy,
         "Risk-On mentions growth sectors"),
        (result_off.tactical_implications != result_on.tactical_implications,
         "Tactical implications differ by regime"),
    ]

    for passed, message in checks:
        status = "✓" if passed else "✗"
        print(f"{status} {message}")


def main():
    """Run all tests."""
    print()
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 15 + "Phase 3b Test Suite: Duration Estimation" + " " * 23 + "║")
    print("╚" + "=" * 78 + "╝")

    test_duration_classification()
    test_aggregate_duration_short_term()
    test_aggregate_duration_medium_term()
    test_aggregate_duration_long_term()
    test_mixed_duration_signals()
    test_regime_specific_exit_strategies()

    print()
    print("=" * 80)
    print("Test Suite Complete")
    print("=" * 80)


if __name__ == "__main__":
    main()
