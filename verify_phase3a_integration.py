"""
Verify Phase 3a Integration

Tests the full pipeline integration of event direction analysis.
Simulates running Step 1 with mock data and verifies Phase 3a fields are populated.
"""

import asyncio
import json
from datetime import date

from app.pipeline.step1_macro import run_macro_analysis


async def test_step1_with_phase3a():
    """Test Step 1 macro analysis with Phase 3a event direction analysis."""
    print("=" * 80)
    print("Phase 3a Integration Test: Step 1 Macro Analysis")
    print("=" * 80)
    print()

    # Mock macro news (2026-03-20 scenario: 4 escalation + 1 de-escalation)
    mock_news = [
        {"headline": "UK deploys submarine to Red Sea amid escalating tensions"},
        {"headline": "Saudi Arabia expels Iranian diplomats over oil blockade threats"},
        {"headline": "Oil hits $200 amid fears Iran threatens Strait of Hormuz closure"},
        {"headline": "Israel-Iran conflict risks broader Middle East war"},
        {"headline": "Iranian gas exports to Europe resume after G7 pressure"},
    ]

    # Mock economic calendar
    mock_calendar = []

    # Mock history
    history_block = """
2026-03-18 [Risk-Off]: Multiple escalation events, confidence=85
2026-03-19 [Risk-Off]: Escalation continues, confidence=85
    """

    print("Running Step 1 with mock 2026-03-20 data...")
    print(f"News items: {len(mock_news)}")
    print()

    # Run Step 1 analysis
    result = await run_macro_analysis(
        target_date=date(2026, 3, 20),
        macro_news=mock_news,
        econ_calendar=mock_calendar,
        history_block=history_block,
        db=None,  # No DB connection for this test
    )

    print("=" * 80)
    print("Step 1 Output")
    print("=" * 80)
    print()

    # Basic fields
    print(f"Regime: {result.regime}")
    print(f"Confidence: {result.confidence}")
    print(f"Summary: {result.summary}")
    print(f"Key Events: {result.key_events}")
    print(f"Reasoning: {result.reasoning[:200]}...")
    print()

    # Phase 2: Transmission vector
    print("=" * 80)
    print("Phase 2: Transmission Vector")
    print("=" * 80)
    print()
    if result.transmission_vector:
        top_impacts = sorted(
            result.transmission_vector.items(),
            key=lambda x: -abs(x[1])
        )[:5]
        for sector, strength in top_impacts:
            direction = "↑" if strength > 0 else "↓"
            print(f"  {sector}: {direction} {abs(strength):.2f}")
    else:
        print("  No transmission vector generated")
    print()

    # Phase 3a: Event direction analysis
    print("=" * 80)
    print("Phase 3a: Event Direction Analysis")
    print("=" * 80)
    print()

    if result.net_escalation_score is not None:
        print(f"✓ Net Escalation Score: {result.net_escalation_score:.2f}")
        escalation_label = (
            "STRONG ESCALATION" if result.net_escalation_score > 0.6 else
            "MODERATE ESCALATION" if result.net_escalation_score > 0.3 else
            "BALANCED / MIXED" if result.net_escalation_score > -0.3 else
            "DE-ESCALATION"
        )
        print(f"  → {escalation_label}")
    else:
        print("✗ Net Escalation Score: NOT POPULATED")

    print()
    if result.regime_phase:
        print(f"✓ Regime Phase: {result.regime_phase}")
    else:
        print("✗ Regime Phase: NOT POPULATED")

    print()
    if result.event_direction_reasoning:
        print(f"✓ Event Direction Reasoning:")
        print(f"  {result.event_direction_reasoning}")
    else:
        print("✗ Event Direction Reasoning: NOT POPULATED")

    print()
    print("=" * 80)
    print("Integration Validation")
    print("=" * 80)
    print()

    # Validation checks
    checks = [
        (result.net_escalation_score is not None,
         "Net escalation score populated"),
        (result.regime_phase is not None,
         "Regime phase populated"),
        (result.event_direction_reasoning is not None,
         "Event direction reasoning populated"),
        (result.net_escalation_score is not None and 0.3 < result.net_escalation_score < 0.7,
         f"Net escalation in expected range (0.3-0.7): {result.net_escalation_score:.2f if result.net_escalation_score is not None else 'N/A'}"),
        (result.regime_phase is not None and ("Peak" in result.regime_phase or "deceleration" in result.regime_phase),
         f"Phase detects deceleration: '{result.regime_phase}'"),
    ]

    all_passed = True
    for passed, message in checks:
        status = "✓" if passed else "✗"
        print(f"{status} {message}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("🎉 All validation checks PASSED!")
    else:
        print("⚠️  Some validation checks FAILED")

    # Show JSON output (for API response simulation)
    print()
    print("=" * 80)
    print("JSON Output (for API response)")
    print("=" * 80)
    print()
    result_dict = result.model_dump()
    print(json.dumps(result_dict, indent=2, ensure_ascii=False))

    return result


async def main():
    """Run integration test."""
    await test_step1_with_phase3a()


if __name__ == "__main__":
    asyncio.run(main())
