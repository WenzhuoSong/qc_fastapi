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

import sys
import json
import asyncio
import traceback
from datetime import date, datetime, timedelta
from typing import List

from sqlalchemy.orm import Session

from app.config import settings
from app.db.database import SessionLocal, init_db
from app.db.models import DailyHoldings, TickerNewsLibrary
from app.pipeline.data_fetcher import fetch_ticker_news

BATCH_SIZE = 10
PRE_FETCH_TIMEOUT = 600  # 10 minutes


async def summarize_headlines_batch(
    ticker: str, news_items: List[dict]
) -> List[dict]:
    """Batch-summarize headlines for a single ticker with one LLM call.

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
        f"{i + 1}. {item.get('headline', '')}"
        for i, item in enumerate(news_items[:BATCH_SIZE])
    )

    prompt = (
        f"Ticker: {ticker}\n"
        f"Headlines:\n{headlines_block}\n\n"
        "For each headline, return ONLY a JSON array (no markdown fences):\n"
        "[\n"
        '  {"index": 1, "summary": "<one sentence, max 20 words>", '
        '"sentiment": "positive|negative|neutral", '
        '"is_hard_event": true|false}\n'
        "]\n\n"
        "is_hard_event = true ONLY for: earnings surprise, FDA decision, "
        "trading halt, merger/acquisition, SEC investigation, major lawsuit, "
        "bankruptcy, significant regulatory action."
    )

    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    response = await client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": "You are a financial news analyst. Be concise and accurate."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.1,
        max_tokens=1000,
    )

    raw = response.choices[0].message.content or "[]"

    start = raw.find("[")
    end = raw.rfind("]")
    if start == -1 or end == -1:
        return [
            {"summary": it.get("headline", "")[:80], "sentiment": "neutral", "is_hard_event": False}
            for it in news_items
        ]

    try:
        parsed = json.loads(raw[start:end + 1])
        results = []
        for i, item in enumerate(news_items[:BATCH_SIZE]):
            matched = next((p for p in parsed if p.get("index") == i + 1), None)
            if matched:
                results.append({
                    "summary": str(matched.get("summary", ""))[:200],
                    "sentiment": matched.get("sentiment", "neutral"),
                    "is_hard_event": bool(matched.get("is_hard_event", False)),
                })
            else:
                results.append({
                    "summary": item.get("headline", "")[:80],
                    "sentiment": "neutral",
                    "is_hard_event": False,
                })
        return results
    except json.JSONDecodeError:
        return [
            {"summary": it.get("headline", "")[:80], "sentiment": "neutral", "is_hard_event": False}
            for it in news_items
        ]


async def process_ticker(db: Session, ticker: str, target_date: date) -> int:
    """Fetch news for one ticker, summarize, and store. Returns count of new rows."""
    news_items = fetch_ticker_news(ticker, days_back=2, limit=BATCH_SIZE)
    if not news_items:
        return 0

    new_headlines = []
    for item in news_items:
        headline = item.get("headline", "").strip()
        if not headline:
            continue
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
        db.add(TickerNewsLibrary(
            ticker=ticker,
            date=target_date,
            headline=item.get("headline", ""),
            source=item.get("source", ""),
            llm_summary=summary_data.get("summary", ""),
            sentiment=summary_data.get("sentiment", "neutral"),
            is_hard_event=summary_data.get("is_hard_event", False),
        ))
        count += 1

    db.commit()
    return count


async def run_pre_fetch(target_date: date) -> None:
    """Main pre-fetch logic: collect all tickers, fetch news, summarize."""
    db: Session = SessionLocal()

    try:
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


async def main() -> None:
    target = date.today()
    if len(sys.argv) > 1:
        target = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()

    print(f"=== Pre-Fetch Pipeline Start: {target} ===")
    init_db()

    try:
        await asyncio.wait_for(run_pre_fetch(target), timeout=PRE_FETCH_TIMEOUT)
        print(f"=== Pre-Fetch Pipeline Success: {target} ===")
    except asyncio.TimeoutError:
        print(f"[FATAL] Pre-fetch TIMEOUT after {PRE_FETCH_TIMEOUT}s")
        sys.exit(1)
    except Exception as e:
        print(f"[FATAL] Pre-fetch CRASHED: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
