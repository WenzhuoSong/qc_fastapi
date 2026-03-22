"""
Phase 2 Week 1 - Manual Testing Script

Interactive tests for transmission_rules.py without requiring pytest.
Run scenarios based on real historical events to validate pattern matching.

Usage:
    python test_phase2_manual.py
"""

from app.pipeline.transmission_rules import (
    match_event_to_pattern,
    detect_event_type,
    format_transmission_context,
    CANONICAL_TRANSMISSIONS,
)


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def test_pattern_definitions():
    """Test 1: Validate canonical pattern definitions."""
    print_section("Test 1: Canonical Pattern Definitions")

    print(f"\nTotal patterns defined: {len(CANONICAL_TRANSMISSIONS)}")

    for pattern_name, pattern_def in CANONICAL_TRANSMISSIONS.items():
        print(f"\n📋 {pattern_name}")
        print(f"   Description: {pattern_def['description']}")
        print(f"   Keywords: {len(pattern_def['keywords'])} keywords")

        # Check sector coverage
        vector = pattern_def["vector"]
        if len(vector) != 11:
            print(f"   ⚠️  WARNING: Only {len(vector)} sectors defined (expected 11)")
        else:
            print(f"   ✓ All 11 sectors defined")

        # Check value ranges
        invalid = [
            (s, v) for s, v in vector.items()
            if v < -1.0 or v > 1.0
        ]
        if invalid:
            print(f"   ⚠️  WARNING: Invalid values: {invalid}")
        else:
            print(f"   ✓ All values in valid range [-1.0, 1.0]")

        # Show top winners/losers
        sorted_sectors = sorted(vector.items(), key=lambda x: -x[1])
        print(f"   Top 3 winners: {', '.join(f'{s}={v:.2f}' for s, v in sorted_sectors[:3])}")
        print(f"   Top 3 losers: {', '.join(f'{s}={v:.2f}' for s, v in sorted_sectors[-3:])}")


def test_historical_scenario_2026_03_20():
    """Test 2: 2026-03-20 Iran war + oil crisis scenario."""
    print_section("Test 2: Historical Scenario - 2026-03-20 (Iran War)")

    # Actual key_events from 2026-03-20 pipeline
    key_events = [
        "Iran war escalation",
        "Strait of Hormuz threatened",
        "Oil supply disruption concerns"
    ]
    reasoning = (
        "Military tensions in the Middle East have escalated with Iran threatening "
        "to close the Strait of Hormuz, a critical chokepoint for global oil shipments. "
        "This has created severe oil supply disruption fears, with crude prices surging "
        "toward $200/barrel. Defense contractors are benefiting from increased military "
        "spending, while consumer sectors face demand destruction from high energy costs."
    )

    print(f"\nInput:")
    print(f"  Key Events: {key_events}")
    print(f"  Reasoning: {reasoning[:150]}...")

    # Test pattern matching
    transmission = match_event_to_pattern(key_events, reasoning)

    print(f"\nMatched Transmission Vector:")
    if not transmission:
        print("  ❌ No pattern matched!")
        return

    # Sort by absolute strength
    sorted_sectors = sorted(
        transmission.items(),
        key=lambda x: -abs(x[1])
    )

    print(f"\n  Top Beneficiaries:")
    for sector, strength in sorted_sectors[:5]:
        if strength > 0:
            print(f"    {sector}: +{strength:.2f}")

    print(f"\n  Top Victims:")
    for sector, strength in reversed(sorted_sectors[-5:]):
        if strength < 0:
            print(f"    {sector}: {strength:.2f}")

    # Validate expected results
    print(f"\n  Validation:")
    assertions = [
        ("XLE should be strong winner", transmission.get("XLE", 0) > 0.8),
        ("XLY should be strong loser", transmission.get("XLY", 0) < -0.5),
        ("XLI should benefit (defense)", transmission.get("XLI", 0) > 0.5),
        ("XLK should be hurt (growth)", transmission.get("XLK", 0) < -0.3),
    ]

    for description, passed in assertions:
        status = "✓" if passed else "✗"
        print(f"    {status} {description}")

    # Test event type detection
    event_type = detect_event_type(key_events, reasoning)
    print(f"\n  Detected Event Type: {event_type}")

    # Test formatting
    formatted = format_transmission_context(transmission)
    print(f"\n  Formatted Context (for Step 2 prompt):")
    print("  " + "\n  ".join(formatted.split("\n")[:10]))


def test_rate_shock_scenario():
    """Test 3: Fed hawkish rate shock scenario."""
    print_section("Test 3: Rate Shock Scenario")

    key_events = [
        "Fed hikes 75bps to 5.5%",
        "Powell signals higher for longer",
        "10-year Treasury yields hit 5.2%"
    ]
    reasoning = (
        "Federal Reserve delivered a surprise 75 basis point rate hike, with Chair Powell "
        "signaling that rates will remain elevated for an extended period. Treasury yields "
        "surged across the curve, with the 10-year hitting 5.2%. Long-duration assets are "
        "selling off sharply, while financials benefit from higher net interest margins."
    )

    print(f"\nScenario: Fed Hawkish Rate Shock")
    transmission = match_event_to_pattern(key_events, reasoning)

    if transmission:
        print(f"\n  Winners:")
        for sector, strength in sorted(transmission.items(), key=lambda x: -x[1])[:3]:
            print(f"    {sector}: {strength:+.2f}")

        print(f"\n  Losers:")
        for sector, strength in sorted(transmission.items(), key=lambda x: x[1])[:3]:
            print(f"    {sector}: {strength:+.2f}")

        # Key validations
        print(f"\n  Key Validations:")
        print(f"    {'✓' if transmission.get('XLF', 0) > 0.5 else '✗'} XLF (Financials) > 0.5: {transmission.get('XLF', 0):.2f}")
        print(f"    {'✓' if transmission.get('XLK', 0) < -0.6 else '✗'} XLK (Tech) < -0.6: {transmission.get('XLK', 0):.2f}")
        print(f"    {'✓' if transmission.get('XLRE', 0) < -0.7 else '✗'} XLRE (Real Estate) < -0.7: {transmission.get('XLRE', 0):.2f}")


def test_risk_off_scenario():
    """Test 4: Risk-off credit stress scenario."""
    print_section("Test 4: Risk-Off Credit Stress Scenario")

    key_events = [
        "Regional bank failures",
        "Credit spreads widen sharply",
        "VIX spikes to 45"
    ]
    reasoning = (
        "Banking sector stress has triggered a broad risk-off move, with credit spreads "
        "widening dramatically and the VIX volatility index spiking to 45. Investors are "
        "fleeing to defensive sectors as contagion fears spread through the financial system."
    )

    print(f"\nScenario: Credit Crisis Risk-Off")
    transmission = match_event_to_pattern(key_events, reasoning)

    if transmission:
        print(f"\n  Defensive Winners:")
        defensives = ["XLV", "XLP", "XLU"]
        for sector in defensives:
            strength = transmission.get(sector, 0)
            status = "✓" if strength > 0.6 else "✗"
            print(f"    {status} {sector}: {strength:+.2f}")

        print(f"\n  Cyclical Losers:")
        cyclicals = ["XLY", "XLK", "XLF"]
        for sector in cyclicals:
            strength = transmission.get(sector, 0)
            status = "✓" if strength < -0.5 else "✗"
            print(f"    {status} {sector}: {strength:+.2f}")


def test_multiple_pattern_blending():
    """Test 5: Multiple overlapping patterns (oil war)."""
    print_section("Test 5: Multiple Pattern Blending")

    key_events = [
        "Iran war escalation",
        "Hormuz strait closure",
        "Oil supply shock",
        "OPEC emergency meeting"
    ]
    reasoning = (
        "Military conflict in the Middle East has escalated into war, with Iran closing "
        "the Strait of Hormuz and blocking critical oil shipments. OPEC called an emergency "
        "meeting as crude prices surge. Defense contractors are winning on military spending "
        "while energy producers benefit from supply disruptions."
    )

    print(f"\nScenario: Oil War (should match BOTH supply_shock_oil AND war_geopolitical)")
    transmission = match_event_to_pattern(key_events, reasoning)

    if transmission:
        print(f"\n  Expected Pattern Blending:")
        print(f"    - supply_shock_oil: XLE=0.95, XLI=0.70")
        print(f"    - war_geopolitical: XLE=0.80, XLI=0.90")
        print(f"    - Blended (sum+clip): XLE≈1.0, XLI≈1.0 (both clipped)")

        print(f"\n  Actual Transmission:")
        print(f"    XLE: {transmission.get('XLE', 0):+.2f} {'✓ (amplified)' if transmission.get('XLE', 0) >= 0.9 else '✗'}")
        print(f"    XLI: {transmission.get('XLI', 0):+.2f} {'✓ (amplified)' if transmission.get('XLI', 0) >= 0.9 else '✗'}")
        print(f"    XLY: {transmission.get('XLY', 0):+.2f} {'✓ (very negative)' if transmission.get('XLY', 0) <= -0.7 else '✗'}")


def test_no_match_scenario():
    """Test 6: Events that should NOT match any pattern."""
    print_section("Test 6: No Match Scenario")

    key_events = [
        "Company earnings reports mixed",
        "Apple launches new iPhone",
        "Retail sales data in-line with expectations"
    ]
    reasoning = (
        "Quarterly earnings season continues with mixed results. Tech giant Apple unveiled "
        "its latest iPhone model to positive reviews. Economic data showed retail sales "
        "growth meeting consensus forecasts."
    )

    print(f"\nScenario: Routine corporate/economic news (no macro shock)")
    transmission = match_event_to_pattern(key_events, reasoning)

    if not transmission:
        print(f"\n  ✓ Correctly returned empty transmission (no pattern matched)")
    else:
        print(f"\n  ⚠️  Unexpected match: {transmission}")
        print(f"     This should NOT have matched any pattern!")


def run_all_tests():
    """Run all manual tests."""
    print("\n" + "█" * 70)
    print("  Phase 2 Week 1 - Manual Testing Suite")
    print("  Testing transmission_rules.py pattern matching")
    print("█" * 70)

    tests = [
        test_pattern_definitions,
        test_historical_scenario_2026_03_20,
        test_rate_shock_scenario,
        test_risk_off_scenario,
        test_multiple_pattern_blending,
        test_no_match_scenario,
    ]

    for i, test_func in enumerate(tests, 1):
        try:
            test_func()
        except Exception as e:
            print(f"\n❌ Test {i} failed with error: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "█" * 70)
    print("  Testing Complete!")
    print("█" * 70)


if __name__ == "__main__":
    run_all_tests()
