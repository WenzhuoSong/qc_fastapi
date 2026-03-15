"""
Combined Pipeline — Pre-Fetch + Main Cron in a single process.

Use this when both pipelines must run from the same Railway service
(e.g. when one cron service lacks outbound network access).

Usage:
    python run_all.py              # run both for today
    python run_all.py 2026-03-15   # specific date
    python run_all.py --force      # clear and re-run everything

Railway Cron (EDT): 30 17 * * 1-5  (13:30 ET — pre-fetch starts, main follows)
Railway Cron (EST): 30 18 * * 1-5
"""

import sys
import asyncio
from datetime import date, datetime

from pre_fetch_pipeline import (
    run_pre_fetch,
    _wait_for_network,
    PRE_FETCH_TIMEOUT,
)
from cron_pipeline import run_pipeline, PIPELINE_TIMEOUT, send_alert
from app.db.database import init_db


async def main() -> None:
    force = "--force" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--force"]
    target = date.today()
    if args:
        target = datetime.strptime(args[0], "%Y-%m-%d").date()

    print(f"=== Combined Pipeline Start: {target} {'(FORCE)' if force else ''} ===")

    if not _wait_for_network():
        print("[FATAL] Network unavailable after retries, aborting")
        sys.exit(1)

    init_db()

    # Phase 1: Pre-Fetch
    try:
        print(f"\n{'='*50}")
        print(f"  Phase 1: Pre-Fetch News")
        print(f"{'='*50}")
        await asyncio.wait_for(run_pre_fetch(target, force=force), timeout=PRE_FETCH_TIMEOUT)
        print(f"=== Pre-Fetch Success ===\n")
    except asyncio.TimeoutError:
        print(f"[WARN] Pre-fetch TIMEOUT after {PRE_FETCH_TIMEOUT}s — continuing to main pipeline")
    except Exception as e:
        print(f"[WARN] Pre-fetch failed: {e} — continuing to main pipeline")

    # Phase 2: Main Pipeline
    try:
        print(f"{'='*50}")
        print(f"  Phase 2: Main Pipeline (Steps 1-4)")
        print(f"{'='*50}")
        await asyncio.wait_for(run_pipeline(target, force=force), timeout=PIPELINE_TIMEOUT)
        print(f"=== Main Pipeline Success ===")
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

    print(f"\n=== Combined Pipeline Done: {target} ===")


if __name__ == "__main__":
    asyncio.run(main())
