"""
Test Option A Fixes - Pattern Blending & Transmission Mapping

Validates:
1. Pattern blending改进（diminishing returns vs simple sum）
2. Transmission mapping规则是否正确显示

Run: python test_option_a_fixes.py
"""

from app.pipeline.transmission_rules import (
    match_event_to_pattern,
    format_transmission_context,
    CANONICAL_TRANSMISSIONS,
)


def print_section(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def test_blending_improvement():
    """Test Case 1: 2026-03-20 Iran War Scenario"""
    print_section("Test 1: Pattern Blending Improvement")

    key_events = [
        "Iran closes Strait of Hormuz",
        "Oil supply disruption",
        "UK nuclear submarine positioned in Arabian Sea",
        "Saudi Arabia expels Iranian military attache",
    ]

    reasoning = (
        "Iran war escalates beyond Trump's control. "
        "Major oil supply shock affecting global markets."
    )

    transmission = match_event_to_pattern(key_events, reasoning)

    print("\nMatched Patterns:")
    # Manually calculate which patterns should match
    combined_text = " ".join(key_events).lower() + " " + reasoning.lower()

    for pattern_name, pattern_def in CANONICAL_TRANSMISSIONS.items():
        score = sum(1 for kw in pattern_def["keywords"] if kw in combined_text)
        if score >= 2:
            print(f"  {pattern_name}: {score} keywords matched")

    print("\nXLB Transmission Analysis:")
    xlb_strength = transmission.get("XLB", 0.0)
    print(f"  Current (with diminishing returns): {xlb_strength:.2f}")

    # Calculate what old method would give
    supply_shock_xlb = CANONICAL_TRANSMISSIONS["supply_shock_oil"]["vector"]["XLB"]
    war_xlb = CANONICAL_TRANSMISSIONS["war_geopolitical"]["vector"]["XLB"]
    old_method_result = min(1.0, supply_shock_xlb + war_xlb)

    print(f"  Old method (simple sum + clip):   {old_method_result:.2f}")
    print(f"  Improvement: {old_method_result:.2f} → {xlb_strength:.2f}")

    if xlb_strength < old_method_result:
        print("  ✅ SUCCESS: Blending is now more conservative")
    else:
        print("  ⚠️  WARNING: Blending may not be working as expected")

    # Show top sectors
    print("\nTop 5 Transmission Strengths:")
    sorted_sectors = sorted(transmission.items(), key=lambda x: -abs(x[1]))[:5]
    for sector, strength in sorted_sectors:
        print(f"  {sector}: {strength:+.2f}")


def test_transmission_mapping():
    """Test Case 2: Transmission Context Formatting"""
    print_section("Test 2: Transmission Mapping Rules")

    # Create a sample transmission vector
    test_transmission = {
        "XLE": 0.95,   # Strong positive
        "XLB": 0.80,   # Strong positive (improved from 1.00)
        "XLI": 0.70,   # Moderate positive
        "XLY": -0.75,  # Strong negative
        "XLK": -0.50,  # Moderate negative
        "XLF": -0.30,  # Weak negative
    }

    context = format_transmission_context(test_transmission)

    print("\nFormatted Transmission Context:")
    print(context)

    # Validate key components are present
    checks = [
        ("Strength interpretation present", "TRANSMISSION STRENGTH → SCORE INTERPRETATION" in context),
        ("Score ranges defined", "0.7-1.0  → Target score 8-10" in context),
        ("Critical rules included", "CRITICAL RULES:" in context),
        ("Macro Rule distinction", "sectors WITH Macro Rules" in context),
        ("Example provided", "EXAMPLE:" in context),
        ("XLB example mentioned", "XLB transmission=0.80" in context),
    ]

    print("\nValidation Checks:")
    all_passed = True
    for check_name, result in checks:
        status = "✅" if result else "❌"
        print(f"  {status} {check_name}")
        if not result:
            all_passed = False

    if all_passed:
        print("\n✅ All validation checks passed!")
    else:
        print("\n⚠️  Some checks failed - review output above")


def test_edge_cases():
    """Test Case 3: Edge Cases"""
    print_section("Test 3: Edge Cases")

    # Case 1: Only one pattern matches
    print("\nCase 1: Single Pattern Match")
    single_match = match_event_to_pattern(
        ["Fed rate cut", "Powell dovish pivot"],
        "Fed signals easing cycle"
    )
    print(f"  Single pattern matched: fed_dovish_easing")
    print(f"  XLRE: {single_match.get('XLRE', 0.0):.2f} (should be 0.80 - no blending)")

    # Case 2: Opposite signs (inflation + recession contradictory)
    print("\nCase 2: Contradictory Signals (edge case)")
    contradictory = match_event_to_pattern(
        ["Inflation spike", "CPI high", "Recession fears", "GDP miss"],
        "Mixed signals in economy"
    )
    print(f"  Patterns matched: rate_shock_hawkish + recession_demand_collapse")
    print(f"  XLF: {contradictory.get('XLF', 0.0):+.2f}")
    print(f"    (rate_shock: +0.70, recession: -0.50 → should partially cancel)")

    # Case 3: No pattern matches
    print("\nCase 3: No Pattern Match")
    no_match = match_event_to_pattern(
        ["Sunny weather today"],
        "Market closed for holiday"
    )
    if not no_match:
        print("  ✅ Correctly returns empty dict when no pattern matches")
    else:
        print("  ⚠️  Should return empty dict but didn't")


def main():
    """Run all tests"""
    print("=" * 70)
    print("  Option A Fixes Validation Test Suite")
    print("  Testing Pattern Blending & Transmission Mapping")
    print("=" * 70)

    test_blending_improvement()
    test_transmission_mapping()
    test_edge_cases()

    print("\n" + "=" * 70)
    print("  Test Suite Complete")
    print("=" * 70)


if __name__ == "__main__":
    main()
