# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Start the API gateway (dev)
python run.py
# API docs at http://localhost:8000/docs

# Run tests
pytest tests/ -v

# Run a single test
pytest tests/test_api.py::test_health_check -v

# Run the cron pipeline
python cron_pipeline.py                  # today
python cron_pipeline.py 2026-03-14       # specific date
python cron_pipeline.py --force          # re-run even if READY

# Run the pre-fetch pipeline
python pre_fetch_pipeline.py

# Code formatting (line length: 100)
black app/ tests/
```

## Architecture

This is a **quantitative trading backend** with a strict separation between computation (cron jobs) and delivery (FastAPI gateway). The API is read-only — it only serves pre-computed data from PostgreSQL.

### Two-Process Design

1. **`pre_fetch_pipeline.py`** (runs 13:30 ET) — Fetches Finnhub news for all holdings/candidates, batch-summarizes with LLM, stores to `ticker_news_library` and `sector_news_library`.

2. **`cron_pipeline.py`** (runs 14:00 ET) — 4-step checkpoint pipeline that reads from DB (no real-time API calls for news), calls OpenAI for macro/micro/risk analysis, writes final weights to `daily_decisions`.

3. **FastAPI app** (`python run.py`) — Read-only gateway that serves pre-computed allocation from `daily_decisions`. Target <10ms response.

### Pipeline Steps (`app/pipeline/`)

- **Step 1** (`step1_macro.py`) — Calls `gpt-4o` with macro news + economic calendar + 5-day history. Returns `Step1Output` (Pydantic structured output): regime, confidence, key_events, reasoning.
- **Step 2** (`step2_micro.py`) — ETF sector scoring using **2-pass process** defined in `prompts.py`:
  - **Pass 1 (Top-Down)**: Scan macro key_events and apply mandatory score constraints from the **Macro Event Transmission Rules** table (e.g., Hormuz closure → XLE >= 7). These constraints OVERRIDE individual ticker news for directly impacted sectors.
  - **Pass 2 (Bottom-Up)**: Use portfolio holdings, pre-fetched ticker news, sector outlooks, and earnings flags to refine remaining sectors.
- **Step 3** (`step3_risk.py`) — Risk audit and guardrail adjustments on Step 2 scores.
- **Step 4** (`step4_format.py`) — Normalizes scores to portfolio weights summing to 1.0.
- After Step 4: **Gated Regime Override** — AI can only downgrade (to Risk-Off), never upgrade. Requires confidence >= 80, >= 2 key events, AI regime differs from QC regime.

### Checkpoint State Machine

`DailyDecision.status`: `INIT → STEP1_DONE → STEP2_DONE → STEP3_DONE → READY` (or `ERROR`)

Pipeline is idempotent — crashing at any step allows resume from last checkpoint. Use `--force` to reset a READY record.

### Database Tables (PostgreSQL, SQLAlchemy ORM)

| Table | Purpose |
|-------|---------|
| `daily_decisions` | Checkpoint state + intermediate results + final weights |
| `daily_holdings` | Holdings snapshot from QuantConnect (POST at 10:00/13:30 ET) |
| `daily_news_digest` | Macro summary + regime + ticker_risks (written per pipeline run) |
| `decision_log` | QC vs AI regime audit trail with post-hoc correctness fields |
| `ticker_news_library` | Per-ticker news headlines with LLM summaries, sentiment, hard-event flags |
| `sector_news_library` | Sector ETF daily outlook synthesized from constituent ticker news |

Models are in `app/db/models.py`. Database initializes lazily via `init_db()`.

### Key Design Constraints

- **AI subtracts, never adds**: regime override is one-directional (Risk-On → Risk-Off only).
- **Defense levels**: `Risk-Off` → `half` (50%), `Neutral` → `light` (70%), `Risk-On` → `full` (100%).
- **Hard risk flags**: `earnings_soon`, `fda_pending`, `trading_halted`, `acquisition_target`, `major_lawsuit` — tickers with these are excluded from new buys in QuantConnect.
- **`is_stale`** in allocation response: true if today's pipeline hasn't run — QuantConnect should hold positions, not rebalance.

### Configuration (`app/config.py`)

Uses Pydantic `BaseSettings` loading from `.env`. Copy `env_example.txt` to `.env`. Required keys: `OPENAI_API_KEY`, `API_TOKEN`, `DATABASE_URL`, `FINNHUB_API_KEY`. Leave `API_TOKEN` empty to disable auth in local dev (no DB needed for health/root endpoints).

### Authentication

All `/api/v1/` endpoints (except `/health/`) require authentication via `app/core/security.py`:
- **Standard**: `Authorization: Bearer <API_TOKEN>` header
- **QC-compatible**: `?token=<API_TOKEN>` query parameter (fallback for `/allocation/` since QuantConnect's `self.Download()` cannot set custom headers)
- `verify_token` — Bearer-only auth (used by most endpoints)
- `verify_token_flexible` — Bearer OR query param (used by `/allocation/` and `/holdings/submit`)

### Legacy Endpoints

**Removed 2026-03-22:** CrewAI endpoints (`/crew/`, `/tasks/`) and `app/services/` directory cleaned up before Phase 2. The following files were deleted:
- `example_usage.py` (144 lines)
- `app/services/` (agents.py, crew_service.py, tasks_def.py - ~300 lines)
- `app/api/v1/endpoints/crew.py` (88 lines)
- `app/api/v1/endpoints/tasks.py` (90 lines)

Total: ~600 lines of unused CrewAI code removed.

### Prompt Engineering (`app/pipeline/step2_micro.py`)

Step 2 scoring uses inline `STEP2_SYSTEM` prompt with transmission rules. Critical:
- **Macro Event Transmission Rules** — Mandatory floors/ceilings mapping macro events to sector impacts. When modifying:
  - Constraints are **bidirectional** (both floor `>=` and ceiling `<=`)
  - Multiple rules can apply simultaneously
  - Trigger keywords must match Step 1's `key_events`
- **Phase 1 Credibility Weighting** (2026-03-22) — News credibility guides LLM attention:
  - High-credibility sources (Bloomberg=100, Reuters=100) emphasized with bold markdown
  - Low-credibility sources (<40) tagged to reduce noise
  - Prompt instructs: "HIGH-CREDIBILITY SOURCE ALWAYS WINS" when news conflicts

### Phase 1 Implementation (2026-03-17 to 2026-03-22)

**Objective**: Increase information density without adding API calls — leverage existing Finnhub fields.

**Enhancements**:
1. **Database Schema** — Added 5 columns to `ticker_news_library`:
   - `category` (VARCHAR50) — Event type classification
   - `related` (JSONB) — Related tickers for contagion analysis
   - `datetime_utc` (INTEGER) — Precise timestamp for recency
   - `url` (TEXT) — Source link
   - `credibility` (INTEGER 0-100) — Source trustworthiness

2. **Data Collection** (`pre_fetch_pipeline.py`):
   - Source credibility scoring: Bloomberg=100, Reuters=100, Seeking Alpha=60, PR=40
   - Sector aggregation prioritizes high-credibility (sorted by cred)
   - Displays credibility in LLM prompt: `(cred:100)`

3. **Step 1 Integration** (`step1_macro.py`):
   - Extracts QC quantitative indicators from `DailyHoldings.payload.qc_regime_detail`
   - Cross-validates news vs technicals (SPY/MA200, HYG/IEF, breadth)
   - 4 cross-check rules prevent false signals

4. **Step 2 Enhancement** (`step2_micro.py`):
   - News sorted by credibility (desc) then recency
   - High-cred news (≥85) in **bold**, low-cred (≤40) tagged `[low-cred:XX]`
   - Recency: `[breaking]` for <6h news
   - Event categories: `[earnings]`, `[FDA]`, `[merger]`
   - Contagion: 🔗 CONTAGION RISK from related tickers
   - Sector context: `[high-cred:XX]` or `[low-cred:XX]` average
   - Explicit prompt rule: "HIGH-CREDIBILITY SOURCE ALWAYS WINS"

**Expected Impact**: Regime accuracy +10-15%, reduce noise over-reaction

### Deployment

Deployed on Railway with 3 services: PostgreSQL, web service (FastAPI), and 2 cron jobs. See `railway.toml` and `Dockerfile`. The `cron_pipeline.py` patches `socket.getaddrinfo` at startup to force IPv4 due to Railway cron container IPv6 issues.
