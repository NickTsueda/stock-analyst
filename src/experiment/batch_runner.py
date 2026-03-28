"""Batch runner — runs tickers through the analysis pipeline and stores results.

Usage:
    python -m src.experiment.batch_runner          # uses screener for 50 stocks
    python -m src.experiment.batch_runner AAPL MSFT # specific tickers
"""
from __future__ import annotations

import logging
import sys
from datetime import date

import anthropic
import yfinance as yf

from src.agents.orchestrator import OrchestratorAgent
from src.experiment.db import DEFAULT_DB_PATH, init_db, insert_analysis
from src.experiment.screener import fetch_sp500_tickers, select_stratified_sample
from src.models import DataPackage, InvestmentThesis

logger = logging.getLogger(__name__)


def _get_spy_price() -> float:
    """Fetch current SPY price as benchmark."""
    spy = yf.Ticker("SPY")
    return spy.info.get("regularMarketPrice", 0.0)


def extract_analysis_row(
    data: DataPackage,
    thesis: InvestmentThesis | None,
    spy_price: float,
) -> dict:
    """Extract a flat dict from pipeline output for the analyses table."""
    price = data.market_data.current_price if data.market_data else 0.0
    sector = data.market_data.sector if data.market_data else ""

    if thesis is None or thesis.confidence is None:
        return {
            "ticker": data.ticker,
            "company_name": data.company_name,
            "sector": sector,
            "recommendation": "INCOMPLETE",
            "confidence_score": 0,
            "data_completeness": data.data_completeness_score,
            "earnings_quality": 0,
            "valuation_clarity": 0,
            "company_predictability": data.company_predictability_score,
            "insider_signal": 0,
            "macro_conditions": 0,
            "price_at_analysis": price,
            "spy_price_at_analysis": spy_price,
            "analysis_date": date.today().isoformat(),
            "analysis_cost": 0.0,
        }

    driver_map = {d.factor: d.score for d in thesis.confidence.drivers}

    return {
        "ticker": data.ticker,
        "company_name": data.company_name,
        "sector": sector,
        "recommendation": thesis.recommendation.value,
        "confidence_score": thesis.confidence.score,
        "data_completeness": driver_map.get("Data Completeness", 0),
        "earnings_quality": driver_map.get("Earnings Quality", 0),
        "valuation_clarity": driver_map.get("Valuation Clarity", 0),
        "company_predictability": driver_map.get("Company Predictability", 0),
        "insider_signal": driver_map.get("Insider Signal", 0),
        "macro_conditions": driver_map.get("Macro Conditions", 0),
        "price_at_analysis": price,
        "spy_price_at_analysis": spy_price,
        "analysis_date": date.today().isoformat(),
        "analysis_cost": 0.20,
    }


def run_batch(
    tickers: list[str],
    db_path: str = DEFAULT_DB_PATH,
) -> dict:
    """Run a list of tickers through the full analysis pipeline.

    Returns summary dict with counts of successes/failures.
    """
    init_db(db_path)
    client = anthropic.Anthropic()
    orchestrator = OrchestratorAgent(client)
    spy_price = _get_spy_price()

    results = {"success": 0, "failed": 0, "errors": []}

    for i, ticker in enumerate(tickers, 1):
        print(f"[{i}/{len(tickers)}] Analyzing {ticker}...")
        try:
            data, analysis, thesis = orchestrator.run(ticker)
            row = extract_analysis_row(data, thesis, spy_price)
            insert_analysis(db_path, row)
            results["success"] += 1
            print(f"  -> {row['recommendation']} (confidence: {row['confidence_score']})")
        except Exception as e:
            logger.error("Failed to analyze %s: %s", ticker, e)
            results["failed"] += 1
            results["errors"].append({"ticker": ticker, "error": str(e)})
            print(f"  -> FAILED: {e}")

    print(f"\nBatch complete: {results['success']} succeeded, {results['failed']} failed")
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) > 1:
        tickers = [t.upper() for t in sys.argv[1:]]
    else:
        print("Fetching S&P 500 list...")
        sp500 = fetch_sp500_tickers()
        sample = select_stratified_sample(sp500, sample_size=50)
        tickers = list(sample["Symbol"])
        print(f"Selected {len(tickers)} tickers across {sample['GICS Sector'].nunique()} sectors")

    run_batch(tickers)
