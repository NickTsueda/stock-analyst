"""Experiment database — SQLite schema and query helpers.

All SQL lives here. Other experiment modules call these functions.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

DEFAULT_DB_PATH = str(Path(__file__).resolve().parent.parent.parent / "data" / "experiment.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    company_name TEXT,
    sector TEXT,
    recommendation TEXT NOT NULL,
    confidence_score INTEGER,
    data_completeness INTEGER,
    earnings_quality INTEGER,
    valuation_clarity INTEGER,
    company_predictability INTEGER,
    insider_signal INTEGER,
    macro_conditions INTEGER,
    price_at_analysis REAL,
    spy_price_at_analysis REAL,
    analysis_date TEXT,
    analysis_cost REAL
);

CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    price REAL,
    spy_price REAL,
    snapshot_date TEXT,
    quarter INTEGER
);
"""


def init_db(db_path: str = DEFAULT_DB_PATH) -> None:
    """Create tables if they don't exist. Idempotent."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(_SCHEMA)
    finally:
        conn.close()


def insert_analysis(db_path: str, row: dict) -> None:
    """Insert a single analysis row."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """INSERT INTO analyses
            (ticker, company_name, sector, recommendation, confidence_score,
             data_completeness, earnings_quality, valuation_clarity,
             company_predictability, insider_signal, macro_conditions,
             price_at_analysis, spy_price_at_analysis, analysis_date, analysis_cost)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                row["ticker"], row["company_name"], row["sector"],
                row["recommendation"], row["confidence_score"],
                row["data_completeness"], row["earnings_quality"],
                row["valuation_clarity"], row["company_predictability"],
                row["insider_signal"], row["macro_conditions"],
                row["price_at_analysis"], row["spy_price_at_analysis"],
                row["analysis_date"], row["analysis_cost"],
            ),
        )
        conn.commit()
    finally:
        conn.close()


def insert_snapshot(db_path: str, row: dict) -> None:
    """Insert a single price snapshot row."""
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            """INSERT INTO snapshots (ticker, price, spy_price, snapshot_date, quarter)
            VALUES (?, ?, ?, ?, ?)""",
            (row["ticker"], row["price"], row["spy_price"],
             row["snapshot_date"], row["quarter"]),
        )
        conn.commit()
    finally:
        conn.close()


def get_all_analyses(db_path: str) -> list[dict]:
    """Return all analysis rows as dicts."""
    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM analyses ORDER BY ticker").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_snapshots(db_path: str, ticker: str | None = None) -> list[dict]:
    """Return snapshot rows, optionally filtered by ticker."""
    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        if ticker:
            rows = conn.execute(
                "SELECT * FROM snapshots WHERE ticker = ? ORDER BY quarter",
                (ticker,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM snapshots ORDER BY ticker, quarter"
            ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_tickers(db_path: str) -> list[str]:
    """Return list of unique tickers from the analyses table."""
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT DISTINCT ticker FROM analyses ORDER BY ticker"
        ).fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()
