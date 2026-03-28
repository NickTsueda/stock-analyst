"""Tests for S&P 500 stratified random stock screener."""
from unittest.mock import patch

import pandas as pd
import pytest

from src.experiment.screener import (
    fetch_sp500_tickers,
    compute_sector_allocation,
    select_stratified_sample,
)


# Minimal mock of the Wikipedia S&P 500 table
MOCK_SP500 = pd.DataFrame({
    "Symbol": ["AAPL", "MSFT", "GOOGL", "AMZN", "META",
               "JPM", "BAC", "WFC",
               "JNJ", "PFE",
               "XOM", "CVX"],
    "Security": ["Apple Inc.", "Microsoft Corp", "Alphabet Inc.", "Amazon.com Inc.",
                 "Meta Platforms", "JPMorgan Chase", "Bank of America", "Wells Fargo",
                 "Johnson & Johnson", "Pfizer Inc.", "Exxon Mobil", "Chevron Corp"],
    "GICS Sector": [
        "Information Technology", "Information Technology",
        "Communication Services", "Consumer Discretionary",
        "Communication Services",
        "Financials", "Financials", "Financials",
        "Health Care", "Health Care",
        "Energy", "Energy",
    ],
})


class TestFetchSp500Tickers:
    @patch("src.experiment.screener.pd.read_html")
    def test_returns_dataframe_with_required_columns(self, mock_read_html):
        mock_read_html.return_value = [MOCK_SP500]
        df = fetch_sp500_tickers()
        assert "Symbol" in df.columns
        assert "GICS Sector" in df.columns
        assert len(df) == 12


class TestComputeSectorAllocation:
    def test_allocations_sum_to_sample_size(self):
        alloc = compute_sector_allocation(MOCK_SP500, sample_size=6)
        assert sum(alloc.values()) == 6

    def test_proportional_to_sector_weights(self):
        # IT is 2/12 = 16.7%, Financials is 3/12 = 25%
        alloc = compute_sector_allocation(MOCK_SP500, sample_size=12)
        assert alloc["Financials"] >= alloc["Information Technology"]

    def test_every_sector_gets_at_least_one(self):
        alloc = compute_sector_allocation(MOCK_SP500, sample_size=6)
        for sector in MOCK_SP500["GICS Sector"].unique():
            assert alloc[sector] >= 1


class TestSelectStratifiedSample:
    def test_returns_correct_count(self):
        result = select_stratified_sample(MOCK_SP500, sample_size=6)
        assert len(result) == 6

    def test_result_has_required_columns(self):
        result = select_stratified_sample(MOCK_SP500, sample_size=6)
        assert "Symbol" in result.columns
        assert "GICS Sector" in result.columns

    def test_all_sectors_represented(self):
        result = select_stratified_sample(MOCK_SP500, sample_size=6)
        result_sectors = set(result["GICS Sector"])
        source_sectors = set(MOCK_SP500["GICS Sector"])
        assert result_sectors == source_sectors

    def test_respects_seed_for_reproducibility(self):
        r1 = select_stratified_sample(MOCK_SP500, sample_size=6, seed=42)
        r2 = select_stratified_sample(MOCK_SP500, sample_size=6, seed=42)
        assert list(r1["Symbol"]) == list(r2["Symbol"])
