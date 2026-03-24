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
import time
import json
import socket
import asyncio
import traceback
from datetime import date, datetime
from typing import Dict, Any, List

# Force IPv4 — Railway cron containers may have broken IPv6 (IPV6_NDISC_NS_OTHERHOST)
_orig_getaddrinfo = socket.getaddrinfo
def _ipv4_only(*args, **kwargs):
    responses = _orig_getaddrinfo(*args, **kwargs)
    ipv4 = [r for r in responses if r[0] == socket.AF_INET]
    return ipv4 if ipv4 else responses
socket.getaddrinfo = _ipv4_only

import httpx

from sqlalchemy.orm import Session

from app.config import settings
from app.db.database import SessionLocal, init_db
from app.db.models import DailyDecision, DailyHoldings, DailyNewsDigest, DecisionLog
from app.core.notifier import send_alert
from app.pipeline.data_fetcher import (
    fetch_macro_news,
    fetch_economic_calendar,
    fetch_earnings_flag,
)
from app.pipeline.step1_macro import (
    run_macro_analysis,
    format_macro_context,
    Step1Output,
)
from app.pipeline.step2_micro import (
    run_micro_scoring,
    build_news_context_from_db,
    build_sector_context_from_db,
    build_hard_flags_from_db,
)
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

    TIERED OVERRIDE LOGIC:

    Tier A - Geopolitical Emergency: Uses geo_severity (independent of confidence)
             computed from keyword count + event count. Triggers when geo_severity >= 0.5.
             CRITICAL: Decoupled from confidence to prevent Phase 5b contradiction detection
             from blocking legitimate geopolitical overrides.

    Tier B - Confidence-Based: Traditional high-confidence override (>= 80).
    """
    import re

    ai_regime = str(macro_parsed.get("regime", "Neutral"))
    try:
        confidence = int(macro_parsed.get("confidence", 50))
    except (TypeError, ValueError):
        confidence = 50

    # Support both key_events and events keys (for robustness)
    key_events = macro_parsed.get("key_events") or macro_parsed.get("events") or []
    if not isinstance(key_events, list):
        key_events = [str(key_events)]
    reasoning = str(macro_parsed.get("reasoning", ""))

    if not qc_regime:
        return ai_regime, False, "No QC regime provided"

    # Normalize for comparison
    ai_norm = re.sub(r'[^a-z]', '', ai_regime.lower())
    qc_norm = re.sub(r'[^a-z]', '', qc_regime.lower())

    if ai_norm == qc_norm:
        return ai_regime, False, "QC and AI agree"

    # Only allow Risk-Off downgrade overrides (safety constraint)
    if ai_norm != "riskoff":
        return qc_regime, False, f"AI not Risk-Off ({ai_regime}), keeping QC={qc_regime}"

    # ── TIER A: Geopolitical Emergency Override ──
    # Use geo_severity (independent metric) instead of confidence
    # Phase 5b may reduce confidence when detecting contradictions,
    # but geopolitical risks remain real and require defensive positioning
    GEOPOLITICAL_KEYWORDS = [
        "war", "invasion", "attack", "missile", "bombing", "military",
        "oil", "crude", "embargo", "sanctions", "supply disruption",
        "iran", "ukraine", "russia", "israel", "hamas", "strait", "hormuz",
        "opec", "energy crisis", "inflation shock",
    ]

    combined_text = (" ".join(str(e) for e in key_events) + " " + reasoning).lower()
    matches = [kw for kw in GEOPOLITICAL_KEYWORDS if kw in combined_text]

    if matches and len(key_events) >= 2:
        # Compute geo_severity independent of confidence
        # Based on: keyword count + event count
        keyword_score = min(len(matches) / 3.0, 1.0)  # 3+ keywords = max
        event_score = min(len(key_events) / 5.0, 1.0)  # 5+ events = max
        geo_severity = 0.6 * keyword_score + 0.4 * event_score

        # Trigger override if geo_severity >= 0.5 (regardless of confidence)
        if geo_severity >= 0.5:
            reason = (
                f"GEO OVERRIDE: {qc_regime}→{ai_regime} | "
                f"geo_severity={geo_severity:.2f}, keywords={matches[:3]}, "
                f"events={len(key_events)}, conf={confidence}"
            )
            return ai_regime, True, reason

    # ── TIER B: Traditional Confidence-Based Override ──
    if confidence >= 80 and len(key_events) >= 2:
        reason = (
            f"CONF OVERRIDE: {qc_regime}→{ai_regime} | "
            f"conf={confidence}, events={len(key_events)}"
        )
        return ai_regime, True, reason

    # Debug: show why override was blocked
    debug_info = []
    if matches:
        keyword_score = min(len(matches) / 3.0, 1.0)
        event_score = min(len(key_events) / 5.0, 1.0)
        geo_severity = 0.6 * keyword_score + 0.4 * event_score
        debug_info.append(f"geo_severity={geo_severity:.2f}<0.5")
    else:
        debug_info.append("no keywords")
    if confidence < 80:
        debug_info.append(f"conf={confidence}<80")

    return qc_regime, False, (
        f"Override blocked: {', '.join(debug_info)}. "
        f"Keeping QC={qc_regime}"
    )


def _compute_defense_level(effective_regime: str) -> str:
    """Map effective regime to defense level.

    After gated override, the effective regime already reflects the
    correct call. Explicit mapping for all known regime values.
    """
    import re

    # Normalize: remove non-alphabetic chars and lowercase
    r = re.sub(r'[^a-z]', '', effective_regime.lower())

    REGIME_TO_DEFENSE = {
        "riskoff": "half",      # Risk-Off: activate defense
        "neutral": "light",     # Neutral: light defense
        "chop": "light",        # Chop (sideways): treat as neutral
        "riskon": "none",       # Risk-On: no defense
    }

    return REGIME_TO_DEFENSE.get(r, "light")  # Default to light for unknown


def _compute_ema3(current_value: float, db: Session, target_date: date) -> float:
    """Compute 3-day EMA for contradiction score.

    EMA formula: EMA_today = α * value_today + (1-α) * EMA_yesterday
    where α = 2/(N+1) = 2/4 = 0.5 for N=3

    Args:
        current_value: Today's raw contradiction score
        db: Database session
        target_date: Current date

    Returns:
        3-day EMA smoothed score
    """
    from datetime import timedelta

    ALPHA = 0.5  # EMA smoothing factor for N=3

    # Query yesterday's EMA (if exists)
    yesterday = target_date - timedelta(days=1)
    prev_log = db.query(DecisionLog).filter_by(date=yesterday).first()

    if prev_log and prev_log.contradiction_score_ema3 is not None:
        # Use previous EMA
        prev_ema = prev_log.contradiction_score_ema3
        ema = ALPHA * current_value + (1 - ALPHA) * prev_ema
    else:
        # Bootstrap: use current value as EMA
        ema = current_value

    return ema


# ═══════════════════════════════════════════════════════════════
# Main pipeline
# ═══════════════════════════════════════════════════════════════

async def run_pipeline(target_date: date, force: bool = False) -> None:
    """Execute the full 4-step pipeline with checkpoint resume."""
    db: Session = SessionLocal()
    macro_parsed: Dict[str, Any] = {}

    try:
        row = db.query(DailyDecision).filter_by(date=target_date).first()
        if not row:
            row = DailyDecision(date=target_date, status="INIT")
            db.add(row)
            db.commit()

        if row.status == "READY" and not force:
            print(f"[{target_date}] Already READY, skipping. (use --force to re-run)")
            return

        if force and row.status == "READY":
            print(f"[{target_date}] Force re-run: resetting READY → INIT")
            row.status = "INIT"
            row.step1_macro_result = None
            row.step2_micro_result = None
            row.step3_risk_result = None
            row.final_weights = None
            row.error_log = None
            db.commit()

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

            step1_result = await run_macro_analysis(
                target_date,
                macro_news=macro_news,
                econ_calendar=econ_calendar,
                history_block=history_block,
                db=db,  # Phase 1: Pass db to get QC quantitative indicators
            )
            macro_parsed = step1_result.model_dump()

            row.step1_macro_result = json.dumps(macro_parsed, ensure_ascii=False)
            row.status = "STEP1_DONE"
            row.error_log = None
            db.commit()

            # ── Write DailyNewsDigest ──
            digest = db.query(DailyNewsDigest).filter_by(date=target_date).first()
            if not digest:
                digest = DailyNewsDigest(date=target_date)
                db.add(digest)
            digest.macro_summary = step1_result.summary
            digest.macro_regime = step1_result.regime
            digest.confidence = step1_result.confidence
            digest.key_events = step1_result.key_events
            db.commit()

            # ── Phase 2: Store transmission vector to event_transmission table ──
            if step1_result.transmission_vector:
                from app.db.models import EventTransmission
                from app.pipeline.transmission_rules import detect_event_type

                event_id = f"macro_{target_date.isoformat()}"
                event_type = detect_event_type(step1_result.key_events, step1_result.reasoning)

                # Check if record already exists
                existing = db.query(EventTransmission).filter_by(event_id=event_id).first()
                if existing:
                    # Update existing record
                    existing.date = target_date
                    existing.event_type = event_type
                    existing.event_description = step1_result.summary
                    existing.confidence = step1_result.confidence
                    existing.transmission_vector = step1_result.transmission_vector
                else:
                    # Create new record
                    db.add(EventTransmission(
                        date=target_date,
                        event_id=event_id,
                        event_type=event_type,
                        event_description=step1_result.summary,
                        confidence=step1_result.confidence,
                        transmission_vector=step1_result.transmission_vector,
                    ))
                db.commit()
                print(f"[{target_date}]   Transmission vector stored: {event_type}")

            print(f"[{target_date}] Step 1 done.")
            print(f"[{target_date}]   Regime: {step1_result.regime} "
                  f"(confidence: {step1_result.confidence})")
            print(f"[{target_date}]   Summary: {step1_result.summary}")
            print(f"[{target_date}]   Events: {step1_result.key_events}")
            print(f"[{target_date}]   Reasoning: {step1_result.reasoning[:200]}")

            # Phase 3a: Print event direction analysis
            if step1_result.net_escalation_score is not None:
                print(f"[{target_date}]   [Phase 3a] Net Escalation: {step1_result.net_escalation_score:.2f}")
                print(f"[{target_date}]   [Phase 3a] Regime Phase: {step1_result.regime_phase}")
                if step1_result.event_direction_reasoning:
                    print(f"[{target_date}]   [Phase 3a] {step1_result.event_direction_reasoning}")

            # Phase 3b: Print duration estimate
            if step1_result.duration_estimate:
                print(f"[{target_date}]   [Phase 3b] Duration: {step1_result.duration_estimate}")
                print(f"[{target_date}]   [Phase 3b] Category: {step1_result.duration_category}")
                if step1_result.exit_strategy:
                    print(f"[{target_date}]   [Phase 3b] Exit Strategy: {step1_result.exit_strategy[:120]}...")

            # Phase 3c: Print regime transition analysis
            if step1_result.transition_probability is not None:
                warning_flag = "⚠️ " if step1_result.early_warning else ""
                print(f"[{target_date}]   [Phase 3c] {warning_flag}Transition Probability: {step1_result.transition_probability:.0%}")
                if step1_result.transition_direction:
                    print(f"[{target_date}]   [Phase 3c] Direction: {step1_result.transition_direction}")
                print(f"[{target_date}]   [Phase 3c] Confidence Trend: {step1_result.confidence_trend}")
                if step1_result.pivot_signals:
                    met_count = sum(1 for s in step1_result.pivot_signals if s.get("status") == "met")
                    print(f"[{target_date}]   [Phase 3c] Pivot Signals: {met_count}/{len(step1_result.pivot_signals)} met")

        # ── Restore macro_parsed on checkpoint resume ──
        if not macro_parsed and row.step1_macro_result:
            try:
                macro_parsed = json.loads(row.step1_macro_result)
            except json.JSONDecodeError:
                macro_parsed = {"regime": "Neutral", "confidence": 50, "summary": "", "key_events": [], "reasoning": ""}

        macro_context_str = format_macro_context(macro_parsed)

        # ── Step 2: Micro Scoring (holdings + pre-fetched news + earnings) ──
        if row.status == "STEP1_DONE":
            print(f"[{target_date}] Running Step 2: Micro Scoring...")

            holdings_row = db.query(DailyHoldings).filter_by(date=target_date).first()
            tickers = holdings_row.tickers if holdings_row else None
            print(f"[{target_date}]   Holdings: {tickers or '(none reported)'}")

            # Collect all tickers: holdings + top_candidates
            all_tickers = list(tickers) if tickers else []
            if holdings_row and holdings_row.payload:
                candidates = holdings_row.payload.get("top_candidates", [])
                for c in candidates:
                    if c not in all_tickers:
                        all_tickers.append(c)

            news_digest_str = "(No news data available)"
            sector_context_str = "(No sector data available)"
            earnings_flags: dict = {}
            hard_flags: Dict[str, List[str]] = {}

            if all_tickers:
                print(f"[{target_date}]   Reading pre-fetched news from DB for {len(all_tickers)} tickers...")
                news_digest_str = build_news_context_from_db(db, all_tickers, target_date)

                print(f"[{target_date}]   Reading sector outlooks from DB...")
                sector_context_str = build_sector_context_from_db(db, target_date)

                hard_flags = build_hard_flags_from_db(db, all_tickers, target_date)
                if hard_flags:
                    print(f"[{target_date}]   ⚠ Hard events from library: {list(hard_flags.keys())}")
                else:
                    print(f"[{target_date}]   No hard events in library")

                print(f"[{target_date}]   Checking earnings calendar...")
                earnings_flags = {t: fetch_earnings_flag(t) for t in all_tickers}
                upcoming = [t for t, v in earnings_flags.items() if v]
                print(f"[{target_date}]   Earnings upcoming: {upcoming or 'none'}")

            # Phase 2: Extract transmission vector from macro_parsed
            transmission = macro_parsed.get("transmission_vector", {}) if macro_parsed else {}
            if transmission:
                top_impacts = sorted(transmission.items(), key=lambda x: -abs(x[1]))[:3]
                print(f"[{target_date}]   Transmission vector: {', '.join(f'{s}={v:+.2f}' for s, v in top_impacts)}")

            result = await run_micro_scoring(
                target_date,
                macro_context_str,
                holdings=tickers,
                news_digest=news_digest_str,
                sector_context=sector_context_str,
                earnings_flags=earnings_flags,
                hard_flags=hard_flags,
                transmission_vector=transmission,
            )
            row.step2_micro_result = result
            row.status = "STEP2_DONE"
            db.commit()

            # ── Update DailyNewsDigest with ticker_risks from library ──
            if all_tickers:
                hard_flags = build_hard_flags_from_db(db, all_tickers, target_date)
                ticker_risks = {}
                for t in all_tickers:
                    if t in hard_flags:
                        ticker_risks[t] = {
                            "risk": "high",
                            "reason": hard_flags[t][0],
                            "flags": hard_flags[t],
                        }
                    elif earnings_flags.get(t):
                        ticker_risks[t] = {
                            "risk": "high",
                            "reason": "Upcoming earnings event",
                            "flags": ["earnings_soon"],
                        }
                    else:
                        ticker_risks[t] = {"risk": "low", "reason": "Normal", "flags": []}

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
            print(f"[{target_date}] Running Step 4: Normalize Weights...", flush=True)
            weights = normalize_to_weights(row.step2_micro_result, row.step3_risk_result)
            row.final_weights = weights
            row.status = "READY"
            db.commit()
            print(f"[{target_date}] Step 4 done.")

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

            # ── Phase 5b: Store contradiction score with EMA smoothing ──
            contradiction_raw = macro_parsed.get("llm_contradiction_score")
            if contradiction_raw is not None:
                log.contradiction_score_raw = float(contradiction_raw)
                log.contradiction_score_ema3 = _compute_ema3(
                    float(contradiction_raw), db, target_date
                )
            log.llm_confidence_adjustment = macro_parsed.get("llm_confidence_adjustment")

            log.reasoning = (
                f"{macro_parsed.get('reasoning', '')}\n"
                f"Override: {override_reason}"
            )
            if risk_flags_summary:
                log.reasoning += f"\nHard risk flags: {json.dumps(risk_flags_summary)}"
            db.commit()

            print(f"[{target_date}]   QC regime: {qc_regime} | AI regime: {log.ai_regime}")
            print(f"[{target_date}]   Override: {was_overridden} → Effective: {effective_regime}")
            print(f"[{target_date}]   Defense: {defense} | Reason: {override_reason}")
            if risk_flags_summary:
                print(f"[{target_date}]   Hard risks: {risk_flags_summary}")
            print(f"[{target_date}]   Tickers: {len(weights)}  Weights: {weights}")
            print(f"[{target_date}]   Sum: {sum(weights.values()):.4f}")
            print(f"[{target_date}] Pipeline complete!", flush=True)

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


def _wait_for_network(max_retries: int = 10, delay: int = 5) -> bool:
    """Block until outbound HTTPS is reachable (cold-start network init)."""
    time.sleep(3)
    targets = ["https://api.openai.com", "https://finnhub.io", "https://1.1.1.1"]
    for i in range(max_retries):
        for url in targets:
            try:
                httpx.get(url, timeout=5)
                print(f"[NET] Network ready (via {url})")
                return True
            except Exception:
                pass
        print(f"[NET] Waiting for network... attempt {i + 1}/{max_retries}")
        time.sleep(delay)
    return False


async def main() -> None:
    """Entry point with global timeout and Telegram alerting."""
    force = "--force" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--force"]
    target = date.today()
    if args:
        target = datetime.strptime(args[0], "%Y-%m-%d").date()

    print(f"=== Cron Pipeline Start: {target} {'(FORCE)' if force else ''} ===")

    net_ok = _wait_for_network()
    if not net_ok:
        print("[WARN] Network unreachable — proceeding with DB-only data, LLM calls may fail")

    init_db()

    try:
        await asyncio.wait_for(run_pipeline(target, force=force), timeout=PIPELINE_TIMEOUT)
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
