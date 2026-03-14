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
from typing import Dict, Any, List

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
    scan_all_holdings_risks,
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


# ═══════════════════════════════════════════════════════════════
# Helper functions
# ═══════════════════════════════════════════════════════════════

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


def _apply_regime_override(
    qc_regime: str | None, macro_parsed: Dict[str, Any]
) -> tuple[str, bool, str]:
    """Gated regime override — AI can only DOWNGRADE, never upgrade.

    Returns (effective_regime, was_overridden, override_reason).

    Override requires ALL conditions:
      1. AI confidence >= 80
      2. AI regime differs from QC
      3. AI has >= 2 key events as evidence
      4. AI regime is Risk-Off (downgrade only)
    """
    ai_regime = macro_parsed.get("regime", "Neutral")
    confidence = macro_parsed.get("confidence", 50)
    key_events = macro_parsed.get("key_events", [])

    if qc_regime is None:
        return ai_regime, False, "No QC regime provided"

    if qc_regime.lower() == ai_regime.lower().replace("-", "").replace(" ", ""):
        return ai_regime, False, "QC and AI agree"

    conditions = [
        confidence >= 80,
        len(key_events) >= 2,
        ai_regime.lower().replace("-", "").replace(" ", "") == "riskoff",
    ]

    if all(conditions):
        reason = (
            f"AI override: {qc_regime}→{ai_regime} "
            f"(confidence={confidence}, events={key_events[:3]})"
        )
        return ai_regime, True, reason

    reason = (
        f"Override blocked: confidence={confidence}, "
        f"events={len(key_events)}, ai_regime={ai_regime}. "
        f"Keeping QC regime={qc_regime}"
    )
    return qc_regime, False, reason


def _compute_defense_level(effective_regime: str) -> str:
    """Map effective regime to defense level.

    After gated override, the effective regime already reflects the
    correct call. Simple mapping:
      Risk-Off → half
      Neutral  → light
      else     → full
    """
    r = effective_regime.lower().replace("-", "").replace(" ", "")
    if r == "riskoff":
        return "half"
    if r == "neutral":
        return "light"
    return "full"


def _build_ticker_risks(
    tickers: List[str],
    hard_risks: Dict[str, Dict[str, str]],
    earnings_flags: Dict[str, bool],
    news: Dict[str, list],
) -> Dict[str, dict]:
    """Combine hard risk scan with earnings/news data for DailyNewsDigest."""
    risks = {}
    for t in tickers:
        t_hard = hard_risks.get(t, {})
        if t_hard:
            top_risk = next(iter(t_hard))
            risks[t] = {
                "risk": "high",
                "reason": t_hard[top_risk],
                "flags": list(t_hard.keys()),
            }
        elif earnings_flags.get(t):
            risks[t] = {"risk": "high", "reason": "Upcoming earnings event", "flags": ["earnings_soon"]}
        elif not news.get(t):
            risks[t] = {"risk": "medium", "reason": "No recent news coverage", "flags": []}
        else:
            risks[t] = {"risk": "low", "reason": "Normal", "flags": []}
    return risks


# ═══════════════════════════════════════════════════════════════
# Main pipeline
# ═══════════════════════════════════════════════════════════════

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
            print(f"[{target_date}]   Got {len(econ_calendar)} events")

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

        # ── Step 2: Micro Scoring (holdings + news + earnings + hard risks) ──
        if row.status == "STEP1_DONE":
            print(f"[{target_date}] Running Step 2: Micro Scoring...")

            holdings_row = db.query(DailyHoldings).filter_by(date=target_date).first()
            tickers = holdings_row.tickers if holdings_row else None
            print(f"[{target_date}]   Holdings: {tickers or '(none reported)'}")

            news: dict = {}
            earnings_flags: dict = {}
            hard_risks: dict = {}

            if tickers:
                print(f"[{target_date}]   Fetching company news...")
                news = fetch_all_holdings_news(tickers)
                print(f"[{target_date}]   News fetched for {len(news)} tickers")

                print(f"[{target_date}]   Checking earnings calendar...")
                earnings_flags = {t: fetch_earnings_flag(t) for t in tickers}
                upcoming = [t for t, v in earnings_flags.items() if v]
                print(f"[{target_date}]   Earnings upcoming: {upcoming or 'none'}")

                print(f"[{target_date}]   Scanning hard risks...")
                hard_risks = scan_all_holdings_risks(tickers, news, earnings_flags)
                flagged = {t: list(r.keys()) for t, r in hard_risks.items() if r}
                if flagged:
                    print(f"[{target_date}]   ⚠ Hard risk flags: {flagged}")
                else:
                    print(f"[{target_date}]   No hard risk flags")

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
                ticker_risks = _build_ticker_risks(tickers, hard_risks, earnings_flags, news)
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

        # ── Step 4: Format Weights + Gated Regime Override ──
        if row.status == "STEP3_DONE":
            print(f"[{target_date}] Running Step 4: Normalize Weights...")
            weights = normalize_to_weights(row.step2_micro_result, row.step3_risk_result)
            row.final_weights = weights
            row.status = "READY"
            db.commit()

            # ── Gated Regime Override ──
            holdings_row = db.query(DailyHoldings).filter_by(date=target_date).first()
            qc_regime = None
            if holdings_row and holdings_row.payload:
                qc_regime = holdings_row.payload.get("qc_regime")

            effective_regime, was_overridden, override_reason = _apply_regime_override(
                qc_regime, macro_parsed
            )
            defense = _compute_defense_level(effective_regime)

            # ── Collect hard risk flags for DecisionLog ──
            digest = db.query(DailyNewsDigest).filter_by(date=target_date).first()
            risk_flags_summary = {}
            if digest and digest.ticker_risks:
                for t, info in digest.ticker_risks.items():
                    flags = info.get("flags", [])
                    if flags:
                        risk_flags_summary[t] = flags

            # ── Write DecisionLog ──
            log = db.query(DecisionLog).filter_by(date=target_date).first()
            if not log:
                log = DecisionLog(date=target_date)
                db.add(log)
            log.qc_regime = qc_regime
            log.ai_regime = macro_parsed.get("regime", "Neutral")
            log.regime_override = was_overridden
            log.confidence = macro_parsed.get("confidence", 50)
            log.defense_level = defense
            log.final_weights = weights
            log.reasoning = (
                f"{macro_parsed.get('reasoning', '')}\n"
                f"Override: {override_reason}"
            )
            if risk_flags_summary:
                log.reasoning += f"\nHard risk flags: {json.dumps(risk_flags_summary)}"
            db.commit()

            print(f"[{target_date}] Pipeline complete!")
            print(f"[{target_date}]   QC regime: {qc_regime} | AI regime: {log.ai_regime}")
            print(f"[{target_date}]   Override: {was_overridden} → Effective: {effective_regime}")
            print(f"[{target_date}]   Defense: {defense} | Reason: {override_reason}")
            if risk_flags_summary:
                print(f"[{target_date}]   Hard risks: {risk_flags_summary}")
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
