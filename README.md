# Quant Agent Backend (V3.1 Chronos)

A quantitative trading backend that **pre-computes portfolio allocations** using LLM-powered research and serves them via a lightweight API gateway to QuantConnect.

**Core Philosophy**: Computation and delivery are fully separated. Heavy LLM inference runs on a schedule (Cron), while the API only queries the database — guaranteeing <10ms response times and zero timeout risk.

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Cron Pipeline   │────▶│   PostgreSQL     │◀────│  FastAPI Gateway │
│  (14:00 ET daily)│     │   (SSOT)         │     │  (24/7)          │
│                  │     │                  │     │                  │
│  Step 1: Macro   │     │  daily_decisions │     │  GET /allocation │
│  Step 2: Micro   │     │  - status        │     │  - is_stale flag │
│  Step 3: Risk    │     │  - checkpoints   │     │  - Bearer auth   │
│  Step 4: Format  │     │  - final_weights │     │                  │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                                         ▲
                                                         │
                                                  QuantConnect
```

## Project Structure

```
qc_fastapi/
├── cron_pipeline.py              # Cron Job entry — checkpoint-based daily pipeline
├── app/
│   ├── api/v1/
│   │   ├── endpoints/
│   │   │   ├── allocation.py     # GET /allocation (lightweight DB query)
│   │   │   ├── crew.py           # CrewAI endpoints (legacy)
│   │   │   ├── health.py         # Health checks
│   │   │   └── tasks.py          # Task management (legacy)
│   │   └── router.py
│   ├── core/
│   │   ├── security.py           # Bearer Token authentication
│   │   ├── cache.py              # TTL cache
│   │   ├── notifier.py           # Telegram alerts
│   │   └── tools.py              # Custom tools (legacy)
│   ├── db/
│   │   ├── database.py           # SQLAlchemy connection pool
│   │   └── models.py             # daily_decisions ORM (checkpoint state machine)
│   ├── models/
│   │   └── schemas.py            # Pydantic schemas (AllocationResponse, etc.)
│   ├── pipeline/
│   │   ├── prompts.py            # All LLM prompts in one place
│   │   ├── step1_macro.py        # Macro regime analysis
│   │   ├── step2_micro.py        # Sector ETF scoring
│   │   ├── step3_risk.py         # Risk audit & guardrails
│   │   └── step4_format.py       # Normalize to portfolio weights
│   ├── services/                 # CrewAI services (legacy)
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
# Edit .env: set OPENAI_API_KEY, API_TOKEN, DATABASE_URL
```

### 3. Start the API Gateway

```bash
python run.py
# API docs: http://localhost:8000/docs
```

### 4. Run the Cron Pipeline (locally)

```bash
# Run for today
python cron_pipeline.py

# Run for a specific date
python cron_pipeline.py 2026-03-14
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
| GET | `/api/v1/allocation/` | **Get portfolio weights** (core endpoint for QC) |
| POST | `/api/v1/crew/execute` | Execute CrewAI task (legacy) |
| GET | `/api/v1/crew/info` | Crew configuration info |

### Allocation Response Format

```json
{
    "date": "2026-03-14",
    "status": "READY",
    "is_stale": false,
    "weights": {
        "XLK": 0.35,
        "XLF": 0.25,
        "XLV": 0.15,
        "XLE": 0.10,
        "XLI": 0.08,
        "XLP": 0.04,
        "XLU": 0.03
    },
    "message": null
}
```

**`is_stale` graceful degradation**:
- `false` — Today's allocation is fresh and READY
- `true` — Fell back to the most recent valid allocation (non-trading day, pipeline error, etc.)

## Checkpoint State Machine

The pipeline uses a database-backed state machine for fault tolerance:

```
INIT → STEP1_DONE → STEP2_DONE → STEP3_DONE → READY
  ↓                                               
ERROR (resume from last checkpoint on retry)
```

If the pipeline crashes at Step 2, rerunning it will skip Step 1 (already saved) and resume from Step 2. No duplicate LLM calls, no wasted money.

## Railway Deployment

### Services Required

1. **PostgreSQL** — Add via Railway Dashboard → New → Database → PostgreSQL
2. **Web Service** — Your FastAPI gateway (this repo, auto-deploys from GitHub)
3. **Cron Job** — Runs `python cron_pipeline.py` daily at `0 18 * * 1-5` (14:00 ET = 18:00 UTC, weekdays only)

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | OpenAI API key |
| `API_TOKEN` | Yes (prod) | Bearer token for API auth |
| `DATABASE_URL` | Yes | PostgreSQL connection string (auto-provided by Railway) |
| `TG_BOT_TOKEN` | No | Telegram bot token for alerts |
| `TG_CHAT_ID` | No | Telegram chat ID for alerts |

## Tech Stack

- **FastAPI** — Lightweight API gateway
- **PostgreSQL** — Persistent checkpoint storage (SSOT)
- **SQLAlchemy** — ORM and connection management
- **OpenAI** — LLM-powered research pipeline
- **Pydantic** — Data validation and settings
- **Uvicorn** — ASGI server

## License

MIT License
