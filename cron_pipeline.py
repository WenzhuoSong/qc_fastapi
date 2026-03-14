"""
Cron Pipeline Entry Point — Checkpoint-Based Daily Research

Designed to run as a Railway Cron Job (e.g. every day at 14:00 ET).
Each step checks the database first; if a checkpoint exists, it skips
to the next step. This guarantees:
  - No duplicate LLM calls (saves money)
  - Resume-on-failure
  - Total timeout protection with Telegram alerting

Usage:
    python cron_pipeline.py            # run for today
    python cron_pipeline.py 2026-03-14 # run for a specific date
"""

import sys
import json
import asyncio
import traceback
from datetime import date, datetime
from typing import Dict, Any

from sqlalchemy.orm import Session

from app.config import settings
from app.db.database import SessionLocal, init_db
from app.db.models import DailyDecision, DailyHoldings, DailyNewsDigest, DecisionLog
from app.core.notifier import send_alert
from app.pipeline.data_fetcher import (
    fetch_macro_news,
    fetch_economic_calendar,
    fetch_all_holdings_news,
    fetch_earnings_flag,
)
from app.pipeline.step1_macro import (
    run_macro_analysis,
    parse_macro_output,
    format_macro_context,
)
from app.pipeline.step2_micro import run_micro_scoring
from app.pipeline.step3_risk import run_risk_audit
from app.pipeline.step4_format import normalize_to_weights

PIPELINE_TIMEOUT = 1800  # 30 minutes
def _build_history_block(db: Session, limit: int = 5) -> str:
    """Load recent DailyNewsDigest rows and format into a history block."""
    rows = (
        db.query(DailyNewsDigest)
        .order_by(DailyNewsDigest.date.desc())
        .limit(limit)
        .all()
    )
    if not rows:
        return "(No historical context yet — first run)"

    lines = []
    for d in reversed(rows):
        events = ", ".join(d.key_events) if d.key_events else "N/A"
        summary = d.macro_summary or "N/A"
        lines.append(f"{d.date} [{d.macro_regime}]: {summary} | Key: {events}")
    return "\n".join(lines)


def _compute_defense_level(qc_regime: str | None, ai_regime: str) -> str:
    """Derive defense level from QC vs AI regime comparison.

    Rules:
      - QC=bear OR AI=Risk-Off → half  (strong caution)
      - AI=Neutral             → light (mild caution)
      - Otherwise              → full  (both bullish / risk-on)
    """
    ai = ai_regime.lower().replace("-", "").replace(" ", "")
    qc = (qc_regime or "").lower().strip()

    if qc == "bear" or ai == "riskoff":
        return "half"
    if ai == "neutral":
        return "light"
    return "full"


def _build_ticker_risks(
    tickers: list, earnings_flags: Dict[str, bool], news: Dict[str, list]
) -> Dict[str, dict]:
    """Derive per-ticker risk assessments from available data."""
    risks = {}
    for t in tickers:
        if earnings_flags.get(t):
            risks[t] = {"risk": "high", "reason": "Upcoming earnings event"}
        elif not news.get(t):
            risks[t] = {"risk": "medium", "reason": "No recent news coverage"}
        else:
            risks[t] = {"risk": "low", "reason": "Normal — news available, no earnings"}
    return risks


async def run_pipeline(target_date: date) -> None:
    """Execute the full 4-step pipeline with checkpoint resume."""
    db: Session = SessionLocal()
    macro_parsed: Dict[str, Any] = {}

    try:
        row = db.query(DailyDecision).filter_by(date=target_date).first()
        if not row:
            row = DailyDecision(date=target_date, status="INIT")
            db.add(row)
            db.commit()

        if row.status == "READY":
            print(f"[{target_date}] Already READY, skipping.")
            return

        # ── Step 1: Macro Analysis (with real news + calendar + history) ──
        if row.status in ("INIT", "ERROR"):
            print(f"[{target_date}] Running Step 1: Macro Analysis...")

            print(f"[{target_date}]   Fetching macro news...")
            macro_news = fetch_macro_news()
            print(f"[{target_date}]   Got {len(macro_news)} news articles")

            print(f"[{target_date}]   Fetching economic calendar...")
            econ_calendar = fetch_economic_calendar()
            print(f"[{target_date}]   Got {len(econ_calendar)} high-impact events")

            history_block = _build_history_block(db)
            print(f"[{target_date}]   History context loaded")

            macro_parsed = await run_macro_analysis(
                target_date,
                macro_news=macro_news,
                econ_calendar=econ_calendar,
                history_block=history_block,
            )

            row.step1_macro_result = json.dumps(macro_parsed, ensure_ascii=False)
            row.status = "STEP1_DONE"
            row.error_log = None
            db.commit()

            # ── Write DailyNewsDigest ──
            digest = db.query(DailyNewsDigest).filter_by(date=target_date).first()
            if not digest:
                digest = DailyNewsDigest(date=target_date)
                db.add(digest)
            digest.macro_summary = macro_parsed.get("summary", "")
            digest.macro_regime = macro_parsed.get("regime", "Neutral")
            digest.confidence = macro_parsed.get("confidence", 50)
            digest.key_events = macro_parsed.get("key_events", [])
            digest.sector_thesis = macro_parsed.get("sector_thesis", "")
            db.commit()

            print(f"[{target_date}] Step 1 done.")
            print(f"[{target_date}]   Regime: {macro_parsed.get('regime')} "
                  f"(confidence: {macro_parsed.get('confidence')})")
            print(f"[{target_date}]   Summary: {macro_parsed.get('summary', '')[:200]}")

        # ── Restore macro_parsed on checkpoint resume ──
        if not macro_parsed and row.step1_macro_result:
            try:
                macro_parsed = json.loads(row.step1_macro_result)
            except json.JSONDecodeError:
                macro_parsed = parse_macro_output(row.step1_macro_result)

        macro_context_str = format_macro_context(macro_parsed)

        # ── Step 2: Micro Scoring (holdings + news + earnings) ──
        if row.status == "STEP1_DONE":
            print(f"[{target_date}] Running Step 2: Micro Scoring...")

            holdings_row = db.query(DailyHoldings).filter_by(date=target_date).first()
            tickers = holdings_row.tickers if holdings_row else None
            print(f"[{target_date}]   Holdings: {tickers or '(none reported)'}")

            news: dict = {}
            earnings_flags: dict = {}

            if tickers:
                print(f"[{target_date}]   Fetching company news...")
                news = fetch_all_holdings_news(tickers)
                print(f"[{target_date}]   News fetched for {len(news)} tickers")

                print(f"[{target_date}]   Checking earnings calendar...")
                earnings_flags = {t: fetch_earnings_flag(t) for t in tickers}
                upcoming = [t for t, v in earnings_flags.items() if v]
                print(f"[{target_date}]   Earnings upcoming: {upcoming or 'none'}")

            result = await run_micro_scoring(
                target_date,
                macro_context_str,
                holdings=tickers,
                news=news,
                earnings_flags=earnings_flags,
            )
            row.step2_micro_result = result
            row.status = "STEP2_DONE"
            db.commit()

            # ── Update DailyNewsDigest with ticker_risks ──
            if tickers:
                ticker_risks = _build_ticker_risks(tickers, earnings_flags, news)
                digest = db.query(DailyNewsDigest).filter_by(date=target_date).first()
                if digest:
                    digest.ticker_risks = ticker_risks
                    db.commit()

            print(f"[{target_date}] Step 2 done.")
            print(f"[{target_date}]   Micro output (first 500 chars): {result[:500]}")

        # ── Step 3: Risk Audit ──
        if row.status == "STEP2_DONE":
            print(f"[{target_date}] Running Step 3: Risk Audit...")
            result = await run_risk_audit(
                target_date, macro_context_str, row.step2_micro_result
            )
            row.step3_risk_result = result
            row.status = "STEP3_DONE"
            db.commit()
            print(f"[{target_date}] Step 3 done.")
            print(f"[{target_date}]   Risk output (first 500 chars): {result[:500]}")

        # ── Step 4: Format Weights (pure Python, no LLM) ──
        if row.status == "STEP3_DONE":
            print(f"[{target_date}] Running Step 4: Normalize Weights...")
            weights = normalize_to_weights(row.step2_micro_result, row.step3_risk_result)
            row.final_weights = weights
            row.status = "READY"
            db.commit()

            # ── Write DecisionLog ──
            holdings_row = db.query(DailyHoldings).filter_by(date=target_date).first()
            qc_regime = None
            if holdings_row and holdings_row.payload:
                qc_regime = holdings_row.payload.get("qc_regime")

            ai_regime = macro_parsed.get("regime", "Neutral")
            regime_override = (
                qc_regime is not None
                and qc_regime.lower() != ai_regime.lower()
            )

            log = db.query(DecisionLog).filter_by(date=target_date).first()
            if not log:
                log = DecisionLog(date=target_date)
                db.add(log)
            log.qc_regime = qc_regime
            log.ai_regime = ai_regime
            log.regime_override = regime_override
            log.confidence = macro_parsed.get("confidence", 50)
            log.defense_level = _compute_defense_level(qc_regime, ai_regime)
            log.final_weights = weights
            log.reasoning = macro_parsed.get("reasoning", "")
            db.commit()

            print(f"[{target_date}] Pipeline complete!")
            print(f"[{target_date}]   Regime: {ai_regime} | QC: {qc_regime} | "
                  f"Override: {regime_override} | Defense: {log.defense_level}")
            print(f"[{target_date}]   Tickers: {len(weights)}  Weights: {weights}")
            print(f"[{target_date}]   Sum: {sum(weights.values()):.4f}")

    except Exception as e:
        error_msg = traceback.format_exc()
        try:
            row.status = "ERROR"
            row.error_log = error_msg
            db.commit()
        except Exception:
            pass
        raise e

    finally:
        db.close()


async def main() -> None:
    """Entry point with global timeout and Telegram alerting."""
    target = date.today()
    if len(sys.argv) > 1:
        target = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()

    print(f"=== Cron Pipeline Start: {target} ===")

    init_db()

    try:
        await asyncio.wait_for(run_pipeline(target), timeout=PIPELINE_TIMEOUT)
        print(f"=== Cron Pipeline Success: {target} ===")
    except asyncio.TimeoutError:
        msg = f"Pipeline TIMEOUT after {PIPELINE_TIMEOUT}s for {target}"
        print(f"[FATAL] {msg}")
        await send_alert(msg)
        sys.exit(1)
    except Exception as e:
        msg = f"Pipeline CRASHED for {target}: {e}"
        print(f"[FATAL] {msg}")
        await send_alert(msg)
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
