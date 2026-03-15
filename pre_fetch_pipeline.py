"""
Pre-Fetch Pipeline — 13:30 ET News Collection + LLM Batch Summarization

Runs as a separate Railway Cron Job 30 minutes before the main pipeline.
Fetches company news for all top_candidates and current holdings,
summarizes them with a single LLM call per ticker batch, and stores
the results in ticker_news_library for the 14:00 pipeline to consume.

Usage:
    python pre_fetch_pipeline.py            # run for today
    python pre_fetch_pipeline.py 2026-03-14 # run for a specific date

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
from app.db.database import SessionLocal, init_db
from app.db.models import DailyHoldings, TickerNewsLibrary
from app.pipeline.data_fetcher import fetch_ticker_news

BATCH_SIZE = 10
PRE_FETCH_TIMEOUT = 600  # 10 minutes


class NewsAnalysis(BaseModel):
    index: int = Field(description="1-based index matching the input headline")
    summary: str = Field(description="One sentence summary, max 30 words")
    sentiment: Literal["positive", "negative", "neutral"]
    is_hard_event: bool


class BatchAnalysisResponse(BaseModel):
    results: List[NewsAnalysis]


_SUMMARIZE_SYSTEM = (
    "You are a quantitative financial news analyst. Be concise and accurate.\n\n"
    "CRITICAL — is_hard_event classification rules:\n"
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

_CTRL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _sanitize(text: str) -> str:
    """Remove control characters and excessive whitespace that break JSON serialization."""
    text = _CTRL_CHARS.sub("", text)
    text = text.replace("\r\n", " ").replace("\n", " ").replace("\r", " ")
    return text.strip()


async def summarize_headlines_batch(
    ticker: str, news_items: List[dict]
) -> List[dict]:
    """Batch-summarize headlines for a single ticker with one LLM call.

    Uses OpenAI Structured Outputs to guarantee valid JSON — no manual parsing.
    Returns a list of {summary, sentiment, is_hard_event} dicts,
    one per input headline (in order).
    """
    if not news_items:
        return []

    if not settings.OPENAI_API_KEY or settings.OPENAI_API_KEY.startswith("sk-test"):
        return [
            {
                "summary": item.get("headline", "")[:80],
                "sentiment": "neutral",
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
                    "summary": matched.summary[:200],
                    "sentiment": matched.sentiment,
                    "is_hard_event": matched.is_hard_event,
                })
            else:
                results.append({
                    "summary": item.get("headline", "")[:80],
                    "sentiment": "neutral",
                    "is_hard_event": False,
                })
        return results

    except Exception as e:
        print(f"[LLM] summarize_headlines_batch error for {ticker}: {e}")
        return [
            {
                "summary": it.get("headline", "")[:80],
                "sentiment": "neutral",
                "is_hard_event": False,
            }
            for it in news_items
        ]


async def process_ticker(db: Session, ticker: str, target_date: date) -> int:
    """Fetch news for one ticker, summarize, and store. Returns count of new rows."""
    news_items = fetch_ticker_news(ticker, days_back=2, limit=BATCH_SIZE)
    if not news_items:
        return 0

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
        return 0

    summaries = await summarize_headlines_batch(ticker, new_headlines)

    count = 0
    for item, summary_data in zip(new_headlines, summaries):
        try:
            db.add(TickerNewsLibrary(
                ticker=ticker,
                date=target_date,
                headline=item.get("headline", ""),
                source=item.get("source", ""),
                llm_summary=summary_data.get("summary", ""),
                sentiment=summary_data.get("sentiment", "neutral"),
                is_hard_event=summary_data.get("is_hard_event", False),
            ))
            db.flush()
            count += 1
        except Exception:
            db.rollback()

    db.commit()
    return count


async def run_pre_fetch(target_date: date, force: bool = False) -> None:
    """Main pre-fetch logic: collect all tickers, fetch news, summarize."""
    db: Session = SessionLocal()

    try:
        if force:
            deleted = (
                db.query(TickerNewsLibrary)
                .filter(TickerNewsLibrary.date == target_date)
                .delete()
            )
            db.commit()
            print(f"[{target_date}] Force mode: cleared {deleted} existing articles")

        holdings = db.query(DailyHoldings).filter_by(date=target_date).first()
        if not holdings:
            print(f"[{target_date}] No holdings record, skipping pre-fetch")
            return

        current = set(holdings.tickers or [])
        candidates = set()
        if holdings.payload and holdings.payload.get("top_candidates"):
            candidates = set(holdings.payload["top_candidates"])

        all_tickers = sorted(current | candidates)
        print(f"[{target_date}] Pre-fetch targets: {len(all_tickers)} tickers")
        print(f"[{target_date}]   Holdings: {sorted(current)}")
        print(f"[{target_date}]   Candidates: {sorted(candidates - current)}")

        total_new = 0
        for ticker in all_tickers:
            count = await process_ticker(db, ticker, target_date)
            if count > 0:
                print(f"[{target_date}]   {ticker}: {count} new articles stored")
            total_new += count
            await asyncio.sleep(0.3)

        print(f"[{target_date}] Pre-fetch complete: {total_new} new articles across {len(all_tickers)} tickers")

    except Exception as e:
        print(f"[{target_date}] Pre-fetch error: {traceback.format_exc()}")
        raise e

    finally:
        db.close()


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
