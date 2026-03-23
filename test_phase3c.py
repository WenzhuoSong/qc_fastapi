"""
Test Phase 3c: Regime Transition Detection & Pivot Signal Generation

Tests transition probability calculation, pivot signal generation,
and early warning detection.
"""

from app.pipeline.regime_transition import (
    detect_regime_transition,
    generate_pivot_signals,
    analyze_confidence_trend,
)


def test_pivot_signal_generation():
    """Test pivot signal generation for different regimes."""
    print("\n=== Test 1: Pivot Signal Generation ===\n")

    # Test Risk-Off with oil events
    print("Scenario: Risk-Off with oil crisis")
    signals = generate_pivot_signals(
        regime="Risk-Off",
        net_escalation=0.65,
        regime_phase="Risk-Off Peak",
        key_events=[
            "Oil prices surge on Middle East tensions",
            "Iran threatens shipping lanes",
        ],
    )
    print(f"Generated {len(signals)} pivot signals:")
    for sig in signals:
        print(f"  {sig.status:8} | {sig.signal}")
    print()

    # Test Risk-Off with de-escalation
    print("Scenario: Risk-Off with de-escalation signals")
    signals = generate_pivot_signals(
        regime="Risk-Off",
        net_escalation=0.45,
        regime_phase="Risk-Off Fading",
        key_events=[
            "G7 backs security measures",
            "Gas exports resume after halt",
        ],
    )
    print(f"Generated {len(signals)} pivot signals:")
    for sig in signals:
        print(f"  {sig.status:8} | {sig.signal}")
    met_count = sum(1 for s in signals if s.status == "met")
    print(f"Met signals: {met_count}/{len(signals)}")


def test_confidence_trend_analysis():
    """Test confidence trend detection."""
    print("\n=== Test 2: Confidence Trend Analysis ===\n")

    test_cases = [
        ([70, 75, 80, 85], "rising"),
        ([85, 80, 75, 70], "falling"),
        ([80, 80, 80, 80], "stable"),
        ([70, 85, 60, 90], "volatile"),
        ([80, 75, 78], "stable"),
    ]

    for history, expected in test_cases:
        trend = analyze_confidence_trend(history)
        status = "✓" if trend == expected else "✗"
        print(f"{status} {history} → {trend} (expected: {expected})")


def test_transition_detection_peak_to_fading():
    """Test transition detection: Peak → Fading."""
    print("\n=== Test 3: Peak → Fading Transition ===\n")

    # Scenario: Risk-Off Peak with 2 pivot signals met, escalation declining
    result = detect_regime_transition(
        regime="Risk-Off",
        regime_phase="Risk-Off Peak (first signs of deceleration)",
        net_escalation=0.46,
        previous_net_escalation=0.75,
        confidence=70,
        confidence_history=[80, 85, 80, 75, 70],
        key_events=[
            "UK submarine deployed to region",
            "Iran threatens energy facilities",
            "G7 backs security measures",  # De-escalation signal
            "Gas exports resume",           # De-escalation signal
        ],
    )

    print(f"Transition Probability: {result.transition_probability:.0%}")
    print(f"Direction: {result.direction}")
    print(f"Confidence Trend: {result.confidence_trend}")
    print(f"Early Warning: {result.early_warning}")
    print()
    print("Pivot Signals:")
    for sig in result.pivot_signals:
        print(f"  {sig.status:8} | {sig.signal}")
    print()
    print(f"Recommendation:\n{result.recommendation}")

    # Validation
    print()
    checks = [
        (result.transition_probability >= 0.25,
         f"Transition probability elevated: {result.transition_probability:.0%}"),
        ("Fading" in result.direction if result.direction else False,
         f"Direction indicates Fading: '{result.direction}'"),
        (result.confidence_trend == "falling",
         f"Confidence trend detected as falling: {result.confidence_trend}"),
    ]

    for passed, message in checks:
        status = "✓" if passed else "✗"
        print(f"{status} {message}")


def test_transition_detection_fading_to_recovery():
    """Test transition detection: Fading → Recovery."""
    print("\n=== Test 4: Fading → Recovery Transition ===\n")

    # Scenario: Risk-Off Fading with multiple pivot signals met
    result = detect_regime_transition(
        regime="Risk-Off",
        regime_phase="Risk-Off Fading",
        net_escalation=0.15,
        previous_net_escalation=0.45,
        confidence=65,
        confidence_history=[75, 70, 68, 66, 65],
        key_events=[
            "Tensions ease as talks progress",
            "Oil prices stabilize",
            "G7 security measures showing effect",
        ],
    )

    print(f"Transition Probability: {result.transition_probability:.0%}")
    print(f"Direction: {result.direction}")
    print(f"Early Warning: {result.early_warning}")
    print()
    print(f"Recommendation:\n{result.recommendation}")

    # Validation
    print()
    checks = [
        (result.transition_probability >= 0.30,
         f"High transition probability: {result.transition_probability:.0%}"),
        ("Recovery" in result.direction if result.direction else False,
         f"Direction indicates Recovery: '{result.direction}'"),
        (result.early_warning,
         f"Early warning triggered: {result.early_warning}"),
    ]

    for passed, message in checks:
        status = "✓" if passed else "✗"
        print(f"{status} {message}")


def test_transition_detection_stable_regime():
    """Test transition detection: Stable Risk-Off."""
    print("\n=== Test 5: Stable Risk-Off (No Transition) ===\n")

    # Scenario: Risk-Off Building with no pivot signals
    result = detect_regime_transition(
        regime="Risk-Off",
        regime_phase="Risk-Off Building",
        net_escalation=0.70,
        previous_net_escalation=0.65,
        confidence=85,
        confidence_history=[80, 82, 84, 85, 85],
        key_events=[
            "War escalates further",
            "Oil supply disruption worsens",
        ],
    )

    print(f"Transition Probability: {result.transition_probability:.0%}")
    print(f"Direction: {result.direction}")
    print(f"Early Warning: {result.early_warning}")
    print()
    print(f"Recommendation:\n{result.recommendation}")

    # Validation
    print()
    checks = [
        (result.transition_probability <= 0.15,
         f"Low transition probability: {result.transition_probability:.0%}"),
        (not result.early_warning,
         f"No early warning: {result.early_warning}"),
        ("Maintain" in result.recommendation or "Strengthen" in result.recommendation,
         "Recommendation suggests maintaining positions"),
    ]

    for passed, message in checks:
        status = "✓" if passed else "✗"
        print(f"{status} {message}")


def test_transition_detection_neutral_to_risk_off():
    """Test transition detection: Neutral → Risk-Off."""
    print("\n=== Test 6: Neutral → Risk-Off Transition ===\n")

    # Scenario: Neutral regime with clear escalation signals
    result = detect_regime_transition(
        regime="Neutral",
        regime_phase="Neutral Tilting Risk-Off",
        net_escalation=0.55,
        previous_net_escalation=0.30,
        confidence=70,
        confidence_history=[65, 68, 70, 70, 70],
        key_events=[
            "Sudden escalation in Middle East",
            "Market volatility spikes",
        ],
    )

    print(f"Transition Probability: {result.transition_probability:.0%}")
    print(f"Direction: {result.direction}")
    print(f"Early Warning: {result.early_warning}")
    print()
    print(f"Recommendation:\n{result.recommendation}")

    # Validation
    print()
    checks = [
        (result.transition_probability >= 0.35,
         f"High transition probability: {result.transition_probability:.0%}"),
        ("Risk-Off" in result.direction if result.direction else False,
         f"Direction indicates Risk-Off: '{result.direction}'"),
        (result.early_warning,
         f"Early warning triggered: {result.early_warning}"),
        ("Rotate to defensive" in result.recommendation,
         "Recommendation suggests rotation to defensive"),
    ]

    for passed, message in checks:
        status = "✓" if passed else "✗"
        print(f"{status} {message}")


def main():
    """Run all tests."""
    print()
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 10 + "Phase 3c Test Suite: Regime Transition Detection" + " " * 18 + "║")
    print("╚" + "=" * 78 + "╝")

    test_pivot_signal_generation()
    test_confidence_trend_analysis()
    test_transition_detection_peak_to_fading()
    test_transition_detection_fading_to_recovery()
    test_transition_detection_stable_regime()
    test_transition_detection_neutral_to_risk_off()

    print()
    print("=" * 80)
    print("Test Suite Complete")
    print("=" * 80)


if __name__ == "__main__":
    main()
