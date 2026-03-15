# Quant Agent Backend (V3.1 Chronos)

A quantitative trading backend that **pre-computes portfolio allocations** using LLM-powered research grounded in real market data, and serves them via a lightweight API gateway to QuantConnect.

**Core Philosophy**: AI does subtraction, not addition — high-confidence event filtering and risk-off detection, not price prediction. Computation and delivery are fully separated.

## Architecture

```
 10:00 ET          13:30 ET              14:00 ET              15:45 ET
    │                  │                     │                     │
    ▼                  ▼                     ▼                     ▼
┌────────┐    ┌──────────────┐    ┌──────────────────┐    ┌──────────────┐
│  QC    │    │  Pre-Fetch   │    │  Cron Pipeline   │    │ FastAPI GW   │
│ POST   │    │  Pipeline    │    │                  │    │ (24/7 <10ms) │
│holdings│    │              │    │ Step 1: Macro    │    │              │
│+regime │    │ Finnhub news │    │  news+calendar   │    │ GET /alloc   │
│+cands  │    │ for 15-20    │    │  +history        │    │  weights     │
└────┬───┘    │ tickers      │    │ Step 2: Micro    │    │  defense     │
     │        │              │    │  read DB library │    │  risk_flags  │
     │        │ LLM batch    │    │ Step 3: Risk     │    │  regime      │
     │        │ summarize    │    │ Step 4: Weights  │    │              │
     │        │              │    │ Regime Override   │    │ GET /decide  │
     │        └──────┬───────┘    └────────┬─────────┘    └──────┬───────┘
     │               │                     │                     │
     ▼               ▼                     ▼                     ▲
   ┌───────────────────────────────────────────────────────────────┐
   │                       PostgreSQL                              │
   │  daily_holdings        │  ticker_news_library  (pre-fetched)  │
   │  daily_decisions       │  daily_news_digest                   │
   │  decision_log          │                                      │
   └───────────────────────────────────────────────────────────────┘
```

## Three-Layer Value Framework

| Layer | Function | Confidence | Usage |
|-------|----------|------------|-------|
| **Hard Rules** | Earnings/FDA/halt/merger detection | High | Auto-exclude from new buys |
| **Regime Override** | AI downgrades QC regime (gated) | Medium | Only Risk-Off, confidence>=80, >=2 events |
| **ETF Scoring** | Sector allocation weights | Low | Reference only during observation period |

**Key Principle**: AI can only downgrade positions (subtract risk), never upgrade them.

## Project Structure

```
qc_fastapi/
├── cron_pipeline.py              # Cron 1 (14:00 ET) — checkpoint pipeline + regime override
├── pre_fetch_pipeline.py         # Cron 2 (13:30 ET) — news fetch + LLM batch summarize
├── app/
│   ├── api/v1/
│   │   ├── endpoints/
│   │   │   ├── allocation.py     # GET  — weights + defense_level + risk_flags
│   │   │   ├── holdings.py       # POST — QC 10:00 ET position snapshot
│   │   │   ├── decisions.py      # GET/PATCH — decision log review + backfill
│   │   │   ├── health.py         # Health checks
│   │   │   ├── crew.py           # (legacy, scheduled for removal)
│   │   │   └── tasks.py          # (legacy, scheduled for removal)
│   │   └── router.py
│   ├── core/
│   │   ├── security.py           # Bearer Token authentication
│   │   ├── cache.py              # TTL cache
│   │   └── notifier.py           # Telegram alerts
│   ├── db/
│   │   ├── database.py           # SQLAlchemy lazy-init connection pool
│   │   └── models.py             # 4 tables: decisions, holdings, digest, log
│   ├── models/
│   │   └── schemas.py            # Pydantic schemas
│   ├── pipeline/
│   │   ├── data_fetcher.py       # Finnhub API: news, calendar, earnings, hard risks
│   │   ├── prompts.py            # All LLM prompts (structured JSON output)
│   │   ├── step1_macro.py        # Macro regime → structured {regime, confidence, ...}
│   │   ├── step2_micro.py        # Sector ETF scoring with news + earnings context
│   │   ├── step3_risk.py         # Risk audit & guardrails
│   │   └── step4_format.py       # Normalize scores → portfolio weights
│   ├── config.py                 # Pydantic settings
│   └── main.py                   # FastAPI app entry
├── tests/
├── Dockerfile
├── railway.toml
└── requirements.txt
```

## Quick Start

### 1. Install Dependencies

```bash
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp env_example.txt .env
# Edit .env: set OPENAI_API_KEY, API_TOKEN, DATABASE_URL, FINNHUB_API_KEY
```

### 3. Start the API Gateway

```bash
python run.py
# API docs: http://localhost:8000/docs
```

### 4. Run the Cron Pipeline

```bash
python cron_pipeline.py              # run for today
python cron_pipeline.py 2026-03-14   # run for a specific date
```

## API Endpoints

### Public

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/api/v1/health/ready` | Readiness check |

### Authenticated (Bearer Token)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/allocation/` | Portfolio weights + defense_level + risk_flags |
| POST | `/api/v1/holdings/` | Submit QC 10:00 ET holdings snapshot |
| GET | `/api/v1/holdings/` | View today's holdings |
| GET | `/api/v1/decisions/` | List recent decision logs |
| GET | `/api/v1/decisions/{date}` | Single day decision detail |
| PATCH | `/api/v1/decisions/{date}` | Backfill market_outcome + correctness |

### Allocation Response

```json
{
    "date": "2026-03-14",
    "status": "READY",
    "is_stale": false,
    "weights": {
        "XLK": 0.14, "XLF": 0.12, "XLV": 0.10,
        "XLE": 0.08, "XLI": 0.10, "XLP": 0.06,
        "XLU": 0.04, "XLY": 0.12, "XLC": 0.10,
        "XLRE": 0.06, "XLB": 0.08
    },
    "defense_level": "light",
    "risk_flags": {"NVDA": ["earnings_soon"]},
    "regime": "Neutral",
    "message": null
}
```

**Fields for QC consumption**:
- `weights` — ETF allocation targets (sum = 1.0)
- `defense_level` — Position sizing: `full` / `light` / `half`
- `risk_flags` — Per-ticker hard events: `earnings_soon`, `fda_pending`, `trading_halted`, `acquisition_target`, `major_lawsuit`
- `regime` — AI macro regime call: `Risk-On` / `Neutral` / `Risk-Off`
- `is_stale` — `true` = using fallback data from a previous day

## Pipeline Data Flow

```
Finnhub API
  ├── fetch_macro_news()         ─┐
  ├── fetch_economic_calendar()   ├──▶ Step 1: Macro Analysis → structured JSON
  └── 5-day history_block        ─┘      ↓ writes DailyNewsDigest
                                         ↓
  ├── fetch_all_holdings_news()  ─┐
  ├── fetch_earnings_flag()       ├──▶ Step 2: Micro Scoring → ETF scores
  └── scan_all_holdings_risks()  ─┘      ↓ updates ticker_risks
                                         ↓
                                    Step 3: Risk Audit → adjusted scores
                                         ↓
                                    Step 4: Normalize → weights (sum=1.0)
                                         ↓
                                    Gated Regime Override
                                      ├── confidence >= 80?
                                      ├── >= 2 key events?
                                      ├── AI says Risk-Off?
                                      └── YES to all → override QC regime
                                         ↓
                                    Write DecisionLog (audit trail)
```

## Gated Regime Override

AI can only **downgrade** positions, never upgrade. Override requires ALL conditions:

1. AI confidence >= 80
2. AI regime differs from QC regime
3. At least 2 key events as evidence
4. AI regime is `Risk-Off` (downgrade only)

If any condition fails → keep QC's regime, log the rejection reason.

## Checkpoint State Machine

```
INIT → STEP1_DONE → STEP2_DONE → STEP3_DONE → READY
  ↓
ERROR (resume from last checkpoint on retry)
```

Crash at Step 2? Rerun skips Step 1 (already saved) and resumes from Step 2. No duplicate LLM calls.

## Database Tables

| Table | Purpose |
|-------|---------|
| `daily_decisions` | Pipeline checkpoint state machine + final weights |
| `daily_holdings` | QC position snapshot (tickers + top_candidates + payload) |
| `daily_news_digest` | Macro summary, regime, key events, ticker risks |
| `decision_log` | Full audit: QC vs AI regime, override, defense, backfill fields |
| `ticker_news_library` | Pre-fetched news with LLM summaries, sentiment, hard event flags |

## Railway Deployment

### Services Required

1. **PostgreSQL** — Add via Railway Dashboard
2. **Web Service** — FastAPI gateway (auto-deploys from GitHub)
3. **Cron Job 1** — Pre-fetch: `python pre_fetch_pipeline.py` on weekdays:
   - EDT (Mar–Nov): `30 17 * * 1-5` (UTC 17:30 = ET 13:30)
   - EST (Nov–Mar): `30 18 * * 1-5` (UTC 18:30 = ET 13:30)
4. **Cron Job 2** — Main pipeline: `python cron_pipeline.py` on weekdays:
   - EDT (Mar–Nov): `0 18 * * 1-5` (UTC 18:00 = ET 14:00)
   - EST (Nov–Mar): `0 19 * * 1-5` (UTC 19:00 = ET 14:00)

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | OpenAI API key |
| `API_TOKEN` | Yes (prod) | Bearer token for API auth |
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `FINNHUB_API_KEY` | Yes | Finnhub market data API key |
| `TG_BOT_TOKEN` | No | Telegram bot token for alerts |
| `TG_CHAT_ID` | No | Telegram chat ID for alerts |

## QuantConnect Integration

### 1. Submit Holdings + Candidates (13:30 ET)

After momentum scoring completes, POST current holdings and top candidates:

```python
# QuantConnect — Scheduled Event at 13:30 ET
import requests

url = "https://your-app.up.railway.app/api/v1/holdings/"
headers = {"Authorization": "Bearer YOUR_TOKEN"}
payload = {
    "current_holdings": [s.Value for s in self.Portfolio.Keys if self.Portfolio[s].Invested],
    "top_candidates": self.get_momentum_top(15),  # top 15 momentum symbols
    "qc_regime": self.regime,        # "bull" / "chop" / "bear"
    "account_dd": self.Portfolio.TotalUnrealizedProfit / self.Portfolio.TotalPortfolioValue
}
requests.post(url, json=payload, headers=headers, timeout=5)
```

### 2. Fetch Allocation (15:45 ET)

In `BeforeMarketClose` - 15 minutes, GET the AI allocation:

```python
# QuantConnect — Scheduled Event at 15:45 ET
resp = requests.get(
    "https://your-app.up.railway.app/api/v1/allocation/",
    headers={"Authorization": "Bearer YOUR_TOKEN"},
    timeout=5
).json()

# Decision logic
if resp["is_stale"]:
    return  # stale data → hold current positions, don't rebalance

# Apply defense_level to position sizing
MAX_EXPOSURE = {"full": 1.0, "light": 0.7, "half": 0.5}
scale = MAX_EXPOSURE.get(resp["defense_level"], 1.0)

# Apply risk_flags — exclude flagged tickers from new buys
blocked = set(resp.get("risk_flags", {}).keys())

# Apply weights (during observation period: log only, don't execute)
for etf, weight in resp["weights"].items():
    target = weight * scale
    self.SetHoldings(etf, target)
```

### 3. Observation Period (First 30 Days)

During the initial period, log AI decisions but don't let them affect real positions:

```python
# Log only — compare AI vs actual performance
self.Log(f"AI regime={resp['regime']} defense={resp['defense_level']} "
         f"flags={resp.get('risk_flags', {})} weights={resp['weights']}")
```

After 30 days, analyze `decision_log` via the `/decisions/` endpoint to determine which AI signals are reliable enough to act on.

## Validation Workflow (Post-30 Days)

```sql
-- AI accuracy when calling Risk-Off
SELECT date, ai_regime, confidence, market_outcome, decision_correct
FROM decision_log
WHERE ai_regime = 'Risk-Off'
ORDER BY date DESC;

-- Override frequency and accuracy
SELECT date, qc_regime, ai_regime, regime_override, decision_correct
FROM decision_log
WHERE regime_override = true
ORDER BY date DESC;
```

## Tech Stack

- **FastAPI** — API gateway (<10ms response)
- **PostgreSQL** — Persistent state (5 tables)
- **SQLAlchemy** — ORM with lazy initialization
- **OpenAI** — LLM pipeline (gpt-4o-mini)
- **Finnhub** — Real-time news, economic calendar, earnings
- **Pydantic** — Validation and settings management
- **Uvicorn** — ASGI server

## License

MIT License
