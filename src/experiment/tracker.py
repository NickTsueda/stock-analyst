"""Quarterly price tracker — fetches current prices and stores snapshots.

Triggered by cron job. No Claude API calls — cost is $0.
Usage: python -m src.experiment.tracker
"""
from __future__ import annotations

import logging
import sys
from datetime import date

import yfinance as yf

from src.experiment.db import (
    DEFAULT_DB_PATH,
    get_all_analyses,
    get_tickers,
    insert_snapshot,
)

logger = logging.getLogger(__name__)


def compute_quarter(analysis_date: date, snapshot_date: date) -> int:
    """Determine which quarter this snapshot represents (1-4).

    Based on months elapsed since analysis date:
    0-4 months = Q1, 5-7 = Q2, 8-10 = Q3, 11+ = Q4.
    """
    months = (snapshot_date.year - analysis_date.year) * 12 + (
        snapshot_date.month - analysis_date.month
    )
    if months <= 4:
        return 1
    elif months <= 7:
        return 2
    elif months <= 10:
        return 3
    else:
        return 4


def take_snapshot(db_path: str = DEFAULT_DB_PATH) -> dict:
    """Fetch prices for all tracked tickers + SPY and store snapshots.

    Returns summary dict with success/failure counts.
    """
    tickers = get_tickers(db_path)
    if not tickers:
        print("No tickers found in database. Run batch_runner first.")
        return {"success": 0, "failed": 0}

    analyses = get_all_analyses(db_path)
    analysis_date = date.fromisoformat(analyses[0]["analysis_date"])

    all_symbols = tickers + ["SPY"]
    print(f"Fetching prices for {len(all_symbols)} symbols...")
    raw = yf.download(all_symbols, period="1d", progress=False)
    # yfinance returns MultiIndex columns (metric, ticker); extract Close level.
    # When mocked in tests the return value is already a flat ticker DataFrame.
    if "Close" in raw.columns:
        prices = raw["Close"]
    else:
        prices = raw

    if len(prices) == 0:
        print("ERROR: yfinance returned no data")
        return {"success": 0, "failed": len(tickers)}

    latest = prices.iloc[-1]
    spy_price = float(latest.get("SPY", 0.0))
    today = date.today()
    quarter = compute_quarter(analysis_date, today)

    results = {"success": 0, "failed": 0}
    for ticker in tickers:
        price = latest.get(ticker)
        if price is None or price != price:  # NaN check
            logger.warning("No price data for %s", ticker)
            results["failed"] += 1
            continue

        insert_snapshot(db_path, {
            "ticker": ticker,
            "price": float(price),
            "spy_price": spy_price,
            "snapshot_date": today.isoformat(),
            "quarter": quarter,
        })
        results["success"] += 1

    print(f"Snapshot Q{quarter}: {results['success']} ok, {results['failed']} failed")
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    db = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DB_PATH
    take_snapshot(db)
