"""
Phase 2 Week 2 Verification Script

Validates Phase 2 integration by analyzing existing database records.
Compares Phase 1 (no transmission) vs Phase 2 (with transmission).

Usage:
    python verify_phase2.py                    # Analyze latest record
    python verify_phase2.py 2026-03-20         # Analyze specific date
    python verify_phase2.py --railway          # Connect to Railway DB
"""

import sys
import json
from datetime import date, datetime
from typing import Optional, Dict, Any

from sqlalchemy import desc

from app.db.database import SessionLocal, init_db
from app.db.models import DailyDecision, EventTransmission, DailyNewsDigest, DecisionLog


def print_section(title: str, char: str = "="):
    """Print formatted section header."""
    print(f"\n{char * 70}")
    print(f"  {title}")
    print(f"{char * 70}")


def analyze_phase2_integration(target_date: Optional[date] = None):
    """Analyze Phase 2 integration for a specific date."""

    init_db()
    db = SessionLocal()

    try:
        # Get target date
        if target_date is None:
            # Use latest record
            latest = db.query(DailyDecision).order_by(desc(DailyDecision.date)).first()
            if not latest:
                print("❌ No records found in daily_decisions table")
                return
            target_date = latest.date

        print_section(f"Phase 2 Integration Analysis - {target_date}", "=")

        # ═══════════════════════════════════════════════════════════════
        # Section 1: Check if Phase 2 data exists
        # ═══════════════════════════════════════════════════════════════

        print_section("1. Phase 2 Data Availability", "-")

        decision = db.query(DailyDecision).filter_by(date=target_date).first()
        transmission = db.query(EventTransmission).filter_by(date=target_date).first()
        digest = db.query(DailyNewsDigest).filter_by(date=target_date).first()
        decision_log = db.query(DecisionLog).filter_by(date=target_date).first()

        if not decision:
            print(f"❌ No DailyDecision record for {target_date}")
            return

        print(f"✓ DailyDecision: {decision.status}")
        print(f"{'✓' if transmission else '✗'} EventTransmission: {'Found' if transmission else 'Not found'}")
        print(f"{'✓' if digest else '✗'} DailyNewsDigest: {'Found' if digest else 'Not found'}")
        print(f"{'✓' if decision_log else '✗'} DecisionLog: {'Found' if decision_log else 'Not found'}")

        # ═══════════════════════════════════════════════════════════════
        # Section 2: Step 1 Output Analysis
        # ═══════════════════════════════════════════════════════════════

        print_section("2. Step 1 Output (Macro Analysis)", "-")

        if not decision.step1_macro_result:
            print("❌ No Step 1 result found")
            return

        try:
            step1_data = json.loads(decision.step1_macro_result)
        except json.JSONDecodeError:
            print("❌ Failed to parse Step 1 JSON")
            return

        print(f"Regime: {step1_data.get('regime', 'N/A')}")
        print(f"Confidence: {step1_data.get('confidence', 'N/A')}/100")
        print(f"Summary: {step1_data.get('summary', 'N/A')}")

        key_events = step1_data.get('key_events', [])
        print(f"\nKey Events ({len(key_events)}):")
        for i, event in enumerate(key_events, 1):
            print(f"  {i}. {event}")

        # Check if transmission_vector exists (Phase 2)
        has_transmission = 'transmission_vector' in step1_data
        transmission_in_step1 = step1_data.get('transmission_vector')

        if has_transmission and transmission_in_step1:
            print(f"\n✅ Phase 2 Enhancement: Transmission vector PRESENT in Step 1")
        else:
            print(f"\n⚠️  Phase 1 Mode: No transmission vector in Step 1 output")
            print(f"    (This record was created before Phase 2 integration)")

        # ═══════════════════════════════════════════════════════════════
        # Section 3: Transmission Vector Analysis
        # ═══════════════════════════════════════════════════════════════

        print_section("3. Transmission Vector (Phase 2 Feature)", "-")

        if transmission:
            print(f"Event ID: {transmission.event_id}")
            print(f"Event Type: {transmission.event_type or 'N/A'}")
            print(f"Confidence: {transmission.confidence}/100")
            print(f"Description: {transmission.event_description}")
            print(f"Validated: {transmission.validated}")

            if transmission.transmission_vector:
                print(f"\n📊 Transmission Vector (Sector Impact Priors):")

                # Sort by absolute strength
                vector = transmission.transmission_vector
                sorted_sectors = sorted(
                    vector.items(),
                    key=lambda x: -abs(x[1])
                )

                print(f"\n  Top Beneficiaries:")
                for sector, strength in sorted_sectors[:5]:
                    if strength > 0.3:
                        print(f"    {sector}: {strength:+.2f}")

                print(f"\n  Top Victims:")
                for sector, strength in reversed(sorted_sectors[-5:]):
                    if strength < -0.3:
                        print(f"    {sector}: {strength:+.2f}")

                print(f"\n  All Sectors:")
                for sector in ["XLE", "XLF", "XLV", "XLI", "XLP", "XLU", "XLY", "XLK", "XLC", "XLRE", "XLB"]:
                    strength = vector.get(sector, 0)
                    emoji = "🔥" if strength > 0.7 else "📈" if strength > 0.3 else "❄️" if strength < -0.7 else "📉" if strength < -0.3 else "➖"
                    print(f"    {sector}: {strength:+.2f} {emoji}")

            else:
                print("❌ No transmission_vector JSONB data")

        elif transmission_in_step1:
            # Transmission in Step 1 but not in table (migration not run or failed)
            print("⚠️  Transmission vector in Step 1 but NOT in event_transmission table")
            print("    This may happen if:")
            print("    - event_transmission table doesn't exist")
            print("    - Step 1 succeeded but DB write failed")
            print("\n📊 Transmission Vector (from Step 1):")

            sorted_sectors = sorted(
                transmission_in_step1.items(),
                key=lambda x: -abs(x[1])
            )
            for sector, strength in sorted_sectors:
                if abs(strength) > 0.3:
                    print(f"    {sector}: {strength:+.2f}")

        else:
            print("ℹ️  No transmission vector available")
            print("    This is expected for pre-Phase 2 records")

        # ═══════════════════════════════════════════════════════════════
        # Section 4: Step 2 Analysis (Check if transmission was used)
        # ═══════════════════════════════════════════════════════════════

        print_section("4. Step 2 Output (Micro Scoring)", "-")

        if not decision.step2_micro_result:
            print("❌ No Step 2 result found")
            return

        try:
            step2_data = json.loads(decision.step2_micro_result)
        except json.JSONDecodeError:
            print("⚠️  Step 2 result is not JSON (may be raw text)")
            step2_data = {}

        print(f"Applied Macro Rule: {step2_data.get('applied_macro_rule', 'N/A')}")

        print(f"\nSector Scores (1-10):")
        for sector in ["XLE", "XLF", "XLV", "XLI", "XLP", "XLU", "XLY", "XLK", "XLC", "XLRE", "XLB"]:
            score = step2_data.get(sector, "N/A")

            # Compare with transmission if available
            if transmission and transmission.transmission_vector:
                trans_strength = transmission.transmission_vector.get(sector, 0)

                # Simple correlation indicator
                if score != "N/A":
                    if trans_strength > 0.5 and score >= 7:
                        indicator = "✓ (matches transmission)"
                    elif trans_strength < -0.5 and score <= 4:
                        indicator = "✓ (matches transmission)"
                    elif abs(trans_strength) < 0.3:
                        indicator = "○ (neutral transmission)"
                    else:
                        indicator = "? (may differ from transmission)"
                else:
                    indicator = ""

                print(f"  {sector}: {score} | transmission={trans_strength:+.2f} {indicator}")
            else:
                print(f"  {sector}: {score}")

        # ═══════════════════════════════════════════════════════════════
        # Section 5: Final Weights & Decision Log
        # ═══════════════════════════════════════════════════════════════

        print_section("5. Final Weights & Decision", "-")

        if decision.final_weights:
            print(f"Final Portfolio Weights (sum={sum(decision.final_weights.values()):.4f}):")
            sorted_weights = sorted(
                decision.final_weights.items(),
                key=lambda x: -x[1]
            )
            for sector, weight in sorted_weights:
                if weight > 0:
                    print(f"  {sector}: {weight:.4f} ({weight*100:.1f}%)")
        else:
            print("⚠️  No final weights available")

        if decision_log:
            print(f"\nDecision Log:")
            print(f"  QC Regime: {decision_log.qc_regime}")
            print(f"  AI Regime: {decision_log.ai_regime}")
            print(f"  Override: {decision_log.regime_override}")
            print(f"  Defense Level: {decision_log.defense_level}")

        # ═══════════════════════════════════════════════════════════════
        # Section 6: Phase 2 Assessment
        # ═══════════════════════════════════════════════════════════════

        print_section("6. Phase 2 Integration Assessment", "=")

        has_transmission_table = transmission is not None
        has_transmission_step1 = transmission_in_step1 is not None

        print(f"\nPhase 2 Features:")
        print(f"  {'✅' if has_transmission_step1 else '❌'} Transmission vector in Step 1 output")
        print(f"  {'✅' if has_transmission_table else '❌'} Transmission vector stored in DB")
        print(f"  {'✅' if has_transmission_table and has_transmission_step1 else '❌'} Full Phase 2 integration")

        if has_transmission_table and has_transmission_step1:
            print(f"\n🎉 Phase 2 Integration: COMPLETE")
            print(f"   - Transmission vector generated from key_events")
            print(f"   - Stored in event_transmission table")
            print(f"   - Available for Step 2 prompt injection")
            print(f"\n   Next: Verify if Step 2 scores align with transmission priors")
        elif has_transmission_step1:
            print(f"\n⚠️  Phase 2 Integration: PARTIAL")
            print(f"   - Transmission vector generated in Step 1")
            print(f"   - But NOT stored in event_transmission table")
            print(f"   - Check if table exists: SELECT * FROM event_transmission LIMIT 1")
        else:
            print(f"\nℹ️  Pre-Phase 2 Record")
            print(f"   This record was created before Week 2 integration")
            print(f"   Re-run pipeline with --force to test Phase 2:")
            print(f"     python cron_pipeline.py {target_date} --force")

    finally:
        db.close()


def main():
    """Main entry point."""
    import sys

    if "--help" in sys.argv:
        print(__doc__)
        return

    # Parse date argument
    target_date = None
    if len(sys.argv) > 1 and sys.argv[1] not in ["--railway"]:
        try:
            target_date = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
        except ValueError:
            print(f"❌ Invalid date format: {sys.argv[1]}")
            print("   Use: YYYY-MM-DD (e.g., 2026-03-20)")
            return

    analyze_phase2_integration(target_date)


if __name__ == "__main__":
    main()
