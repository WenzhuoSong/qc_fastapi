"""
Test Phase 3a: Event Direction Analysis & Signal Contradictions

Tests the 2026-03-20 scenario: 4 escalation + 1 de-escalation events.
Expected outcome: Confidence should reflect contradictions, regime phase should be "Peak".
"""

import asyncio
from app.pipeline.event_direction import (
    analyze_event_directions,
    classify_event_direction,
    calculate_net_escalation,
    calculate_confidence_adjustment,
    EventWithDirection,
)


def test_classify_event_direction():
    """Test individual event classification."""
    print("\n=== Test 1: Event Classification ===\n")

    test_cases = [
        # Escalation events
        ("Iran threatens military action against shipping", "escalation"),
        ("Oil prices surge on supply disruption fears", "escalation"),
        ("Missile strike escalates Middle East tensions", "escalation"),
        ("Sanctions deepen as conflict worsens", "escalation"),

        # De-escalation events
        ("G7 backs maritime security convoy plan", "de-escalation"),
        ("Iranian gas exports resume after brief halt", "de-escalation"),
        ("Ceasefire negotiations begin in Geneva", "de-escalation"),

        # Neutral events
        ("Markets monitor developments", "neutral"),
        ("Analysts assess situation", "neutral"),
    ]

    for event, expected_direction in test_cases:
        direction, weight = classify_event_direction(event)
        status = "✓" if direction == expected_direction else "✗"
        print(f"{status} '{event[:60]}'")
        print(f"   → {direction} (weight: {weight:.2f}, expected: {expected_direction})\n")


def test_net_escalation_calculation():
    """Test net escalation score calculation."""
    print("\n=== Test 2: Net Escalation Score ===\n")

    # Scenario 1: Pure escalation
    pure_escalation = [
        EventWithDirection(event="attack", direction="escalation", weight=0.8),
        EventWithDirection(event="bombing", direction="escalation", weight=0.8),
        EventWithDirection(event="war", direction="escalation", weight=0.8),
    ]
    score1 = calculate_net_escalation(pure_escalation)
    print(f"Pure escalation (3 events, weight=0.8): {score1:.2f} (expected: ~0.80)")

    # Scenario 2: Mixed signals (2026-03-20 case)
    mixed_signals = [
        EventWithDirection(event="military strike", direction="escalation", weight=0.8),
        EventWithDirection(event="crisis deepens", direction="escalation", weight=0.7),
        EventWithDirection(event="sanctions imposed", direction="escalation", weight=0.7),
        EventWithDirection(event="conflict escalates", direction="escalation", weight=0.8),
        EventWithDirection(event="talks resume", direction="de-escalation", weight=0.4),
    ]
    score2 = calculate_net_escalation(mixed_signals)
    print(f"Mixed signals (4 escalation + 1 de-escalation): {score2:.2f} (expected: ~0.52)")

    # Scenario 3: Balanced
    balanced = [
        EventWithDirection(event="attack", direction="escalation", weight=0.6),
        EventWithDirection(event="ceasefire", direction="de-escalation", weight=0.6),
    ]
    score3 = calculate_net_escalation(balanced)
    print(f"Balanced (1 escalation + 1 de-escalation): {score3:.2f} (expected: 0.00)")

    # Scenario 4: Pure de-escalation
    pure_deescalation = [
        EventWithDirection(event="peace talks", direction="de-escalation", weight=0.7),
        EventWithDirection(event="troops withdraw", direction="de-escalation", weight=0.6),
    ]
    score4 = calculate_net_escalation(pure_deescalation)
    print(f"Pure de-escalation (2 events): {score4:.2f} (expected: ~-0.65)")


def test_full_analysis_2026_03_20():
    """Test full analysis for 2026-03-20 scenario."""
    print("\n=== Test 3: Full Analysis (2026-03-20 Scenario) ===\n")

    # 2026-03-20: 4 escalation + 1 de-escalation events
    key_events = [
        "UK submarine deployed to Red Sea amid escalating tensions",
        "Saudi Arabia expels Iranian diplomats over oil blockade threats",
        "Oil hits $200 amid fears Iran threatens Strait of Hormuz closure",
        "Israel-Iran conflict risks broader Middle East war",
        "Iranian gas exports to Europe resume after G7 pressure",
    ]

    # Simulate previous day (2026-03-19) with higher escalation
    previous_net_escalation = 0.75  # Pure escalation day

    result = analyze_event_directions(
        key_events=key_events,
        regime="Risk-Off",
        confidence=80,
        previous_net_escalation=previous_net_escalation,
    )

    print(f"Net escalation score: {result.net_escalation_score:.2f}")
    print(f"Regime phase: {result.regime_phase}")
    print(f"Confidence adjustment: {result.confidence_adjustment:+d}")
    print(f"\nReasoning: {result.reasoning}")

    print("\nTagged events:")
    for event in result.key_events_tagged:
        print(f"  {event.direction:12} (w={event.weight:.2f}): {event.event}")

    # Assertions
    print("\n--- Validation Checks ---")
    checks = [
        (result.net_escalation_score > 0.4 and result.net_escalation_score < 0.7,
         f"Net escalation in expected range (0.4-0.7): {result.net_escalation_score:.2f}"),

        (result.net_escalation_score < previous_net_escalation,
         f"Escalation decelerating: {result.net_escalation_score:.2f} < {previous_net_escalation:.2f}"),

        ("Peak" in result.regime_phase or "deceleration" in result.regime_phase,
         f"Phase detects deceleration: '{result.regime_phase}'"),

        (result.confidence_adjustment < 0,
         f"Confidence lowered due to contradictions: {result.confidence_adjustment:+d}"),
    ]

    for passed, message in checks:
        status = "✓" if passed else "✗"
        print(f"{status} {message}")


def test_confidence_adjustment_scenarios():
    """Test confidence adjustment in various scenarios."""
    print("\n=== Test 4: Confidence Adjustment Scenarios ===\n")

    scenarios = [
        # Scenario 1: Strong contradictions (40% minority)
        {
            "name": "Strong contradiction (40% de-escalation)",
            "events": [
                EventWithDirection(event="e1", direction="escalation", weight=0.8),
                EventWithDirection(event="e2", direction="escalation", weight=0.8),
                EventWithDirection(event="e3", direction="escalation", weight=0.8),
                EventWithDirection(event="d1", direction="de-escalation", weight=0.5),
                EventWithDirection(event="d2", direction="de-escalation", weight=0.5),
            ],
            "expected_adjustment": -15,
        },
        # Scenario 2: Minor contradictions (10% minority)
        {
            "name": "Minor contradiction (10% de-escalation)",
            "events": [
                EventWithDirection(event="e1", direction="escalation", weight=0.8),
                EventWithDirection(event="e2", direction="escalation", weight=0.8),
                EventWithDirection(event="e3", direction="escalation", weight=0.8),
                EventWithDirection(event="e4", direction="escalation", weight=0.8),
                EventWithDirection(event="e5", direction="escalation", weight=0.8),
                EventWithDirection(event="e6", direction="escalation", weight=0.8),
                EventWithDirection(event="e7", direction="escalation", weight=0.8),
                EventWithDirection(event="e8", direction="escalation", weight=0.8),
                EventWithDirection(event="e9", direction="escalation", weight=0.8),
                EventWithDirection(event="d1", direction="de-escalation", weight=0.5),
            ],
            "expected_adjustment": -5,
        },
        # Scenario 3: Pure escalation
        {
            "name": "Pure escalation (no contradictions)",
            "events": [
                EventWithDirection(event="e1", direction="escalation", weight=0.8),
                EventWithDirection(event="e2", direction="escalation", weight=0.8),
                EventWithDirection(event="e3", direction="escalation", weight=0.8),
            ],
            "expected_adjustment": +5,
        },
        # Scenario 4: Too many neutral events
        {
            "name": "Weak signal clarity (60% neutral)",
            "events": [
                EventWithDirection(event="e1", direction="escalation", weight=0.8),
                EventWithDirection(event="n1", direction="neutral", weight=0.3),
                EventWithDirection(event="n2", direction="neutral", weight=0.3),
                EventWithDirection(event="n3", direction="neutral", weight=0.3),
                EventWithDirection(event="n4", direction="neutral", weight=0.3),
            ],
            "expected_adjustment": -10,
        },
    ]

    for scenario in scenarios:
        net_escalation = calculate_net_escalation(scenario["events"])
        adjustment, reasoning = calculate_confidence_adjustment(
            events=scenario["events"],
            net_escalation=net_escalation,
            base_confidence=80,
        )

        status = "✓" if adjustment == scenario["expected_adjustment"] else "✗"
        print(f"{status} {scenario['name']}")
        print(f"   Net escalation: {net_escalation:.2f}")
        print(f"   Adjustment: {adjustment:+d} (expected: {scenario['expected_adjustment']:+d})")
        print(f"   Reasoning: {reasoning[:100]}...\n")


async def main():
    """Run all tests."""
    print("=" * 80)
    print(" Phase 3a Test Suite: Event Direction Analysis & Signal Contradictions")
    print("=" * 80)

    test_classify_event_direction()
    test_net_escalation_calculation()
    test_full_analysis_2026_03_20()
    test_confidence_adjustment_scenarios()

    print("\n" + "=" * 80)
    print(" Test Suite Complete")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
