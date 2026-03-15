"""
ETF Sector Mapping — Top 5 Holdings per Sector ETF

Used by pre_fetch_pipeline to expand coverage beyond QC candidates.
Maps each sector ETF to its top-5 constituent stocks so the pipeline
can aggregate individual ticker news into sector-level summaries.

Source: SSGA (State Street) ETF fact sheets.
Last updated: 2026-03 — review quarterly (3/6/9/12).
"""

ETF_TOP5 = {
    "XLK":  ["AAPL", "NVDA", "MSFT", "AVGO", "AMD"],
    "XLF":  ["BRK-B", "JPM", "V", "MA", "BAC"],
    "XLV":  ["LLY", "UNH", "JNJ", "ABBV", "MRK"],
    "XLY":  ["AMZN", "TSLA", "HD", "MCD", "BKNG"],
    "XLC":  ["META", "GOOGL", "NFLX", "DIS", "TMUS"],
    "XLE":  ["XOM", "CVX", "COP", "EOG", "SLB"],
    "XLI":  ["GE", "CAT", "RTX", "HON", "UNP"],
    "XLP":  ["PG", "COST", "KO", "PEP", "WMT"],
    "XLU":  ["NEE", "SO", "DUK", "SRE", "AEP"],
    "XLB":  ["LIN", "APD", "SHW", "FCX", "NEM"],
    "XLRE": ["PLD", "AMT", "EQIX", "WELL", "SPG"],
}

ALL_SECTOR_TICKERS = sorted(set(
    t for tickers in ETF_TOP5.values() for t in tickers
))

TICKER_TO_ETFS: dict[str, list[str]] = {}
for _etf, _members in ETF_TOP5.items():
    for _t in _members:
        TICKER_TO_ETFS.setdefault(_t, []).append(_etf)
