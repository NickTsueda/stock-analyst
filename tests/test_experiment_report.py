"""Tests for experiment report generator."""
from __future__ import annotations

import os
import tempfile

import pytest

from src.experiment.report import generate_report
from src.experiment.db import init_db, insert_analysis, insert_snapshot


@pytest.fixture
def db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)

    base = {
        "company_name": "Test Inc.",
        "sector": "Technology",
        "data_completeness": 100,
        "earnings_quality": 70,
        "valuation_clarity": 70,
        "company_predictability": 70,
        "insider_signal": 50,
        "macro_conditions": 60,
        "analysis_date": "2026-03-28",
        "analysis_cost": 0.18,
    }
    insert_analysis(path, {**base, "ticker": "AAA", "recommendation": "BUY",
                           "confidence_score": 80, "price_at_analysis": 100.0,
                           "spy_price_at_analysis": 500.0})
    insert_analysis(path, {**base, "ticker": "BBB", "recommendation": "HOLD",
                           "confidence_score": 55, "price_at_analysis": 50.0,
                           "spy_price_at_analysis": 500.0})
    insert_analysis(path, {**base, "ticker": "CCC", "recommendation": "SELL",
                           "confidence_score": 30, "price_at_analysis": 200.0,
                           "spy_price_at_analysis": 500.0})

    # Q1 snapshots — AAA up 20%, BBB flat, CCC down 10%, SPY up 5%
    insert_snapshot(path, {"ticker": "AAA", "price": 120.0, "spy_price": 525.0,
                           "snapshot_date": "2026-06-28", "quarter": 1})
    insert_snapshot(path, {"ticker": "BBB", "price": 50.0, "spy_price": 525.0,
                           "snapshot_date": "2026-06-28", "quarter": 1})
    insert_snapshot(path, {"ticker": "CCC", "price": 180.0, "spy_price": 525.0,
                           "snapshot_date": "2026-06-28", "quarter": 1})

    yield path
    os.unlink(path)


class TestGenerateReport:
    def test_report_contains_bucket_performance(self, db_path):
        report = generate_report(db_path)
        assert "BUY" in report
        assert "HOLD" in report
        assert "SELL" in report

    def test_report_contains_returns(self, db_path):
        report = generate_report(db_path)
        assert "20.0" in report  # AAA: (120-100)/100 = +20%

    def test_report_contains_spy_benchmark(self, db_path):
        report = generate_report(db_path)
        assert "SPY" in report

    def test_report_with_no_snapshots(self, db_path):
        fd, fresh = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        init_db(fresh)
        base = {
            "company_name": "T", "sector": "Tech", "data_completeness": 100,
            "earnings_quality": 70, "valuation_clarity": 70,
            "company_predictability": 70, "insider_signal": 50,
            "macro_conditions": 60, "analysis_date": "2026-03-28",
            "analysis_cost": 0.18, "spy_price_at_analysis": 500.0,
        }
        insert_analysis(fresh, {**base, "ticker": "X", "recommendation": "BUY",
                                "confidence_score": 70, "price_at_analysis": 100.0})
        report = generate_report(fresh)
        assert "No snapshot data" in report
        os.unlink(fresh)
