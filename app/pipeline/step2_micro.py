"""
Step 2 — Micro Sector Scoring (with Holdings + Dual-Layer News + Earnings)

Takes the macro thesis from Step 1, current holdings from QC,
pre-fetched dual-layer news (ticker + sector), and earnings
flags to produce grounded ETF scores.

Changes vs previous version:
  - MICRO_SYSTEM / MICRO_USER replaced with inline STEP2_SYSTEM
    (richer macro transmission rules, applied_macro_rule CoT field)
  - SectorScores Pydantic model + Structured Outputs (guaranteed JSON)
  - _validate_scores() program-level safety net (hard floors/ceilings)
  - temperature lowered to 0.0 for deterministic rule-following
  - DB builder functions preserved exactly as-is
"""

import json
import logging
import re
import asyncio
from datetime import date, timedelta
from typing import Dict, List, Optional

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.constants import ETF_TOP5

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════
# Pydantic output schema
# ═══════════════════════════════════════════════════════════════

class SectorScores(BaseModel):
    XLK:  int = Field(ge=1, le=10, description="Technology")
    XLF:  int = Field(ge=1, le=10, description="Financials")
    XLV:  int = Field(ge=1, le=10, description="Healthcare")
    XLE:  int = Field(ge=1, le=10, description="Energy")
    XLI:  int = Field(ge=1, le=10, description="Industrials / Defense")
    XLP:  int = Field(ge=1, le=10, description="Consumer Staples")
    XLU:  int = Field(ge=1, le=10, description="Utilities")
    XLY:  int = Field(ge=1, le=10, description="Consumer Discretionary")
    XLC:  int = Field(ge=1, le=10, description="Communication Services")
    XLRE: int = Field(ge=1, le=10, description="Real Estate")
    XLB:  int = Field(ge=1, le=10, description="Materials")

    # CoT anchor — forces the model to name the rule BEFORE committing scores.
    # Dramatically improves floor/ceiling compliance.
    applied_macro_rule: str = Field(
        description=(
            "Which macro transmission rule was triggered? "
            "Must be one of: 'Supply Shock', 'Rate Hike', 'Recession', "
            "'Risk-On', 'None'. Write this BEFORE you assign any scores."
        )
    )
    reasoning: str = Field(
        description=(
            "Per-sector brief rationale explaining how the macro "
            "floor/ceiling was combined with micro news for each ETF."
        )
    )


# ═══════════════════════════════════════════════════════════════
# System prompt
# ═══════════════════════════════════════════════════════════════

STEP2_SYSTEM = """
You are a quantitative portfolio strategist supporting an automated US equity
momentum strategy running on QuantConnect. Your job is to score 11 S&P sector
ETFs (1-10) to guide daily sector rotation.

STRATEGY CONTEXT
----------------
- Momentum strategy; holdings are selected from S&P 500 top-momentum stocks.
- Strategy rebalances daily based on your sector scores.
- Higher score = increase allocation. Lower score = reduce allocation.

SECTOR ETF UNIVERSE
-------------------
XLK  = Technology          XLF  = Financials       XLV  = Healthcare
XLE  = Energy              XLI  = Industrials       XLP  = Consumer Staples
XLU  = Utilities           XLY  = Consumer Discret  XLC  = Communication
XLRE = Real Estate         XLB  = Materials

=================================================================
MACRO TRANSMISSION RULES -- APPLY THESE FIRST, BEFORE MICRO NEWS
=================================================================

STEP 1 (MANDATORY): Identify which rule applies from KEY EVENTS.
Write the rule name in `applied_macro_rule` BEFORE assigning any scores.

RULE: Supply Shock
  Trigger: war / invasion / oil embargo / Iran / Hormuz /
           OPEC cut / energy crisis / geopolitical conflict

  FLOORS (score must be AT LEAST this value):
    XLE  >= 8   (supply shock = direct price beneficiary)
    XLI  >= 7   (defense + industrial spending surge)
    XLP  >= 7   (staples = inflation & crisis haven)
    XLU  >= 7   (utilities = defensive haven)
    XLV  >= 6   (healthcare is non-cyclical)

  CEILINGS (score must be AT MOST this value):
    XLK  <= 4   (growth/tech punished in risk-off)
    XLC  <= 4   (communication/growth punished)
    XLY  <= 3   (discretionary hit hard by inflation)
    XLRE <= 3   (rate-sensitive, hurt by inflation expectation)

RULE: Rate Hike / Hawkish Fed
  Trigger: rate hike / Fed hawkish / inflation shock / CPI beat

  FLOORS: XLF >= 7,  XLE >= 6,  XLP >= 6
  CEILINGS: XLRE <= 3,  XLK <= 4,  XLY <= 4,  XLC <= 5

RULE: Recession / Demand Collapse
  Trigger: recession / GDP contraction / demand collapse /
           credit crisis / unemployment spike

  FLOORS: XLP >= 8,  XLU >= 8,  XLV >= 8
  CEILINGS: XLE <= 4,  XLY <= 3,  XLB <= 3,  XLF <= 4

RULE: Risk-On / Bull Market
  Trigger: strong GDP / broad earnings beats / Fed pivot /
           VIX collapse / credit spreads tightening

  FLOORS: XLK >= 7,  XLY >= 7,  XLC >= 6
  CEILINGS: XLP <= 5,  XLU <= 5,  XLV <= 6

If no rule applies: set applied_macro_rule = "None" and score freely.

STEP 2: Micro adjustment
After applying macro floors/ceilings, you may adjust by +/-2 based on
sector-specific news. You CANNOT violate a macro floor or ceiling by
more than 1 point.

NEWS CREDIBILITY WEIGHTING (Phase 1):
- [credible:85+] = Tier-1 source (Bloomberg, Reuters, WSJ) — **trust fully**, prioritize
- [low-cred:<40] = Press release / unknown source — treat as **noise** unless confirmed
- [breaking] = News within last 6 hours — immediate impact, high weight
- [category] = Event type (e.g., 'earnings', 'FDA', 'merger') — context for assessment
- **Bold text** = High-credibility news — your primary signals
- 🔗 CONTAGION RISK = Related tickers affected by hard events — expand impact assessment
- When news conflicts: HIGH-CREDIBILITY SOURCE ALWAYS WINS over low-credibility speculation

STEP 3: Hard event penalty
If a holding ticker has a HARD EVENT flag (marked with red circles),
its primary sector ceiling = 4.

STEP 4: Final self-check before output
- applied_macro_rule is written
- No growth sector (XLK/XLC/XLY) scores > 5 when regime is Risk-Off
- No defensive sector (XLP/XLU/XLV) scores < 5 when regime is Risk-Off

OUTPUT: Return ONLY the SectorScores JSON. No markdown outside JSON fields.
"""


# ═══════════════════════════════════════════════════════════════
# Program-level score validator  (Layer 3 safety net)
# ═══════════════════════════════════════════════════════════════

_SUPPLY_SHOCK_KW = [
    "war", "invasion", "attack", "missile", "bombing", "military",
    "oil", "crude", "embargo", "sanctions", "supply disruption",
    "iran", "ukraine", "russia", "israel", "hamas", "strait", "hormuz",
    "opec", "energy crisis",
]
_RATE_HIKE_KW = [
    "rate hike", "rate increase", "hawkish", "fed tightening",
    "inflation shock", "cpi beat", "yields surge",
]
_RECESSION_KW = [
    "recession", "gdp contraction", "demand collapse",
    "credit crisis", "unemployment spike", "layoffs surge",
]


def _validate_scores(
    scores: Dict[str, int],
    key_events: List[str],
    reasoning: str = "",
    applied_rule: str = "None",
) -> tuple[Dict[str, int], List[str]]:
    """
    Hard-override scores that violate macro rules.

    Validator floors/ceilings are 1 point looser than prompt rules to
    preserve micro-adjustment room while blocking extreme drift.
    Returns (corrected_scores, list_of_override_messages).
    """
    combined = (
        " ".join(str(e) for e in key_events)
        + " " + reasoning
        + " " + applied_rule
    ).lower()

    overrides: List[str] = []

    def _floor(etf: str, floor: int, rule: str) -> None:
        if scores.get(etf, 5) < floor:
            overrides.append(
                f"VALIDATOR: {etf} {scores[etf]}→{floor} (floor, {rule})"
            )
            scores[etf] = floor

    def _ceil(etf: str, ceiling: int, rule: str) -> None:
        if scores.get(etf, 5) > ceiling:
            overrides.append(
                f"VALIDATOR: {etf} {scores[etf]}→{ceiling} (ceiling, {rule})"
            )
            scores[etf] = ceiling

    is_supply_shock = any(kw in combined for kw in _SUPPLY_SHOCK_KW)
    is_rate_hike    = any(kw in combined for kw in _RATE_HIKE_KW)
    is_recession    = any(kw in combined for kw in _RECESSION_KW)

    if is_supply_shock:
        _floor("XLE",  7, "supply_shock")
        _floor("XLI",  6, "supply_shock")
        _floor("XLP",  6, "supply_shock")
        _floor("XLU",  6, "supply_shock")
        _ceil ("XLK",  5, "supply_shock")
        _ceil ("XLC",  5, "supply_shock")
        _ceil ("XLY",  4, "supply_shock")
        _ceil ("XLRE", 4, "supply_shock")

    if is_rate_hike:
        _floor("XLF",  6, "rate_hike")
        _ceil ("XLRE", 4, "rate_hike")
        _ceil ("XLK",  5, "rate_hike")

    if is_recession:
        _floor("XLP",  7, "recession")
        _floor("XLU",  7, "recession")
        _floor("XLV",  7, "recession")
        _ceil ("XLE",  5, "recession")
        _ceil ("XLY",  4, "recession")
        _ceil ("XLB",  4, "recession")

    return scores, overrides


# ═══════════════════════════════════════════════════════════════
# DB context builders  (preserved from original)
# ═══════════════════════════════════════════════════════════════

def build_news_context_from_db(
    db: Session, tickers: List[str], target_date: date
) -> str:
    """Read pre-fetched news from ticker_news_library and format for LLM.

    Filters out not_relevant items and tags relevance level.
    Hard events are prominently flagged for sector-level impact.
    Phase 1 enhancement: Include credibility scores, event categories, and recency.
    """
    from app.db.models import TickerNewsLibrary
    from app.constants import TICKER_TO_ETFS

    cutoff = target_date - timedelta(days=2)
    parts = []

    for ticker in tickers:
        rows = (
            db.query(TickerNewsLibrary)
            .filter(
                TickerNewsLibrary.ticker == ticker,
                TickerNewsLibrary.date >= cutoff,
            )
            .order_by(
                TickerNewsLibrary.credibility.desc().nullslast(),
                TickerNewsLibrary.date.desc()
            )
            .limit(5)
            .all()
        )

        if not rows:
            parts.append(f"**{ticker}**: No recent news")
            continue

        relevant_rows = [r for r in rows if r.relevance != "not_relevant"]
        if not relevant_rows:
            parts.append(f"**{ticker}**: No relevant news")
            continue

        hard_events = [r for r in relevant_rows if r.is_hard_event]
        lines = []
        for r in relevant_rows:
            tags = []
            if r.sentiment:
                tags.append(r.sentiment)
            if r.relevance and r.relevance != "direct":
                tags.append(r.relevance)

            # Phase 1: Credibility tagging
            if r.credibility:
                if r.credibility >= 85:
                    tags.append(f"credible:{r.credibility}")
                elif r.credibility <= 40:
                    tags.append(f"low-cred:{r.credibility}")

            # Phase 1: Event type categorization
            if r.category and r.category not in ("company news", "general"):
                tags.append(r.category)

            # Phase 1: Recency marker
            if r.datetime_utc:
                from datetime import datetime
                age_hours = (datetime.now().timestamp() - r.datetime_utc) / 3600
                if age_hours < 6:
                    tags.append("breaking")

            tag_str = f"[{', '.join(tags)}]" if tags else ""
            summary = r.llm_summary or r.headline[:80]

            # Phase 1: Emphasize high-credibility news
            if r.credibility and r.credibility >= 85:
                lines.append(f"  - **{tag_str} {summary}**")
            else:
                lines.append(f"  - {tag_str} {summary}")

        block = f"**{ticker}**:\n" + "\n".join(lines)

        # Prominently flag hard events with sector impact notation
        if hard_events:
            affected_etfs = TICKER_TO_ETFS.get(ticker, [])
            etf_str = (
                f" (AFFECTS: {', '.join(affected_etfs)})" if affected_etfs else ""
            )
            block += (
                f"\n  HARD EVENT{etf_str}: "
                f"{hard_events[0].llm_summary}"
            )

            # Phase 1: Contagion analysis from related tickers
            related_tickers = set()
            for he in hard_events:
                if he.related:
                    related_tickers.update([t for t in he.related if t in tickers])
            if related_tickers:
                block += f"\n  🔗 CONTAGION RISK: {', '.join(sorted(related_tickers)[:5])}"

        parts.append(block)

    return "\n\n".join(parts) if parts else "(No news data available)"


def build_sector_context_from_db(db: Session, target_date: date) -> str:
    """Read sector_news_library and format sector outlooks for LLM.

    Phase 1 enhancement: Include average credibility of contributing news.
    """
    from app.db.models import SectorNewsLibrary, TickerNewsLibrary

    parts = []
    for etf in ETF_TOP5:
        row = db.query(SectorNewsLibrary).filter_by(
            sector=etf, date=target_date
        ).first()

        if not row:
            parts.append(f"**{etf}**: No sector data")
            continue

        themes = ", ".join(row.key_themes) if row.key_themes else "N/A"
        tickers = (
            ", ".join(row.contributing_tickers)
            if row.contributing_tickers else "N/A"
        )

        # Phase 1: Calculate average credibility of contributing news
        avg_credibility = None
        if row.contributing_tickers:
            cred_values = []
            for ticker in row.contributing_tickers:
                ticker_news = db.query(TickerNewsLibrary).filter(
                    TickerNewsLibrary.ticker == ticker,
                    TickerNewsLibrary.date == target_date,
                    TickerNewsLibrary.credibility.isnot(None)
                ).all()
                cred_values.extend([n.credibility for n in ticker_news])

            if cred_values:
                avg_credibility = sum(cred_values) / len(cred_values)

        cred_tag = ""
        if avg_credibility:
            if avg_credibility >= 75:
                cred_tag = f" [high-cred:{avg_credibility:.0f}]"
            elif avg_credibility <= 50:
                cred_tag = f" [low-cred:{avg_credibility:.0f}]"

        parts.append(
            f"**{etf}** [{row.outlook}] ({row.sentiment}){cred_tag}: "
            f"{row.sector_summary}\n"
            f"  Themes: {themes} | Sources: {tickers} ({row.news_count} items)"
        )

    return "\n\n".join(parts) if parts else "(No sector data available)"


def build_hard_flags_from_db(
    db: Session, tickers: List[str], target_date: date
) -> Dict[str, List[str]]:
    """Extract hard risk flags from ticker_news_library for allocation response."""
    from app.db.models import TickerNewsLibrary

    cutoff = target_date - timedelta(days=2)
    flags: Dict[str, List[str]] = {}

    for ticker in tickers:
        hard_rows = (
            db.query(TickerNewsLibrary)
            .filter(
                TickerNewsLibrary.ticker == ticker,
                TickerNewsLibrary.date >= cutoff,
                TickerNewsLibrary.is_hard_event.is_(True),
            )
            .all()
        )
        if hard_rows:
            flags[ticker] = [
                r.llm_summary or r.headline[:60] for r in hard_rows
            ]

    return flags


# ═══════════════════════════════════════════════════════════════
# Internal formatting helpers
# ═══════════════════════════════════════════════════════════════

def _format_earnings_flags(flags: Dict[str, bool]) -> str:
    if not flags:
        return "(No earnings data available)"
    upcoming = [t for t, has in flags.items() if has]
    clear    = [t for t, has in flags.items() if not has]
    lines = []
    if upcoming:
        lines.append(f"UPCOMING EARNINGS (high risk): {', '.join(upcoming)}")
    if clear:
        lines.append(f"No earnings soon: {', '.join(clear)}")
    return "\n".join(lines)


def _format_hard_flags(flags: Dict[str, List[str]]) -> str:
    if not flags:
        return "(No hard events detected)"
    lines = [
        "HARD EVENTS DETECTED -- Apply sector ceiling = 4 if holding affected:"
    ]
    for ticker, summaries in flags.items():
        lines.append(f"  - {ticker}: {summaries[0]}")
    return "\n".join(lines)


def _extract_key_events_from_context(macro_context: str) -> List[str]:
    """Pull numbered event lines out of format_macro_context output.

    Matches lines like:  [1] Iran war escalates oil supply risk
    """
    events = []
    for line in macro_context.splitlines():
        stripped = line.strip()
        if re.match(r'^\[\d+\]', stripped):
            events.append(stripped)
    # Fall back to full context if no structured events found
    return events if events else [macro_context]


# ═══════════════════════════════════════════════════════════════
# Main scoring function
# ═══════════════════════════════════════════════════════════════

async def run_micro_scoring(
    target_date: date,
    macro_context: str,
    holdings: Optional[List[str]] = None,
    news_digest: str = "(No news data available)",
    sector_context: str = "(No sector data available)",
    earnings_flags: Optional[Dict[str, bool]] = None,
    hard_flags: Optional[Dict[str, List[str]]] = None,
) -> str:
    """
    Score sector ETFs given macro backdrop, holdings, dual-layer news, earnings.

    Three-layer defence:
      Layer 1 -- STEP2_SYSTEM prompt with transmission rules
      Layer 2 -- applied_macro_rule CoT field (model names rule before scoring)
      Layer 3 -- _validate_scores() hard floor/ceiling override

    Returns raw JSON string for Step 3 / Step 4 consumption.
    """
    holdings_str   = ", ".join(holdings) if holdings else "(no holdings reported)"
    earnings_str   = _format_earnings_flags(earnings_flags or {})
    hard_flags_str = _format_hard_flags(hard_flags or {})

    combined_news = (
        f"### Sector Outlook (from pre-fetch)\n{sector_context}\n\n"
        f"### Individual Ticker News\n{news_digest}\n\n"
        f"### Hard Event Flags (SECTOR IMPACT)\n{hard_flags_str}"
    )

    # ── Stub mode ──
    if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY.startswith("sk-test"):
        await asyncio.sleep(1)
        stub = {etf: 5 for etf in
                ["XLK","XLF","XLV","XLE","XLI","XLP","XLU","XLY","XLC","XLRE","XLB"]}
        stub["applied_macro_rule"] = "None"
        stub["reasoning"] = "Stub mode -- no API key"
        return json.dumps(stub)

    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    user_prompt = f"""
{macro_context}

=== CURRENT HOLDINGS ===
{holdings_str}

=== NEWS & SECTOR INTELLIGENCE ===
{combined_news}

=== EARNINGS CALENDAR ===
{earnings_str}

---
REMINDER -- follow the 4-step scoring process in the system prompt:
1. Write applied_macro_rule first (Supply Shock / Rate Hike / Recession / Risk-On / None)
2. Apply macro floors/ceilings from the matching rule
3. Adjust +/-2 max using sector/ticker news above
4. Apply hard event penalty (sector ceiling = 4) if any holding is flagged
"""

    try:
        response = await client.beta.chat.completions.parse(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": STEP2_SYSTEM},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.0,
            max_tokens=800,
            response_format=SectorScores,
        )

        parsed: SectorScores = response.choices[0].message.parsed

        scores: Dict[str, int] = {
            "XLK":  parsed.XLK,
            "XLF":  parsed.XLF,
            "XLV":  parsed.XLV,
            "XLE":  parsed.XLE,
            "XLI":  parsed.XLI,
            "XLP":  parsed.XLP,
            "XLU":  parsed.XLU,
            "XLY":  parsed.XLY,
            "XLC":  parsed.XLC,
            "XLRE": parsed.XLRE,
            "XLB":  parsed.XLB,
        }

        # ── Layer 3: program-level validator ──
        key_events = _extract_key_events_from_context(macro_context)
        corrected, overrides = _validate_scores(
            scores,
            key_events=key_events,
            reasoning=parsed.reasoning,
            applied_rule=parsed.applied_macro_rule,
        )

        if overrides:
            for msg in overrides:
                logger.warning("[Step2] %s", msg)
                print(f"[{target_date}]   {msg}", flush=True)

        # Attach metadata for downstream logging / Step 3
        corrected["applied_macro_rule"] = parsed.applied_macro_rule
        corrected["reasoning"] = parsed.reasoning

        return json.dumps(corrected, ensure_ascii=False)

    except Exception as e:
        logger.error("[Step2] run_micro_scoring error: %s", e)
        fallback = {etf: 5 for etf in
                    ["XLK","XLF","XLV","XLE","XLI","XLP","XLU","XLY","XLC","XLRE","XLB"]}
        fallback["applied_macro_rule"] = "None"
        fallback["reasoning"] = f"LLM error -- fallback neutral scores: {e}"
        return json.dumps(fallback)