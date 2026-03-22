"""
Phase 2 Week 3 - Transmission Backtesting

Validates transmission vectors by comparing predicted sector impacts
vs actual sector ETF returns.

Features:
- Fetch actual sector returns from Yahoo Finance
- Calculate correlation between transmission and actual returns
- Update accuracy_score in event_transmission table
- Generate validation report

Usage:
    python backtest_transmission.py                 # Backtest all unvalidated
    python backtest_transmission.py 2026-03-20      # Backtest specific date
    python backtest_transmission.py --days 5        # Use 5-day returns
    python backtest_transmission.py --force         # Re-validate all

Requires:
    pip install yfinance pandas
"""

import sys
import argparse
from datetime import date, timedelta, datetime
from typing import Dict, Optional, Tuple

import yfinance as yf
import pandas as pd
from sqlalchemy import desc

from app.db.database import SessionLocal, init_db
from app.db.models import EventTransmission


# ═══════════════════════════════════════════════════════════════
# Market Data Fetching
# ═══════════════════════════════════════════════════════════════

def fetch_sector_returns(
    start_date: date,
    end_date: date,
) -> Dict[str, float]:
    """Fetch actual sector ETF returns from Yahoo Finance.

    Args:
        start_date: Start date for return calculation
        end_date: End date for return calculation

    Returns:
        Dict mapping sector symbol to return (e.g., {"XLE": 0.05, "XLY": -0.02})
    """
    sectors = ["XLE", "XLF", "XLV", "XLI", "XLP", "XLU", "XLY", "XLK", "XLC", "XLRE", "XLB"]

    returns = {}

    try:
        # Download data for all sectors at once
        data = yf.download(
            sectors,
            start=start_date.isoformat(),
            end=(end_date + timedelta(days=1)).isoformat(),
            progress=False,
            group_by="ticker"
        )

        for sector in sectors:
            try:
                if sector in data.columns.levels[0]:
                    # Get adjusted close prices
                    prices = data[sector]["Adj Close"].dropna()

                    if len(prices) >= 2:
                        # Calculate return: (end - start) / start
                        start_price = prices.iloc[0]
                        end_price = prices.iloc[-1]
                        ret = (end_price - start_price) / start_price
                        returns[sector] = float(ret)
                    else:
                        returns[sector] = 0.0
                else:
                    returns[sector] = 0.0

            except Exception as e:
                print(f"  ⚠️  Failed to fetch {sector}: {e}")
                returns[sector] = 0.0

    except Exception as e:
        print(f"  ❌ Failed to download sector data: {e}")
        # Return zeros if download fails
        returns = {s: 0.0 for s in sectors}

    return returns


# ═══════════════════════════════════════════════════════════════
# Validation Logic
# ═══════════════════════════════════════════════════════════════

def calculate_correlation(
    transmission: Dict[str, float],
    actual_returns: Dict[str, float],
) -> Tuple[float, int]:
    """Calculate Pearson correlation between transmission and actual returns.

    Args:
        transmission: Predicted sector impacts (e.g., {"XLE": 1.0, "XLY": -0.75})
        actual_returns: Actual sector returns (e.g., {"XLE": 0.05, "XLY": -0.02})

    Returns:
        (correlation, common_sectors_count)
    """
    # Find common sectors
    common = set(transmission.keys()) & set(actual_returns.keys())

    if not common or len(common) < 3:
        return 0.0, 0

    # Extract values for common sectors
    trans_values = [transmission[s] for s in common]
    return_values = [actual_returns[s] for s in common]

    # Calculate Pearson correlation
    try:
        series_trans = pd.Series(trans_values)
        series_returns = pd.Series(return_values)
        corr = series_trans.corr(series_returns)

        if pd.isna(corr):
            return 0.0, len(common)

        return float(corr), len(common)

    except Exception as e:
        print(f"  ⚠️  Correlation calculation failed: {e}")
        return 0.0, len(common)


def validate_transmission(
    event: EventTransmission,
    days_forward: int = 5,
) -> Tuple[float, Dict[str, float]]:
    """Validate one transmission vector against actual returns.

    Args:
        event: EventTransmission record
        days_forward: Number of days forward to measure returns (default: 5)

    Returns:
        (accuracy_score, actual_returns_dict)
    """
    if not event.transmission_vector:
        return 0.0, {}

    # Calculate date range
    start_date = event.date
    end_date = event.date + timedelta(days=days_forward)

    print(f"  Fetching returns for {start_date} → {end_date} ({days_forward} days)...")

    # Fetch actual returns
    actual_returns = fetch_sector_returns(start_date, end_date)

    if not actual_returns:
        print(f"  ⚠️  No return data available")
        return 0.0, {}

    # Calculate correlation
    corr, common_count = calculate_correlation(
        event.transmission_vector,
        actual_returns
    )

    print(f"  Correlation: {corr:.3f} ({common_count} sectors)")

    return corr, actual_returns


# ═══════════════════════════════════════════════════════════════
# Backtesting Workflow
# ═══════════════════════════════════════════════════════════════

def backtest_event(
    event: EventTransmission,
    days_forward: int = 5,
    force: bool = False,
) -> bool:
    """Backtest one event transmission vector.

    Args:
        event: EventTransmission record
        days_forward: Number of days to measure returns
        force: Re-validate even if already validated

    Returns:
        True if validation succeeded
    """
    if event.validated and not force:
        print(f"  ℹ️  Already validated (accuracy={event.accuracy_score:.3f}), skipping")
        return True

    print(f"\n{'='*70}")
    print(f"  Backtesting: {event.event_id}")
    print(f"{'='*70}")
    print(f"  Date: {event.date}")
    print(f"  Event Type: {event.event_type or 'N/A'}")
    print(f"  Description: {event.event_description}")

    # Validate
    accuracy, actual_returns = validate_transmission(event, days_forward)

    # Display comparison
    if actual_returns and event.transmission_vector:
        print(f"\n  Predicted vs Actual:")
        sorted_sectors = sorted(
            event.transmission_vector.items(),
            key=lambda x: -abs(x[1])
        )
        for sector, trans_strength in sorted_sectors[:8]:
            actual_ret = actual_returns.get(sector, 0.0)
            direction = "✓" if (trans_strength > 0 and actual_ret > 0) or (trans_strength < 0 and actual_ret < 0) else "✗"
            print(f"    {sector}: predicted={trans_strength:+.2f}, actual={actual_ret:+.2%} {direction}")

    return accuracy


def run_backtest(
    target_date: Optional[date] = None,
    days_forward: int = 5,
    force: bool = False,
):
    """Run backtesting on event transmissions.

    Args:
        target_date: If provided, only backtest this date. Otherwise backtest all unvalidated.
        days_forward: Number of days to measure returns
        force: Re-validate even if already validated
    """
    init_db()
    db = SessionLocal()

    try:
        # Query events
        if target_date:
            events = db.query(EventTransmission).filter_by(date=target_date).all()
            if not events:
                print(f"❌ No event transmission found for {target_date}")
                return
        else:
            if force:
                events = db.query(EventTransmission).order_by(desc(EventTransmission.date)).all()
            else:
                events = db.query(EventTransmission).filter_by(validated=False).order_by(EventTransmission.date).all()

            if not events:
                print("✓ All events already validated")
                return

        print(f"\n{'█'*70}")
        print(f"  Phase 2 Week 3 - Transmission Backtesting")
        print(f"  Events to validate: {len(events)}")
        print(f"  Return window: {days_forward} days")
        print(f"{'█'*70}")

        # Backtest each event
        results = []
        for event in events:
            try:
                accuracy = backtest_event(event, days_forward, force)

                # Update database
                event.accuracy_score = accuracy
                event.validated = True
                db.commit()

                results.append((event.date, event.event_type, accuracy))

                print(f"  ✓ Updated accuracy_score: {accuracy:.3f}")

            except Exception as e:
                print(f"  ❌ Validation failed: {e}")
                import traceback
                traceback.print_exc()

        # Summary report
        print(f"\n{'='*70}")
        print(f"  Backtesting Summary")
        print(f"{'='*70}")

        if results:
            avg_accuracy = sum(r[2] for r in results) / len(results)
            print(f"\n  Validated: {len(results)} events")
            print(f"  Average Accuracy: {avg_accuracy:.3f}")

            print(f"\n  Results by Event:")
            for evt_date, evt_type, acc in sorted(results, key=lambda x: -x[2]):
                print(f"    {evt_date} | {evt_type or 'N/A':25s} | {acc:+.3f}")

            # Interpretation
            print(f"\n  Interpretation:")
            if avg_accuracy > 0.5:
                print(f"    ✅ Strong correlation (>0.5) - Transmission predictions are accurate")
            elif avg_accuracy > 0.3:
                print(f"    ✓ Moderate correlation (0.3-0.5) - Transmission predictions are useful")
            elif avg_accuracy > 0.0:
                print(f"    ⚠️  Weak correlation (0-0.3) - Transmission predictions need tuning")
            else:
                print(f"    ❌ No correlation (<0) - Transmission predictions may be inaccurate")

        else:
            print(f"  ℹ️  No events validated")

    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════
# CLI Entry Point
# ═══════════════════════════════════════════════════════════════

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Backtest Phase 2 transmission vectors against actual sector returns"
    )
    parser.add_argument(
        "date",
        nargs="?",
        help="Specific date to backtest (YYYY-MM-DD). If omitted, backtest all unvalidated."
    )
    parser.add_argument(
        "--days",
        type=int,
        default=5,
        help="Number of days forward to measure returns (default: 5)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-validate even if already validated"
    )

    args = parser.parse_args()

    # Parse target date
    target_date = None
    if args.date:
        try:
            target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            print(f"❌ Invalid date format: {args.date}")
            print("   Use: YYYY-MM-DD (e.g., 2026-03-20)")
            sys.exit(1)

    # Run backtesting
    run_backtest(
        target_date=target_date,
        days_forward=args.days,
        force=args.force
    )


if __name__ == "__main__":
    main()
