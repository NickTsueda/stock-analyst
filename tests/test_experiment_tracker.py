"""Tests for quarterly price tracker."""
from __future__ import annotations

import os
import tempfile
from unittest.mock import patch, MagicMock
from datetime import date

import pandas as pd
import pytest

from src.experiment.tracker import take_snapshot, compute_quarter
from src.experiment.db import init_db, insert_analysis, get_snapshots


@pytest.fixture
def db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    for ticker in ["AAPL", "MSFT"]:
        insert_analysis(path, {
            "ticker": ticker,
            "company_name": f"{ticker} Inc.",
            "sector": "Technology",
            "recommendation": "BUY",
            "confidence_score": 70,
            "data_completeness": 100,
            "earnings_quality": 70,
            "valuation_clarity": 70,
            "company_predictability": 70,
            "insider_signal": 50,
            "macro_conditions": 60,
            "price_at_analysis": 100.0,
            "spy_price_at_analysis": 500.0,
            "analysis_date": "2026-03-28",
            "analysis_cost": 0.18,
        })
    yield path
    os.unlink(path)


class TestComputeQuarter:
    def test_q1_three_months(self):
        assert compute_quarter(date(2026, 3, 28), date(2026, 6, 28)) == 1

    def test_q2_six_months(self):
        assert compute_quarter(date(2026, 3, 28), date(2026, 9, 28)) == 2

    def test_q3_nine_months(self):
        assert compute_quarter(date(2026, 3, 28), date(2026, 12, 28)) == 3

    def test_q4_twelve_months(self):
        assert compute_quarter(date(2026, 3, 28), date(2027, 3, 28)) == 4


class TestTakeSnapshot:
    @patch("src.experiment.tracker.yf.download")
    def test_writes_snapshots_for_all_tickers(self, mock_download, db_path):
        mock_df = pd.DataFrame(
            {"AAPL": [185.0], "MSFT": [415.0], "SPY": [520.0]},
            index=pd.to_datetime(["2026-06-28"]),
        )
        mock_download.return_value = mock_df

        result = take_snapshot(db_path)
        assert result["success"] == 2
        assert result["failed"] == 0

        aapl_snaps = get_snapshots(db_path, "AAPL")
        assert len(aapl_snaps) == 1
        assert aapl_snaps[0]["price"] == 185.0
        assert aapl_snaps[0]["spy_price"] == 520.0
