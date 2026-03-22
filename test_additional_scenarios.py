"""
Additional Scenario Tests for Phase 2 Week 1

Tests edge cases and additional scenarios beyond the core 6 patterns.
Run after test_phase2_manual.py for comprehensive coverage.

Usage:
    python test_additional_scenarios.py
"""

from app.pipeline.transmission_rules import (
    match_event_to_pattern,
    detect_event_type,
)


def print_section(title: str):
    """Print section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def test_single_keyword_scenario():
    """Test: Single keyword should NOT match (min_keyword_matches=2)."""
    print_section("Test 1: Single Keyword (Should Not Match)")

    key_events = ["Oil price rises 2%"]
    reasoning = "Crude gains on optimism..."

    transmission = match_event_to_pattern(key_events, reasoning)

    if not transmission:
        print("  ✓ Correctly rejected (only 1 keyword)")
    else:
        print(f"  ⚠️  Unexpected match: {transmission}")
        print("     This should NOT have matched (only 1 keyword)")


def test_weak_keywords_scenario():
    """Test: Generic keywords should require multiple matches."""
    print_section("Test 2: Weak Generic Keywords")

    key_events = ["Market volatility", "Investors cautious"]
    reasoning = "Trading volumes mixed as uncertainty persists..."

    transmission = match_event_to_pattern(key_events, reasoning)

    if not transmission:
        print("  ✓ Correctly rejected (no strong pattern)")
    else:
        print(f"  ⚠️  Matched: {transmission}")
        print("     Check if this is a false positive")


def test_mixed_signals_scenario():
    """Test: Conflicting signals (hawkish + dovish mixed)."""
    print_section("Test 3: Mixed/Conflicting Signals")

    key_events = [
        "Fed hints at rate cuts",
        "Strong jobs data suggests further hikes needed"
    ]
    reasoning = (
        "Mixed signals from the Fed as Powell suggests dovish tilt "
        "while strong employment data argues for continued tightening..."
    )

    transmission = match_event_to_pattern(key_events, reasoning)

    print(f"\n  Input: Mixed hawkish + dovish signals")
    if transmission:
        print(f"\n  Matched pattern detected:")
        # Show which direction won
        if transmission.get("XLF", 0) > 0.5:
            print(f"    → Hawkish signal dominated (XLF={transmission['XLF']:+.2f})")
        elif transmission.get("XLRE", 0) > 0.5:
            print(f"    → Dovish signal dominated (XLRE={transmission['XLRE']:+.2f})")
        else:
            print(f"    → Weak/mixed result")
    else:
        print("  ✓ No clear pattern (signals cancel out)")


def test_inflation_scenario():
    """Test: Inflation spike (should match supply shock or rate shock)."""
    print_section("Test 4: Inflation Spike Scenario")

    key_events = [
        "CPI surges to 9.1%",
        "PPI hits 40-year high",
        "Wage inflation accelerating"
    ]
    reasoning = (
        "Inflation data came in much hotter than expected with CPI at 9.1%, "
        "driven by energy costs and persistent wage pressures. Markets fear "
        "aggressive Fed response."
    )

    transmission = match_event_to_pattern(key_events, reasoning)
    event_type = detect_event_type(key_events, reasoning)

    print(f"\n  Detected event type: {event_type}")
    if transmission:
        print(f"\n  Key impacts:")
        print(f"    XLE (Energy): {transmission.get('XLE', 0):+.2f}")
        print(f"    XLB (Materials): {transmission.get('XLB', 0):+.2f}")
        print(f"    XLY (Consumer): {transmission.get('XLY', 0):+.2f}")
        print(f"    XLRE (Real Estate): {transmission.get('XLRE', 0):+.2f}")
    else:
        print("  ⚠️  No pattern matched for inflation")


def test_china_scenario():
    """Test: China-related geopolitical event."""
    print_section("Test 5: China Geopolitical Scenario")

    key_events = [
        "China-Taiwan tensions escalate",
        "US considers tech sanctions",
        "Supply chain disruption fears"
    ]
    reasoning = (
        "Rising tensions between China and Taiwan trigger fears of supply chain "
        "disruptions in semiconductors and electronics manufacturing. US weighs "
        "additional technology sanctions on Chinese firms."
    )

    transmission = match_event_to_pattern(key_events, reasoning)
    event_type = detect_event_type(key_events, reasoning)

    print(f"\n  Detected event type: {event_type}")
    if transmission:
        print(f"\n  Key impacts:")
        print(f"    XLK (Tech): {transmission.get('XLK', 0):+.2f}")
        print(f"    XLI (Industrials): {transmission.get('XLI', 0):+.2f}")
        print(f"    XLY (Consumer): {transmission.get('XLY', 0):+.2f}")

        # Check if correctly identified as geopolitical
        if transmission.get("XLI", 0) > 0.5:
            print("  ✓ Correctly identified geopolitical pattern (XLI benefits)")
        else:
            print("  ⚠️  Geopolitical pattern not strongly detected")
    else:
        print("  ⚠️  No pattern matched")


def test_crypto_crash_scenario():
    """Test: Crypto crash / fintech stress (should match risk-off)."""
    print_section("Test 6: Crypto/Fintech Stress Scenario")

    key_events = [
        "Bitcoin crashes 40%",
        "Crypto exchange bankruptcies",
        "Contagion fears spread to banks"
    ]
    reasoning = (
        "Cryptocurrency markets collapse with Bitcoin down 40%, triggering "
        "bankruptcy of major exchanges. Contagion fears spread to traditional "
        "financial institutions with crypto exposure."
    )

    transmission = match_event_to_pattern(key_events, reasoning)
    event_type = detect_event_type(key_events, reasoning)

    print(f"\n  Detected event type: {event_type}")
    if transmission:
        # Should match risk_off_credit_stress
        defensives = ["XLV", "XLP", "XLU"]
        cyclicals = ["XLF", "XLK", "XLY"]

        print(f"\n  Defensive sectors:")
        for sector in defensives:
            strength = transmission.get(sector, 0)
            status = "✓" if strength > 0.5 else "✗"
            print(f"    {status} {sector}: {strength:+.2f}")

        print(f"\n  Risk sectors:")
        for sector in cyclicals:
            strength = transmission.get(sector, 0)
            status = "✓" if strength < -0.3 else "✗"
            print(f"    {status} {sector}: {strength:+.2f}")
    else:
        print("  ⚠️  Risk-off pattern not detected")


def test_earnings_recession_scenario():
    """Test: Earnings recession / corporate profit warnings."""
    print_section("Test 7: Earnings Recession Scenario")

    key_events = [
        "S&P 500 earnings miss by 15%",
        "Corporate profit warnings surge",
        "Layoff announcements accelerate"
    ]
    reasoning = (
        "Corporate earnings season reveals widespread profit disappointments "
        "with S&P 500 companies missing estimates by 15% on average. Major "
        "tech firms announce layoffs as economic slowdown deepens."
    )

    transmission = match_event_to_pattern(key_events, reasoning)
    event_type = detect_event_type(key_events, reasoning)

    print(f"\n  Detected event type: {event_type}")
    if transmission:
        print(f"\n  Should match recession pattern:")
        print(f"    XLV (Healthcare defensive): {transmission.get('XLV', 0):+.2f} {'✓' if transmission.get('XLV', 0) > 0.5 else '✗'}")
        print(f"    XLP (Staples defensive): {transmission.get('XLP', 0):+.2f} {'✓' if transmission.get('XLP', 0) > 0.5 else '✗'}")
        print(f"    XLY (Discretionary hurt): {transmission.get('XLY', 0):+.2f} {'✓' if transmission.get('XLY', 0) < -0.5 else '✗'}")
        print(f"    XLK (Tech hurt): {transmission.get('XLK', 0):+.2f} {'✓' if transmission.get('XLK', 0) < -0.3 else '✗'}")
    else:
        print("  ⚠️  Recession pattern not detected")


def test_japan_scenario():
    """Test: Japan-specific events (should generalize or not match)."""
    print_section("Test 8: Japan BOJ Scenario")

    key_events = [
        "Bank of Japan abandons yield curve control",
        "Yen surges 5% against dollar",
        "Japanese bond market turmoil"
    ]
    reasoning = (
        "Bank of Japan makes surprise policy shift abandoning yield curve control, "
        "triggering massive yen appreciation and bond market volatility. Global "
        "carry trade unwinds."
    )

    transmission = match_event_to_pattern(key_events, reasoning)

    if transmission:
        print(f"\n  Matched pattern (global spillover effect):")
        print(f"    XLF (Financials): {transmission.get('XLF', 0):+.2f}")
        print(f"    XLK (Tech): {transmission.get('XLK', 0):+.2f}")
    else:
        print("  ✓ No match (Japan-specific event without clear US transmission)")


def test_climate_disaster_scenario():
    """Test: Climate disaster / natural disaster."""
    print_section("Test 9: Climate Disaster Scenario")

    key_events = [
        "Category 5 hurricane hits Gulf Coast",
        "Oil refinery shutdowns",
        "Insurance claims surge"
    ]
    reasoning = (
        "Major hurricane forces shutdown of Gulf Coast oil refineries, "
        "disrupting fuel supply. Insurance industry faces massive claims."
    )

    transmission = match_event_to_pattern(key_events, reasoning)
    event_type = detect_event_type(key_events, reasoning)

    print(f"\n  Detected event type: {event_type}")
    if transmission:
        # Should potentially match supply_shock_oil
        print(f"\n  Impacts:")
        print(f"    XLE (Energy): {transmission.get('XLE', 0):+.2f}")
        print(f"    XLF (Financials/Insurance): {transmission.get('XLF', 0):+.2f}")
    else:
        print("  ℹ️  No standard pattern matched (specialized scenario)")


def test_breakthrough_technology_scenario():
    """Test: Positive tech breakthrough (no standard pattern should match)."""
    print_section("Test 10: Tech Breakthrough Scenario")

    key_events = [
        "OpenAI announces GPT-5",
        "Breakthrough in quantum computing",
        "Tech stocks rally"
    ]
    reasoning = (
        "Major AI breakthrough announced with GPT-5 demonstrating superhuman "
        "capabilities. Tech stocks rally on optimism about productivity gains."
    )

    transmission = match_event_to_pattern(key_events, reasoning)

    if not transmission:
        print("  ✓ Correctly no match (positive tech-specific event)")
        print("     Standard patterns focus on macro shocks, not sector-specific positives")
    else:
        print(f"  ℹ️  Unexpected match: {transmission}")
        print("     Review if this makes sense")


def run_all_tests():
    """Run all additional scenario tests."""
    print("\n" + "█" * 70)
    print("  Phase 2 Week 1 - Additional Scenario Tests")
    print("  Edge cases and specialized scenarios")
    print("█" * 70)

    tests = [
        test_single_keyword_scenario,
        test_weak_keywords_scenario,
        test_mixed_signals_scenario,
        test_inflation_scenario,
        test_china_scenario,
        test_crypto_crash_scenario,
        test_earnings_recession_scenario,
        test_japan_scenario,
        test_climate_disaster_scenario,
        test_breakthrough_technology_scenario,
    ]

    for i, test_func in enumerate(tests, 1):
        try:
            test_func()
        except Exception as e:
            print(f"\n❌ Test {i} failed: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "█" * 70)
    print("  Additional Scenario Testing Complete!")
    print("█" * 70)
    print("\n📊 Summary:")
    print("  - Single keyword rejection: Edge case handling")
    print("  - Mixed signals: Conflicting pattern resolution")
    print("  - Inflation: Cross-pattern matching")
    print("  - China/Japan: Geographic specificity")
    print("  - Crypto/Climate: Specialized scenarios")
    print("  - Tech breakthrough: Positive events (non-shock)")


if __name__ == "__main__":
    run_all_tests()
