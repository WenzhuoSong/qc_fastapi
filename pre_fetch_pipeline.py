"""
Pre-Fetch Pipeline — 13:30 ET News Collection + LLM Batch Summarization

Runs as a separate Railway Cron Job 30 minutes before the main pipeline.

Two-layer output:
  1. ticker_news_library  — per-ticker headlines with summary, sentiment,
                            relevance, and hard-event flag
  2. sector_news_library  — per-ETF sector outlook synthesized from
                            constituent ticker news

Data sources merged:
  - QC current holdings + top_candidates (from POST /holdings)
  - ETF_TOP5 constituents (55 tickers across 11 sectors)

Usage:
    python pre_fetch_pipeline.py            # run for today
    python pre_fetch_pipeline.py 2026-03-14 # run for a specific date
    python pre_fetch_pipeline.py --force    # clear and re-run

Railway Cron (EDT): 30 17 * * 1-5  (13:30 ET)
Railway Cron (EST): 30 18 * * 1-5  (13:30 ET)
"""

import re
import sys
import time
import asyncio
import traceback
from datetime import date, datetime, timedelta
from typing import List, Literal

import httpx
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import settings
from app.constants import ETF_TOP5, ALL_SECTOR_TICKERS, TICKER_TO_ETFS
from app.db.database import SessionLocal, init_db
from app.db.models import DailyHoldings, TickerNewsLibrary, SectorNewsLibrary
from app.pipeline.data_fetcher import fetch_ticker_news

BATCH_SIZE = 10
PRE_FETCH_TIMEOUT = 600  # 10 minutes

# ═══════════════════════════════════════════════════════════════
# Pydantic models for Structured Outputs
# ═══════════════════════════════════════════════════════════════

class NewsAnalysis(BaseModel):
    index: int = Field(description="1-based index matching the input headline")
    summary: str = Field(description="Impact on this ticker in one sentence, max 30 words")
    sentiment: Literal["positive", "negative", "neutral"]
    relevance: Literal["direct", "indirect", "not_relevant"]
    is_hard_event: bool


class BatchAnalysisResponse(BaseModel):
    results: List[NewsAnalysis]


class SectorSummary(BaseModel):
    sector_sentiment: Literal["positive", "negative", "neutral"]
    outlook: Literal["bullish", "bearish", "neutral"]
    summary: str = Field(description="2-3 sentence sector outlook, max 60 words")
    key_themes: List[str] = Field(description="3-5 key themes driving this sector")


# ═══════════════════════════════════════════════════════════════
# System prompts
# ═══════════════════════════════════════════════════════════════

_SUMMARIZE_SYSTEM = (
    "You are a quantitative financial news analyst. Be concise and accurate.\n\n"
    "RELEVANCE RULE:\n"
    "  direct       → headline is directly about this company itself\n"
    "  indirect     → industry trend that affects this company and peers\n"
    "  not_relevant → headline has nothing to do with this company\n\n"
    "SENTIMENT RULE:\n"
    "  sentiment is the IMPACT on this ticker, NOT the tone of the headline.\n"
    "  Example: 'Competitor loses major contract' → sentiment=positive for this ticker.\n\n"
    "HARD EVENT RULE:\n"
    "is_hard_event = true ONLY for NEGATIVE, BINARY-OUTCOME events with UNHEDGEABLE RISK:\n"
    "  - Earnings miss / revenue shortfall / guidance cut\n"
    "  - FDA rejection / clinical trial failure\n"
    "  - Trading halt / suspension\n"
    "  - Being acquired (target of takeover, NOT the acquirer)\n"
    "  - SEC investigation / fraud allegation / class-action lawsuit\n"
    "  - Bankruptcy filing / debt default\n"
    "  - Regulatory ban / sanctions\n\n"
    "is_hard_event = false for ALL of these:\n"
    "  - Positive deals, partnerships, investments, contracts\n"
    "  - Analyst upgrades/downgrades\n"
    "  - General market commentary or sector trends\n"
    "  - Price movements or trading volume\n"
    "  - Product launches or expansion plans\n\n"
    "When in doubt, set is_hard_event = false."
)

_SECTOR_SYSTEM = (
    "You are a senior sector strategist. Given recent news from multiple "
    "companies in a sector ETF, synthesize a concise sector outlook.\n"
    "Focus on the NET effect of all news combined.\n\n"
    "IMPORTANT field definitions:\n"
    "  sector_sentiment = current news tone (what just happened)\n"
    "  outlook = forward-looking view (what will likely happen next)\n"
    "  These CAN differ. Example: negative news today but sector is oversold "
    "→ sentiment=negative, outlook=bullish.\n"
    "  Only set them equal when current tone and forward view genuinely align."
)

# ═══════════════════════════════════════════════════════════════
# Text sanitization
# ═══════════════════════════════════════════════════════════════

_CTRL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _sanitize(text: str) -> str:
    """Remove control characters and excessive whitespace."""
    text = _CTRL_CHARS.sub("", text)
    text = text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    return text.strip()


# ═══════════════════════════════════════════════════════════════
# Ticker-level: batch headline summarization
# ═══════════════════════════════════════════════════════════════

async def summarize_headlines_batch(
    ticker: str, news_items: List[dict]
) -> List[dict]:
    """Batch-summarize headlines for a single ticker with one LLM call.

    Uses OpenAI Structured Outputs to guarantee valid JSON.
    Returns a list of {summary, sentiment, relevance, is_hard_event} dicts.
    """
    if not news_items:
        return []

    if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY.startswith("sk-test"):
        return [
            {
                "summary": item.get("headline", "")[:80],
                "sentiment": "neutral",
                "relevance": "direct",
                "is_hard_event": False,
            }
            for item in news_items
        ]

    headlines_block = "\n".join(
        f"{i + 1}. {_sanitize(item.get('headline', ''))}"
        for i, item in enumerate(news_items[:BATCH_SIZE])
    )

    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    try:
        response = await client.beta.chat.completions.parse(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": _SUMMARIZE_SYSTEM},
                {"role": "user", "content": f"Ticker: {ticker}\nHeadlines:\n{headlines_block}"},
            ],
            temperature=0.0,
            max_tokens=1000,
            response_format=BatchAnalysisResponse,
        )

        parsed_results = response.choices[0].message.parsed.results

        results = []
        for i, item in enumerate(news_items[:BATCH_SIZE]):
            matched = next((p for p in parsed_results if p.index == i + 1), None)
            if matched:
                results.append({
                    "summary": matched.summary,
                    "sentiment": matched.sentiment,
                    "relevance": matched.relevance,
                    "is_hard_event": matched.is_hard_event,
                })
            else:
                results.append({
                    "summary": item.get("headline", "")[:80],
                    "sentiment": "neutral",
                    "relevance": "direct",
                    "is_hard_event": False,
                })
        return results

    except Exception as e:
        print(f"[LLM] summarize_headlines_batch error for {ticker}: {e}")
        return [
            {
                "summary": it.get("headline", "")[:80],
                "sentiment": "neutral",
                "relevance": "direct",
                "is_hard_event": False,
            }
            for it in news_items
        ]


# ═══════════════════════════════════════════════════════════════
# Sector-level: synthesize sector outlook from ticker news
# ═══════════════════════════════════════════════════════════════

async def summarize_sector_news(
    etf: str, news_list: List[dict]
) -> dict:
    """Synthesize a sector outlook from aggregated ticker news.

    news_list items have keys: ticker, summary, sentiment, relevance.
    Returns {sector_sentiment, outlook, summary, key_themes}.
    """
    if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY.startswith("sk-test"):
        return {
            "sector_sentiment": "neutral",
            "outlook": "neutral",
            "summary": f"Mock sector summary for {etf}",
            "key_themes": ["mock"],
        }

    news_block = "\n".join(
        f"- [{item['ticker']}] ({item['sentiment']}) {item['summary']}"
        for item in news_list[:30]
    )

    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    try:
        response = await client.beta.chat.completions.parse(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": _SECTOR_SYSTEM},
                {"role": "user", "content": (
                    f"Sector ETF: {etf}\n"
                    f"Top-5 constituents: {', '.join(ETF_TOP5.get(etf, []))}\n"
                    f"Recent news ({len(news_list)} items):\n{news_block}"
                )},
            ],
            temperature=0.0,
            max_tokens=500,
            response_format=SectorSummary,
        )

        parsed = response.choices[0].message.parsed
        return {
            "sector_sentiment": parsed.sector_sentiment,
            "outlook": parsed.outlook,
            "summary": parsed.summary,
            "key_themes": parsed.key_themes[:5],
        }

    except Exception as e:
        print(f"[LLM] summarize_sector_news error for {etf}: {e}")
        return {
            "sector_sentiment": "neutral",
            "outlook": "neutral",
            "summary": f"Sector summary unavailable for {etf}",
            "key_themes": [],
        }


# ═══════════════════════════════════════════════════════════════
# Per-ticker processing
# ═══════════════════════════════════════════════════════════════

async def process_ticker(
    db: Session, ticker: str, target_date: date
) -> tuple[int, List[dict]]:
    """Fetch news for one ticker, summarize, and store.

    Returns (count_of_new_rows, list_of_relevant_summaries_for_sector_pool).
    """
    news_items = fetch_ticker_news(ticker, days_back=2, limit=BATCH_SIZE)
    if not news_items:
        return 0, []

    new_headlines = []
    for item in news_items:
        headline = _sanitize(item.get("headline", ""))
        if not headline:
            continue
        item["headline"] = headline
        exists = db.query(TickerNewsLibrary).filter_by(
            ticker=ticker, headline=headline
        ).first()
        if not exists:
            new_headlines.append(item)

    if not new_headlines:
        return 0, []

    summaries = await summarize_headlines_batch(ticker, new_headlines)

    count = 0
    relevant_for_sector = []
    for item, summary_data in zip(new_headlines, summaries):
        try:
            db.add(TickerNewsLibrary(
                ticker=ticker,
                date=target_date,
                headline=item.get("headline", ""),
                source=item.get("source", ""),
                llm_summary=summary_data.get("summary", ""),
                sentiment=summary_data.get("sentiment", "neutral"),
                relevance=summary_data.get("relevance", "direct"),
                is_hard_event=summary_data.get("is_hard_event", False),
            ))
            db.flush()
            count += 1

            if summary_data.get("relevance") != "not_relevant":
                relevant_for_sector.append({
                    "ticker": ticker,
                    "summary": summary_data.get("summary", ""),
                    "sentiment": summary_data.get("sentiment", "neutral"),
                    "relevance": summary_data.get("relevance", "direct"),
                })
        except Exception:
            db.rollback()

    db.commit()
    return count, relevant_for_sector


# ═══════════════════════════════════════════════════════════════
# Main pipeline
# ═══════════════════════════════════════════════════════════════

async def run_pre_fetch(target_date: date, force: bool = False) -> None:
    """Main pre-fetch logic: collect all tickers, fetch + summarize, aggregate sectors."""
    db: Session = SessionLocal()

    try:
        # ── Force cleanup ──
        if force:
            del_ticker = (
                db.query(TickerNewsLibrary)
                .filter(TickerNewsLibrary.date == target_date)
                .delete()
            )
            del_sector = (
                db.query(SectorNewsLibrary)
                .filter(SectorNewsLibrary.date == target_date)
                .delete()
            )
            db.commit()
            print(f"[{target_date}] Force mode: cleared {del_ticker} ticker articles, {del_sector} sector summaries")

        # ── Merge data sources ──
        holdings = db.query(DailyHoldings).filter_by(date=target_date).first()
        qc_tickers: set[str] = set()
        if holdings:
            qc_tickers = set(holdings.tickers or [])
            if holdings.payload and holdings.payload.get("top_candidates"):
                qc_tickers |= set(holdings.payload["top_candidates"])
        else:
            print(f"[{target_date}] No holdings record — using ETF_TOP5 only")

        all_tickers = sorted(qc_tickers | set(ALL_SECTOR_TICKERS))
        print(f"[{target_date}] Pre-fetch targets: {len(all_tickers)} tickers")
        print(f"[{target_date}]   QC tickers: {len(qc_tickers)}")
        print(f"[{target_date}]   ETF_TOP5 constituents: {len(ALL_SECTOR_TICKERS)}")

        # ── Phase 1: Ticker-level fetch + summarize ──
        sector_news_pool: dict[str, List[dict]] = {etf: [] for etf in ETF_TOP5}
        total_new = 0

        for ticker in all_tickers:
            count, relevant = await process_ticker(db, ticker, target_date)
            if count > 0:
                print(f"[{target_date}]   {ticker}: {count} new articles stored")
            total_new += count

            for etf in TICKER_TO_ETFS.get(ticker, []):
                sector_news_pool[etf].extend(relevant)

            await asyncio.sleep(1)

        print(f"[{target_date}] Phase 1 complete: {total_new} new articles across {len(all_tickers)} tickers")

        # ── Phase 2: Sector-level aggregation ──
        sector_count = 0
        for etf, news_list in sector_news_pool.items():
            if not news_list:
                print(f"[{target_date}]   {etf}: no relevant news, skipping sector summary")
                continue

            summary = await summarize_sector_news(etf, news_list)
            contributing = sorted(set(n["ticker"] for n in news_list))

            existing = db.query(SectorNewsLibrary).filter_by(
                sector=etf, date=target_date
            ).first()
            if existing:
                existing.sector_summary = summary["summary"]
                existing.sentiment = summary["sector_sentiment"]
                existing.outlook = summary["outlook"]
                existing.key_themes = summary["key_themes"]
                existing.contributing_tickers = contributing
                existing.news_count = len(news_list)
            else:
                db.add(SectorNewsLibrary(
                    sector=etf,
                    date=target_date,
                    sector_summary=summary["summary"],
                    sentiment=summary["sector_sentiment"],
                    outlook=summary["outlook"],
                    key_themes=summary["key_themes"],
                    contributing_tickers=contributing,
                    news_count=len(news_list),
                ))
            db.commit()
            sector_count += 1
            print(f"[{target_date}]   {etf}: {summary['outlook']} ({len(news_list)} items from {contributing})")

        print(f"[{target_date}] Phase 2 complete: {sector_count} sector summaries generated")

    except Exception as e:
        print(f"[{target_date}] Pre-fetch error: {traceback.format_exc()}")
        raise e

    finally:
        db.close()


# ═══════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════

def _wait_for_network(max_retries: int = 10, delay: int = 5) -> bool:
    """Block until outbound HTTPS is reachable (cold-start network init)."""
    time.sleep(3)
    for i in range(max_retries):
        try:
            httpx.get("https://finnhub.io", timeout=5)
            print("[NET] Network ready")
            return True
        except Exception as e:
            print(f"[NET] Waiting for network... attempt {i + 1}/{max_retries}: {e}")
            time.sleep(delay)
    return False


async def main() -> None:
    force = "--force" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--force"]
    target = date.today()
    if args:
        target = datetime.strptime(args[0], "%Y-%m-%d").date()

    print(f"=== Pre-Fetch Pipeline Start: {target} {'(FORCE)' if force else ''} ===")

    if not _wait_for_network():
        print("[FATAL] Network unavailable after retries, aborting")
        sys.exit(1)

    init_db()

    try:
        await asyncio.wait_for(run_pre_fetch(target, force=force), timeout=PRE_FETCH_TIMEOUT)
        print(f"=== Pre-Fetch Pipeline Success: {target} ===")
    except asyncio.TimeoutError:
        print(f"[FATAL] Pre-fetch TIMEOUT after {PRE_FETCH_TIMEOUT}s")
        sys.exit(1)
    except Exception as e:
        print(f"[FATAL] Pre-fetch CRASHED: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
