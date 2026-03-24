"""
Phase 5b Test Suite: LLM Parallel Analysis

Tests the GPT-4o based parallel analysis system for:
- Signal contradiction detection
- LLM transmission vector generation
- Confidence adjustment logic
- Comparison with rule-based system

Usage:
    python test_phase5b_llm.py
"""

import asyncio
from app.pipeline.llm_parallel_analysis import run_llm_parallel_analysis


async def test_2026_03_23_case():
    """Test LLM analysis on 2026-03-23 real case (from agent feedback)."""
    print("\n" + "=" * 80)
    print("Test Case: 2026-03-23 (Real Agent Feedback Scenario)")
    print("=" * 80 + "\n")

    # Real events from 2026-03-23
    key_events = [
        "Trump postpones Iran energy strikes, markets rally",
        "Oil falls 13% on Iran strike pause",
        "Dollar slides, stocks jump on Iran talks progress",
        "Israeli military strikes in Tehran",
        "Fed's Goolsbee hints at possible rate hikes",
    ]

    reasoning = (
        "The postponement of military strikes on Iran has led to a market rally, "
        "easing previous risk-off sentiment. However, geopolitical tensions remain "
        "with Israeli strikes in Tehran. Quantitative indicators show mixed signals."
    )

    regime = "Neutral"
    confidence = 60

    print("INPUT:")
    print(f"  Regime: {regime}")
    print(f"  Confidence: {confidence}")
    print(f"  Events:")
    for i, event in enumerate(key_events, 1):
        print(f"    {i}. {event}")
    print()

    # Run LLM analysis
    result = await run_llm_parallel_analysis(
        key_events=key_events,
        reasoning=reasoning,
        regime=regime,
        confidence=confidence,
    )

    print("LLM ANALYSIS (GPT-4o):")
    print("-" * 80)

    # Signal contradictions
    print(f"\n1. SIGNAL CONTRADICTIONS:")
    print(f"   Overall Score: {result.overall_contradiction_score:.2f}")
    if result.signal_contradictions:
        for i, contradiction in enumerate(result.signal_contradictions, 1):
            print(f"\n   Contradiction #{i}:")
            print(f"     Event A: {contradiction.event_a}")
            print(f"     Event B: {contradiction.event_b}")
            print(f"     Type: {contradiction.contradiction_type}")
            print(f"     Severity: {contradiction.severity:.2f}")
            print(f"     Reasoning: {contradiction.reasoning}")
    else:
        print("   No contradictions detected")

    # Transmission vector
    print(f"\n2. TRANSMISSION VECTOR (LLM):")
    if result.transmission_vector_llm:
        # Sort by absolute impact
        sorted_sectors = sorted(
            result.transmission_vector_llm.items(),
            key=lambda x: abs(x[1]),
            reverse=True
        )
        for sector, impact in sorted_sectors:
            sign = "+" if impact >= 0 else ""
            print(f"   {sector}: {sign}{impact:.2f}")
    else:
        print("   No transmission vector generated")

    print(f"\n   Reasoning: {result.transmission_reasoning}")

    # Confidence adjustment
    print(f"\n3. CONFIDENCE ADJUSTMENT:")
    print(f"   Recommended: {result.confidence_adjustment:+d}")
    print(f"   New Confidence: {confidence + result.confidence_adjustment}")
    print(f"   Reasoning: {result.confidence_reasoning}")

    # Hidden risks
    if result.hidden_risks:
        print(f"\n4. HIDDEN RISKS:")
        for risk in result.hidden_risks:
            print(f"   • {risk}")

    # Expected results validation
    print("\n" + "=" * 80)
    print("VALIDATION CHECKS:")
    print("=" * 80)

    checks = [
        (
            result.overall_contradiction_score >= 0.6,
            f"High contradiction detected (≥0.6): {result.overall_contradiction_score:.2f}"
        ),
        (
            len(result.signal_contradictions) >= 1,
            f"At least 1 contradiction found: {len(result.signal_contradictions)}"
        ),
        (
            result.confidence_adjustment < 0,
            f"Confidence reduced due to contradictions: {result.confidence_adjustment:+d}"
        ),
        (
            "XLE" in result.transmission_vector_llm,
            "XLE (Energy) present in transmission vector"
        ),
        (
            "XLF" in result.transmission_vector_llm,
            "XLF (Financials) present in transmission vector (rate hikes)"
        ),
    ]

    passed = 0
    for check, description in checks:
        status = "✅" if check else "❌"
        print(f"{status} {description}")
        if check:
            passed += 1

    print(f"\nPassed: {passed}/{len(checks)}")


async def test_clear_signals():
    """Test LLM analysis with clear, reinforcing signals."""
    print("\n" + "=" * 80)
    print("Test Case: Clear Reinforcing Signals (Should Increase Confidence)")
    print("=" * 80 + "\n")

    key_events = [
        "Fed cuts rates 50bp, signals more cuts ahead",
        "Credit spreads tighten to 6-month lows",
        "VIX falls below 15 as calm returns",
        "S&P 500 breaks above 6000 on rally",
    ]

    reasoning = (
        "Federal Reserve delivered a dovish surprise with aggressive rate cuts. "
        "Market responded with broad-based rally across all risk assets. "
        "Credit conditions improving, volatility falling, risk-on confirmed."
    )

    regime = "Risk-On"
    confidence = 85

    result = await run_llm_parallel_analysis(
        key_events=key_events,
        reasoning=reasoning,
        regime=regime,
        confidence=confidence,
    )

    print(f"Contradiction Score: {result.overall_contradiction_score:.2f}")
    print(f"Confidence Adjustment: {result.confidence_adjustment:+d}")
    print(f"Expected: Low contradiction (<0.3), Positive or neutral adjustment")

    checks = [
        (
            result.overall_contradiction_score < 0.3,
            f"Low contradiction score: {result.overall_contradiction_score:.2f}"
        ),
        (
            result.confidence_adjustment >= -5,
            f"No major confidence reduction: {result.confidence_adjustment:+d}"
        ),
    ]

    for check, description in checks:
        status = "✅" if check else "❌"
        print(f"{status} {description}")


async def main():
    """Run all tests."""
    print()
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 15 + "Phase 5b Test Suite: LLM Parallel Analysis" + " " * 20 + "║")
    print("╚" + "=" * 78 + "╝")

    await test_2026_03_23_case()
    await test_clear_signals()

    print("\n" + "=" * 80)
    print("Test Suite Complete")
    print("=" * 80 + "\n")

    print("Next Steps:")
    print("1. Review LLM contradictions vs rule-based net escalation")
    print("2. Compare transmission vectors (rule vs LLM)")
    print("3. Deploy to Railway and test with tomorrow's pipeline run")
    print("4. Monitor Phase 5a accuracy: rule-based vs LLM vs ensemble")


if __name__ == "__main__":
    asyncio.run(main())
