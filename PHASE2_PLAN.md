# Phase 2: Event Chain Modeling (因果链建模)
**Status:** Planning
**Timeline:** 2026-03-22 → TBD
**Objective:** Build macro → sector → ticker causal transmission model

---

## Background

Phase 1 successfully improved information density by leveraging Finnhub metadata (credibility, category, related tickers, recency) and QC quantitative indicators. However, the current system still has limitations:

**Current Limitations:**
1. **Flat event processing** - Each event evaluated independently, missing cascading effects
2. **No transmission logic** - Oil price spike → XLE gain is hardcoded in prompt, not learned
3. **Binary scoring** - Events either apply or don't, no partial transmission strength
4. **Limited sector interaction** - Can't model XLE gain → XLI gain (defense contractors benefit from war premium)

**Phase 1 Results (2026-03-20 test):**
- ✅ Key events improved: Added war context ("Iran war escalation")
- ✅ Credibility weighting working
- ⚠️ Final scores unchanged because macro signal was too strong (supply shock rule dominated)
- 📊 Phase 1 value shows in **weak signal scenarios** and **conflicting news**

**Phase 2 Goals:**
- Build event → sector transmission matrix
- Model secondary effects (e.g., oil war → energy WIN + industrials HURT)
- Quantify transmission strength (not just binary rules)
- Enable historical backtesting of transmission rules

---

## Core Concepts

### 1. Event Transmission Vector

Each macro event has a **transmission vector** mapping to all 11 sectors:

```python
event_vector = {
    "event_id": "oil_supply_shock_2026_03_20",
    "event_type": "supply_shock",
    "primary_keyword": "Strait of Hormuz closure",
    "confidence": 85,
    "transmission": {
        "XLE": {"strength": 0.95, "direction": "positive", "reasoning": "Oil producers benefit directly"},
        "XLB": {"strength": 0.60, "direction": "positive", "reasoning": "Commodity prices rise"},
        "XLI": {"strength": 0.70, "direction": "positive", "reasoning": "Defense contractors win"},
        "XLY": {"strength": -0.75, "direction": "negative", "reasoning": "Consumer demand destruction"},
        "XLK": {"strength": -0.50, "direction": "negative", "reasoning": "Growth tech hurt by inflation"},
        "XLF": {"strength": -0.30, "direction": "negative", "reasoning": "Credit stress from oil shock"},
        "XLP": {"strength": 0.10, "direction": "neutral", "reasoning": "Defensives mildly benefit"},
        "XLV": {"strength": 0.15, "direction": "neutral", "reasoning": "Healthcare less affected"},
        "XLU": {"strength": -0.20, "direction": "negative", "reasoning": "Utilities hurt by input costs"},
        "XLC": {"strength": -0.40, "direction": "negative", "reasoning": "Ad spending declines"},
        "XLRE": {"strength": -0.60, "direction": "negative", "reasoning": "Real estate hurt by inflation"},
    }
}
```

**Strength Scale:**
- `1.0` = Full direct beneficiary (oil spike → XLE)
- `0.5-0.8` = Strong secondary effect
- `0.2-0.4` = Weak indirect effect
- `0.0-0.1` = Minimal/neutral impact
- `-0.2 to -1.0` = Negative impact (losers)

### 2. Transmission Matrix Database

Store historical event vectors in a new table:

```sql
CREATE TABLE event_transmission (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    event_id VARCHAR(100) UNIQUE NOT NULL,
    event_type VARCHAR(50),  -- supply_shock, demand_shock, rate_shock, geopolitical, etc.
    event_description TEXT,
    confidence INTEGER,      -- 0-100
    transmission_vector JSONB,  -- sector scores
    created_at TIMESTAMP DEFAULT NOW(),
    validated BOOLEAN DEFAULT FALSE,  -- backtest validation flag
    accuracy_score FLOAT     -- post-hoc validation (0.0-1.0)
);
```

### 3. Event Types & Canonical Transmission Rules

Define canonical transmission patterns for common event types:

| Event Type | Primary Beneficiaries | Primary Victims | Secondary Effects |
|---|---|---|---|
| **Supply Shock (Oil)** | XLE (0.95), XLB (0.6), XLI (0.7) | XLY (-0.75), XLK (-0.5), XLRE (-0.6) | Consumer demand destruction |
| **War/Geopolitical** | XLI (0.9), XLE (0.8) | XLY (-0.7), XLF (-0.5) | Flight to safety |
| **Rate Shock (Hawkish)** | XLF (0.7), Financials WIN | XLK (-0.8), XLRE (-0.9), XLU (-0.6) | Long-duration assets crash |
| **Risk-Off/Credit Stress** | XLV (0.85), XLP (0.8), XLU (0.7) | XLY (-0.85), XLK (-0.7), XLF (-0.7) | Defensive rotation |
| **Recession/Demand Collapse** | XLV (0.75), XLP (0.7), XLU (0.6) | XLY (-0.8), XLI (-0.6), XLE (-0.6) | Demand > Supply |
| **Fed Dovish/Easing** | XLRE (0.8), XLK (0.7), XLU (0.7) | XLE (-0.3), Commodities LOSE | Duration assets rally |

**Usage:** When Step 1 detects an event, lookup canonical transmission vector, then adjust based on:
- Event confidence (multiply strength by confidence/100)
- Ticker-level news (Phase 1 credibility-weighted signals)
- QC quantitative indicators (cross-validation)

---

## Implementation Plan

### Step 1: Database Schema (1 day)

**New Table:** `event_transmission`

**Migration Script:** `migrate_phase2.py`

```python
"""
Phase 2 Database Migration — Event Transmission Table
"""
from sqlalchemy import Column, Integer, String, Text, Date, Boolean, Float, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB
from app.db.database import Base, engine, SessionLocal

# Add to app/db/models.py
class EventTransmission(Base):
    __tablename__ = "event_transmission"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False, index=True)
    event_id = Column(String(100), unique=True, nullable=False, index=True)
    event_type = Column(String(50), index=True)
    event_description = Column(Text)
    confidence = Column(Integer)  # 0-100
    transmission_vector = Column(JSONB)
    created_at = Column(TIMESTAMP, server_default="NOW()")
    validated = Column(Boolean, default=False)
    accuracy_score = Column(Float)  # post-hoc validation
```

### Step 2: Canonical Transmission Rules (1 day)

**New File:** `app/pipeline/transmission_rules.py`

Define canonical patterns as Python dicts:

```python
CANONICAL_TRANSMISSIONS = {
    "supply_shock_oil": {
        "keywords": ["oil spike", "Hormuz", "OPEC cut", "embargo", "supply disruption"],
        "vector": {
            "XLE": 0.95, "XLB": 0.60, "XLI": 0.70,
            "XLY": -0.75, "XLK": -0.50, "XLRE": -0.60,
            "XLF": -0.30, "XLU": -0.20, "XLC": -0.40,
            "XLP": 0.10, "XLV": 0.15,
        }
    },
    "war_geopolitical": {
        "keywords": ["war", "invasion", "attack", "missile", "bombing"],
        "vector": {
            "XLI": 0.90, "XLE": 0.80, "XLB": 0.50,
            "XLY": -0.70, "XLF": -0.50, "XLK": -0.45,
            "XLV": 0.30, "XLP": 0.25, "XLU": 0.20,
            "XLRE": -0.40, "XLC": -0.35,
        }
    },
    # ... more patterns
}

def match_event_to_pattern(key_events: List[str], reasoning: str) -> dict:
    """Match Step 1 output to canonical transmission patterns."""
    combined = " ".join(key_events).lower() + " " + reasoning.lower()

    matched = []
    for pattern_name, pattern_def in CANONICAL_TRANSMISSIONS.items():
        score = sum(1 for kw in pattern_def["keywords"] if kw in combined)
        if score >= 2:  # At least 2 keywords match
            matched.append((pattern_name, score, pattern_def["vector"]))

    if not matched:
        return {}  # No match, fall back to ticker-level signals

    # Use highest scoring pattern
    matched.sort(key=lambda x: x[1], reverse=True)
    return matched[0][2]
```

### Step 3: Enhance Step 1 Output (1 day)

**Update:** `app/pipeline/step1_macro.py`

Add `transmission_vector` field to `Step1Output`:

```python
class Step1Output(BaseModel):
    regime: str
    confidence: int
    summary: str
    key_events: List[str]
    reasoning: str
    transmission_vector: Optional[Dict[str, float]] = None  # NEW FIELD

# After LLM call:
step1_result = await run_macro_analysis(...)
transmission = match_event_to_pattern(
    step1_result.key_events,
    step1_result.reasoning
)
step1_result.transmission_vector = transmission

# Store in event_transmission table
event_id = f"macro_{target_date.isoformat()}"
db.add(EventTransmission(
    date=target_date,
    event_id=event_id,
    event_type=detect_event_type(step1_result.key_events),
    event_description=step1_result.summary,
    confidence=step1_result.confidence,
    transmission_vector=transmission,
))
```

### Step 4: Integrate Transmission into Step 2 (2 days)

**Update:** `app/pipeline/step2_micro.py`

Modify `run_micro_scoring()` to accept transmission vector:

```python
async def run_micro_scoring(
    target_date: date,
    macro_context_str: str,
    transmission_vector: Dict[str, float],  # NEW PARAMETER
    holdings: Optional[List[str]] = None,
    news_digest: str = "",
    sector_context: str = "",
    earnings_flags: dict = {},
    hard_flags: Dict[str, List[str]] = {},
) -> str:
    """Step 2 with event transmission priors."""

    # Build transmission context
    if transmission_vector:
        trans_lines = []
        for sector, strength in sorted(transmission_vector.items(), key=lambda x: -abs(x[1])):
            if abs(strength) > 0.3:  # Only show significant impacts
                direction = "LONG" if strength > 0 else "SHORT"
                trans_lines.append(f"  {sector}: {direction} {abs(strength):.2f}")

        transmission_context = (
            "## MACRO EVENT TRANSMISSION (Phase 2 Prior)\n"
            "The following sector biases are derived from macro event analysis:\n"
            + "\n".join(trans_lines) + "\n\n"
            "INSTRUCTION: Use these as STARTING POINTS, then refine with ticker-level news.\n"
            "If ticker news strongly contradicts transmission, ticker wins (Phase 1 credibility rule).\n\n"
        )
    else:
        transmission_context = ""

    # Update prompt
    user_prompt = transmission_context + MICRO_USER.format(...)

    # Call LLM
    response = await client.beta.chat.completions.parse(...)
```

**Update:** `cron_pipeline.py` Step 2 section

```python
# Step 2
if row.status == "STEP1_DONE":
    # Load transmission vector
    transmission = {}
    if macro_parsed.get("transmission_vector"):
        transmission = macro_parsed["transmission_vector"]

    result = await run_micro_scoring(
        target_date,
        macro_context_str,
        transmission_vector=transmission,  # NEW
        holdings=tickers,
        news_digest=news_digest_str,
        sector_context=sector_context_str,
        earnings_flags=earnings_flags,
        hard_flags=hard_flags,
    )
```

### Step 5: Backtesting & Validation (3 days)

**New File:** `backtest_transmission.py`

```python
"""
Phase 2 Backtesting — Validate Transmission Rules

For each historical decision:
1. Load event_transmission record
2. Compare predicted sector performance (transmission_vector) vs actual SPY sector returns
3. Compute accuracy: correlation between predicted strength and actual 1-day/5-day returns
4. Update accuracy_score in event_transmission table
"""
import pandas as pd
from datetime import date, timedelta
from app.db.database import SessionLocal
from app.db.models import EventTransmission, DecisionLog

def fetch_spy_sector_returns(date: date, days: int = 5) -> dict:
    """Fetch actual sector ETF returns from start_date to start_date + days.

    TODO: Integrate with market data API or manual CSV.
    """
    # Placeholder
    return {
        "XLE": 0.12, "XLI": 0.08, "XLV": 0.03,
        "XLK": -0.05, "XLY": -0.08, "XLRE": -0.10,
        # ...
    }

def validate_transmission(event: EventTransmission, actual_returns: dict) -> float:
    """Compute correlation between predicted transmission and actual returns."""
    predicted = event.transmission_vector or {}

    common_sectors = set(predicted.keys()) & set(actual_returns.keys())
    if not common_sectors:
        return 0.0

    pred_vals = [predicted[s] for s in common_sectors]
    actual_vals = [actual_returns[s] for s in common_sectors]

    # Pearson correlation
    corr = pd.Series(pred_vals).corr(pd.Series(actual_vals))
    return corr if not pd.isna(corr) else 0.0

def run_backtest():
    db = SessionLocal()
    events = db.query(EventTransmission).filter(EventTransmission.validated == False).all()

    for event in events:
        actual = fetch_spy_sector_returns(event.date, days=5)
        accuracy = validate_transmission(event, actual)

        event.accuracy_score = accuracy
        event.validated = True
        print(f"[{event.date}] {event.event_id}: accuracy={accuracy:.3f}")

    db.commit()
    db.close()

if __name__ == "__main__":
    run_backtest()
```

---

## Testing Strategy

### Unit Tests

```python
# tests/test_phase2.py
def test_match_event_to_pattern():
    key_events = ["Strait of Hormuz closure", "Oil supply disruption"]
    reasoning = "Iran threatens to block oil shipments..."

    transmission = match_event_to_pattern(key_events, reasoning)

    assert transmission["XLE"] > 0.8  # Energy wins
    assert transmission["XLY"] < -0.5  # Consumers lose
    assert transmission["XLI"] > 0.5   # Defense contractors win

def test_transmission_integration():
    # Mock Step 1 output with transmission vector
    step1 = {
        "regime": "Risk-Off",
        "confidence": 85,
        "transmission_vector": {"XLE": 0.95, "XLY": -0.75}
    }

    # Run Step 2
    result = await run_micro_scoring(
        date.today(),
        "macro context",
        transmission_vector=step1["transmission_vector"],
        holdings=["AAPL", "XOM"],
        news_digest="...",
    )

    scores = json.loads(result)
    assert scores["XLE"] > 7  # Should follow transmission
    assert scores["XLY"] < 4  # Should follow transmission
```

### Integration Test

**Test Scenario:** Re-run 2026-03-20 pipeline with Phase 2

1. Delete existing decision: `DELETE FROM daily_decisions WHERE date='2026-03-20'`
2. Delete event transmission: `DELETE FROM event_transmission WHERE date='2026-03-20'`
3. Run: `python cron_pipeline.py 2026-03-20`
4. Compare:
   - Before (Phase 1 only): Final scores from Git commit 08f4f27
   - After (Phase 2): Final scores with transmission vector applied

**Expected Improvement:**
- More explainable sector allocation (can trace to macro event)
- Smoother score transitions (transmission provides continuity)
- Better alignment between AI regime and QC regime (fewer false overrides)

---

## Success Metrics

1. **Transmission Accuracy (Backtest):**
   - Target: Correlation > 0.5 between predicted transmission and actual sector returns (5-day)
   - Baseline: Random guess ≈ 0.0

2. **Regime Accuracy:**
   - Target: +15-20% vs Phase 1 (measured on weak signal days)
   - Method: Compare DecisionLog.decision_correct before/after Phase 2

3. **Score Stability:**
   - Target: Reduce day-to-day sector weight volatility by 20%
   - Method: Measure std dev of sector scores across rolling 10-day windows

4. **Explainability:**
   - Every sector score should trace to either:
     - Macro transmission (>60% influence)
     - Ticker-level news (>30% influence)
     - Earnings flag (<10% influence)

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Transmission rules too rigid | Over-fitting to specific event types | Use confidence-weighted blending; allow ticker news to override |
| Insufficient historical data | Can't validate accuracy | Start collecting now; backfill using archived decision logs |
| LLM prompt becomes too complex | Worse performance, higher cost | Keep transmission as separate prior, not inline rules |
| Database query overhead | Slower pipeline | Index event_transmission.date; cache canonical patterns |

---

## Rollout Plan

1. **Week 1 (2026-03-22 → 03-28):**
   - Implement database schema + migration
   - Build transmission_rules.py with 6 canonical patterns
   - Unit tests

2. **Week 2 (2026-03-29 → 04-04):**
   - Integrate into Step 1 + Step 2
   - Test on 2026-03-20 historical data
   - Compare Phase 1 vs Phase 2 outputs

3. **Week 3 (2026-04-05 → 04-11):**
   - Deploy to Railway (shadow mode: log transmission but don't use)
   - Collect 1 week of transmission data
   - Build backtest script

4. **Week 4 (2026-04-12 → 04-18):**
   - Run backtesting on collected data
   - Tune transmission strengths based on accuracy_score
   - Switch to production (transmission actively used in scoring)

---

## Open Questions

1. **Should transmission be time-decayed?**
   - E.g., oil shock impact on XLE is 0.95 on day 0, decays to 0.70 by day 5
   - Decision: Start with static, add decay in Phase 3 if needed

2. **How to handle conflicting events?**
   - E.g., oil shock (XLE +0.95) + recession (XLE -0.60) on same day
   - Decision: Sum transmission vectors, clip to [-1.0, 1.0]

3. **Should we store transmission history in DailyDecision?**
   - Pros: Easier debugging
   - Cons: JSON field bloat
   - Decision: Yes, add `transmission_applied` JSONB field to DailyDecision

4. **Integration with Phase 1 credibility weighting?**
   - Decision: Transmission is macro-level prior; credibility is ticker-level signal
   - Both can coexist: transmission sets sector baseline, credibility refines within sector

---

## Dependencies

- Phase 1 (complete) ✅
- SQLAlchemy ORM models ✅
- OpenAI Structured Outputs ✅
- PostgreSQL JSONB support ✅

---

## Next Steps

1. Review this plan with user
2. Create database migration script
3. Implement transmission_rules.py
4. Begin Step 1 integration

Ready to proceed?
