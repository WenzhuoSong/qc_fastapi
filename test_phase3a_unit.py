"""
Unit Test: Phase 3a Integration with Step1Output

Tests that Phase 3a properly integrates with Step1Output model
without requiring OpenAI API calls.
"""

from app.pipeline.step1_macro import Step1Output
from app.pipeline.event_direction import analyze_event_directions


def test_step1_output_schema():
    """Test that Step1Output includes Phase 3a fields."""
    print("=" * 80)
    print("Test: Step1Output Schema Validation")
    print("=" * 80)
    print()

    # Create a mock Step1Output with Phase 3a fields
    output = Step1Output(
        regime="Risk-Off",
        confidence=75,
        summary="Mixed signals with escalation and de-escalation events",
        key_events=[
            "Military deployment in region",
            "Oil supply concerns escalate",
            "G7 backs security measures",
        ],
        reasoning="Multiple events show both escalation and stabilization efforts",
        transmission_vector={"XLE": 0.85, "XLY": -0.60},
        net_escalation_score=0.45,
        regime_phase="Risk-Off Peak (first signs of deceleration)",
        event_direction_reasoning="3 events: 2 escalation, 1 de-escalation",
    )

    # Verify all fields are accessible
    checks = [
        (hasattr(output, "regime"), "Has 'regime' field"),
        (hasattr(output, "confidence"), "Has 'confidence' field"),
        (hasattr(output, "key_events"), "Has 'key_events' field"),
        (hasattr(output, "transmission_vector"), "Has 'transmission_vector' field (Phase 2)"),
        (hasattr(output, "net_escalation_score"), "Has 'net_escalation_score' field (Phase 3a)"),
        (hasattr(output, "regime_phase"), "Has 'regime_phase' field (Phase 3a)"),
        (hasattr(output, "event_direction_reasoning"), "Has 'event_direction_reasoning' field (Phase 3a)"),
    ]

    all_passed = True
    for passed, message in checks:
        status = "✓" if passed else "✗"
        print(f"{status} {message}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("✓ All schema fields present")
    else:
        print("✗ Some schema fields missing")

    print()
    print("Sample output:")
    print(f"  Regime: {output.regime}")
    print(f"  Confidence: {output.confidence}")
    print(f"  Net Escalation: {output.net_escalation_score}")
    print(f"  Regime Phase: {output.regime_phase}")

    return all_passed


def test_event_direction_analysis_standalone():
    """Test event direction analysis as standalone function."""
    print()
    print("=" * 80)
    print("Test: Event Direction Analysis (Standalone)")
    print("=" * 80)
    print()

    # 2026-03-20 scenario: 4 escalation + 1 de-escalation
    key_events = [
        "UK submarine deployed to Red Sea amid escalating tensions",
        "Saudi Arabia expels Iranian diplomats over oil blockade threats",
        "Oil hits $200 amid fears Iran threatens Strait of Hormuz closure",
        "Israel-Iran conflict risks broader Middle East war",
        "Iranian gas exports to Europe resume after G7 pressure",
    ]

    # Simulate previous day with higher escalation
    previous_net_escalation = 0.75

    print(f"Input: {len(key_events)} events")
    print("Previous day net escalation: 0.75")
    print()

    # Run analysis
    result = analyze_event_directions(
        key_events=key_events,
        regime="Risk-Off",
        confidence=80,
        previous_net_escalation=previous_net_escalation,
    )

    print("Output:")
    print(f"  Net Escalation Score: {result.net_escalation_score:.2f}")
    print(f"  Regime Phase: {result.regime_phase}")
    print(f"  Confidence Adjustment: {result.confidence_adjustment:+d}")
    print()

    print("Event Classification:")
    for event in result.key_events_tagged:
        print(f"  {event.direction:12} (w={event.weight:.2f}): {event.event[:60]}")

    print()
    print(f"Reasoning: {result.reasoning}")

    # Validation
    print()
    checks = [
        (0.3 < result.net_escalation_score < 0.7,
         f"Net escalation in range (0.3-0.7): {result.net_escalation_score:.2f}"),
        (result.net_escalation_score < previous_net_escalation,
         f"Escalation decelerating: {result.net_escalation_score:.2f} < {previous_net_escalation:.2f}"),
        ("Peak" in result.regime_phase or "deceleration" in result.regime_phase,
         f"Phase detects deceleration: '{result.regime_phase}'"),
        (result.confidence_adjustment < 0,
         f"Confidence lowered due to mixed signals: {result.confidence_adjustment:+d}"),
    ]

    all_passed = True
    for passed, message in checks:
        status = "✓" if passed else "✗"
        print(f"{status} {message}")
        if not passed:
            all_passed = False

    return all_passed


def test_integration_full_flow():
    """Test the full integration flow: key_events → analysis → Step1Output."""
    print()
    print("=" * 80)
    print("Test: Full Integration Flow")
    print("=" * 80)
    print()

    # Step 1: Start with key events
    key_events = [
        "Oil prices surge on Middle East tensions",
        "Iran threatens shipping lanes",
        "G7 announces security convoy plan",
    ]

    print("Step 1: Key Events")
    for i, event in enumerate(key_events, 1):
        print(f"  {i}. {event}")
    print()

    # Step 2: Analyze event directions
    print("Step 2: Run Event Direction Analysis")
    analysis = analyze_event_directions(
        key_events=key_events,
        regime="Risk-Off",
        confidence=75,
        previous_net_escalation=0.60,
    )
    print(f"  → Net escalation: {analysis.net_escalation_score:.2f}")
    print(f"  → Phase: {analysis.regime_phase}")
    print()

    # Step 3: Create Step1Output with analysis results
    print("Step 3: Populate Step1Output")
    step1_output = Step1Output(
        regime="Risk-Off",
        confidence=75 + analysis.confidence_adjustment,  # Apply adjustment
        summary="Oil tensions with G7 intervention attempts",
        key_events=key_events,
        reasoning="Supply shock concerns balanced by diplomatic efforts",
        transmission_vector={"XLE": 0.85, "XLY": -0.60},
        net_escalation_score=analysis.net_escalation_score,
        regime_phase=analysis.regime_phase,
        event_direction_reasoning=analysis.reasoning,
    )
    print(f"  ✓ Regime: {step1_output.regime}")
    print(f"  ✓ Confidence: {step1_output.confidence} (adjusted from 75)")
    print(f"  ✓ Net Escalation: {step1_output.net_escalation_score}")
    print(f"  ✓ Regime Phase: {step1_output.regime_phase}")
    print()

    # Step 4: Verify JSON serialization (for API response)
    print("Step 4: JSON Serialization (for API)")
    output_dict = step1_output.model_dump()
    required_fields = [
        "regime", "confidence", "key_events",
        "transmission_vector",
        "net_escalation_score", "regime_phase", "event_direction_reasoning"
    ]

    all_present = all(field in output_dict for field in required_fields)
    if all_present:
        print("  ✓ All required fields present in JSON output")
    else:
        print("  ✗ Some fields missing from JSON output")

    print()
    print("Sample JSON keys:", list(output_dict.keys()))

    return all_present


def main():
    """Run all unit tests."""
    print()
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "Phase 3a Unit Test Suite" + " " * 34 + "║")
    print("╚" + "=" * 78 + "╝")
    print()

    results = []

    results.append(("Schema Validation", test_step1_output_schema()))
    results.append(("Event Direction Analysis", test_event_direction_analysis_standalone()))
    results.append(("Full Integration Flow", test_integration_full_flow()))

    print()
    print("=" * 80)
    print("Test Summary")
    print("=" * 80)
    print()

    total = len(results)
    passed = sum(1 for _, result in results if result)

    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status:8} {name}")

    print()
    print(f"Result: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests PASSED!")
        return 0
    else:
        print("⚠️  Some tests FAILED")
        return 1


if __name__ == "__main__":
    exit(main())
