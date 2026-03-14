"""
Cron Pipeline Entry Point — Checkpoint-Based Daily Research

Designed to run as a Railway Cron Job (e.g. every day at 14:00 ET).
Each step checks the database first; if a checkpoint exists, it skips
to the next step. This guarantees:
  - No duplicate LLM calls (saves money)
  - Resume-on-failure (断点续传)
  - Total timeout protection with Telegram alerting

Usage:
    python cron_pipeline.py            # run for today
    python cron_pipeline.py 2026-03-14 # run for a specific date
"""

import sys
import asyncio
import traceback
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.config import settings
from app.db.database import SessionLocal, init_db
from app.db.models import DailyDecision
from app.core.notifier import send_alert
from app.pipeline.step1_macro import run_macro_analysis
from app.pipeline.step2_micro import run_micro_scoring
from app.pipeline.step3_risk import run_risk_audit
from app.pipeline.step4_format import normalize_to_weights

PIPELINE_TIMEOUT = 1800  # 30 minutes


async def run_pipeline(target_date: date) -> None:
    """Execute the full 4-step pipeline with checkpoint resume."""
    db: Session = SessionLocal()

    try:
        row = db.query(DailyDecision).filter_by(date=target_date).first()
        if not row:
            row = DailyDecision(date=target_date, status="INIT")
            db.add(row)
            db.commit()

        if row.status == "READY":
            print(f"[{target_date}] Already READY, skipping.")
            return

        # ── Step 1: Macro Analysis ──
        if row.status in ("INIT", "ERROR"):
            print(f"[{target_date}] Running Step 1: Macro Analysis...")
            result = await run_macro_analysis(target_date)
            row.step1_macro_result = result
            row.status = "STEP1_DONE"
            row.error_log = None
            db.commit()
            print(f"[{target_date}] Step 1 done.")

        # ── Step 2: Micro Scoring ──
        if row.status == "STEP1_DONE":
            print(f"[{target_date}] Running Step 2: Micro Scoring...")
            result = await run_micro_scoring(target_date, row.step1_macro_result)
            row.step2_micro_result = result
            row.status = "STEP2_DONE"
            db.commit()
            print(f"[{target_date}] Step 2 done.")

        # ── Step 3: Risk Audit ──
        if row.status == "STEP2_DONE":
            print(f"[{target_date}] Running Step 3: Risk Audit...")
            result = await run_risk_audit(
                target_date, row.step1_macro_result, row.step2_micro_result
            )
            row.step3_risk_result = result
            row.status = "STEP3_DONE"
            db.commit()
            print(f"[{target_date}] Step 3 done.")

        # ── Step 4: Format Weights (pure Python, no LLM) ──
        if row.status == "STEP3_DONE":
            print(f"[{target_date}] Running Step 4: Normalize Weights...")
            weights = normalize_to_weights(row.step2_micro_result, row.step3_risk_result)
            row.final_weights = weights
            row.status = "READY"
            db.commit()
            print(f"[{target_date}] Pipeline complete! Weights: {weights}")

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
