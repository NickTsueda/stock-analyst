"""Tests for experiment database module."""
import os
import sqlite3
import tempfile

import pytest

from src.experiment.db import (
    init_db,
    insert_analysis,
    insert_snapshot,
    get_all_analyses,
    get_snapshots,
    get_tickers,
)


@pytest.fixture
def db_path():
    """Temporary database file, cleaned up after test."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    os.unlink(path)


class TestInitDb:
    def test_creates_tables(self, db_path):
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = {t[0] for t in tables}
        assert "analyses" in table_names
        assert "snapshots" in table_names
        conn.close()

    def test_idempotent(self, db_path):
        init_db(db_path)
        init_db(db_path)  # should not raise


class TestInsertAnalysis:
    def test_insert_and_retrieve(self, db_path):
        init_db(db_path)
        insert_analysis(db_path, {
            "ticker": "AAPL",
            "company_name": "Apple Inc.",
            "sector": "Technology",
            "recommendation": "BUY",
            "confidence_score": 72,
            "data_completeness": 100,
            "earnings_quality": 75,
            "valuation_clarity": 65,
            "company_predictability": 78,
            "insider_signal": 45,
            "macro_conditions": 60,
            "price_at_analysis": 178.50,
            "spy_price_at_analysis": 510.20,
            "analysis_date": "2026-03-28",
            "analysis_cost": 0.18,
        })
        rows = get_all_analyses(db_path)
        assert len(rows) == 1
        assert rows[0]["ticker"] == "AAPL"
        assert rows[0]["recommendation"] == "BUY"
        assert rows[0]["confidence_score"] == 72


class TestInsertSnapshot:
    def test_insert_and_retrieve(self, db_path):
        init_db(db_path)
        insert_snapshot(db_path, {
            "ticker": "AAPL",
            "price": 185.00,
            "spy_price": 520.00,
            "snapshot_date": "2026-06-28",
            "quarter": 1,
        })
        rows = get_snapshots(db_path, "AAPL")
        assert len(rows) == 1
        assert rows[0]["price"] == 185.00
        assert rows[0]["quarter"] == 1


class TestGetTickers:
    def test_returns_unique_tickers(self, db_path):
        init_db(db_path)
        for ticker in ["AAPL", "MSFT", "GOOGL"]:
            insert_analysis(db_path, {
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
        tickers = get_tickers(db_path)
        assert set(tickers) == {"AAPL", "MSFT", "GOOGL"}
