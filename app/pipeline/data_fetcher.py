"""
Data Fetcher — External API Integration (Finnhub)

Provides market news and earnings data as context for the LLM pipeline.
All external calls have timeouts and graceful error handling so a single
ticker failure never crashes the entire pipeline.
"""

import asyncio
from datetime import datetime, timedelta
from typing import List, Dict

import httpx

from app.config import settings


class DataFetcher:
    BASE_URL = "https://finnhub.io/api/v1"
    MAX_NEWS_PER_TICKER = 5
    REQUEST_TIMEOUT = 10

    def __init__(self) -> None:
        self.token = settings.FINNHUB_API_KEY

    async def fetch_ticker_news(
        self, tickers: List[str], days_back: int = 2
    ) -> Dict[str, List[str]]:
        """Fetch recent company news for a list of tickers.

        Returns {"NVDA": ["headline: summary", ...], "AAPL": [...]}
        """
        if not self.token:
            print("[DataFetcher] FINNHUB_API_KEY not set, returning empty news")
            return {t: [] for t in tickers}

        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")

        results: Dict[str, List[str]] = {}

        async with httpx.AsyncClient(timeout=self.REQUEST_TIMEOUT) as client:
            for ticker in tickers:
                results[ticker] = await self._fetch_one(
                    client, ticker, start_date, end_date
                )
                await asyncio.sleep(0.2)  # respect Finnhub rate limit

        return results

    async def _fetch_one(
        self,
        client: httpx.AsyncClient,
        ticker: str,
        start_date: str,
        end_date: str,
    ) -> List[str]:
        try:
            resp = await client.get(
                f"{self.BASE_URL}/company-news",
                params={
                    "symbol": ticker,
                    "from": start_date,
                    "to": end_date,
                    "token": self.token,
                },
            )
            if resp.status_code != 200:
                print(f"[DataFetcher] {ticker}: HTTP {resp.status_code}")
                return []

            articles = resp.json()
            return [
                f"{a['headline']}: {a.get('summary', '')}"
                for a in articles[: self.MAX_NEWS_PER_TICKER]
                if a.get("headline")
            ]

        except Exception as e:
            print(f"[DataFetcher] {ticker} error: {e}")
            return []

    async def check_earnings_calendar(
        self, tickers: List[str], days_ahead: int = 3
    ) -> List[str]:
        """Return tickers that have earnings within the next N days.

        TODO: Implement via Finnhub /calendar/earnings endpoint.
        """
        return []
