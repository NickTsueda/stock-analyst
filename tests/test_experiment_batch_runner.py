"""Tests for experiment batch runner."""
from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock, patch
from datetime import date

import pytest

from src.experiment.batch_runner import run_batch, extract_analysis_row
from src.experiment.db import init_db, get_all_analyses
from src.models import (
    Recommendation,
    ConfidenceLevel,
    ConfidenceScore,
    ConfidenceDriver,
)
from tests.conftest import make_sample_data_package


@pytest.fixture
def db_path():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    init_db(path)
    yield path
    os.unlink(path)


def _make_mock_thesis():
    """Minimal InvestmentThesis mock with the fields batch_runner needs."""
    thesis = MagicMock()
    thesis.recommendation = Recommendation.BUY
    thesis.confidence = ConfidenceScore(
        score=72,
        level=ConfidenceLevel.HIGH,
        summary="High confidence",
        drivers=[
            ConfidenceDriver("Data Completeness", 100, 0.20, "positive", "All data"),
            ConfidenceDriver("Earnings Quality", 75, 0.25, "positive", "Solid"),
            ConfidenceDriver("Valuation Clarity", 65, 0.20, "positive", "Clear"),
            ConfidenceDriver("Company Predictability", 78, 0.20, "positive", "Stable"),
            ConfidenceDriver("Insider Signal", 45, 0.10, "negative", "Selling"),
            ConfidenceDriver("Macro Conditions", 60, 0.05, "neutral", "Mixed"),
        ],
    )
    return thesis


class TestExtractAnalysisRow:
    def test_extracts_all_fields(self):
        data = make_sample_data_package()
        thesis = _make_mock_thesis()
        row = extract_analysis_row(data, thesis, spy_price=510.20)
        assert row["ticker"] == "AAPL"
        assert row["recommendation"] == "BUY"
        assert row["confidence_score"] == 72
        assert row["price_at_analysis"] == 178.50
        assert row["spy_price_at_analysis"] == 510.20
        assert row["data_completeness"] == 100
        assert row["earnings_quality"] == 75

    def test_handles_none_thesis(self):
        data = make_sample_data_package()
        row = extract_analysis_row(data, None, spy_price=510.20)
        assert row["recommendation"] == "INCOMPLETE"
        assert row["confidence_score"] == 0


class TestRunBatch:
    @patch("src.experiment.batch_runner.OrchestratorAgent")
    @patch("src.experiment.batch_runner.yf.Ticker")
    def test_stores_results_in_db(self, mock_yf_ticker, mock_orch_cls, db_path):
        spy_mock = MagicMock()
        spy_mock.info = {"regularMarketPrice": 510.20}
        mock_yf_ticker.return_value = spy_mock

        data = make_sample_data_package()
        thesis = _make_mock_thesis()
        mock_orch = MagicMock()
        mock_orch.run.return_value = (data, MagicMock(), thesis)
        mock_orch_cls.return_value = mock_orch

        run_batch(["AAPL"], db_path=db_path)

        rows = get_all_analyses(db_path)
        assert len(rows) == 1
        assert rows[0]["ticker"] == "AAPL"

    @patch("src.experiment.batch_runner.OrchestratorAgent")
    @patch("src.experiment.batch_runner.yf.Ticker")
    def test_skips_failed_ticker(self, mock_yf_ticker, mock_orch_cls, db_path):
        spy_mock = MagicMock()
        spy_mock.info = {"regularMarketPrice": 510.20}
        mock_yf_ticker.return_value = spy_mock

        mock_orch = MagicMock()
        mock_orch.run.side_effect = Exception("API error")
        mock_orch_cls.return_value = mock_orch

        run_batch(["AAPL"], db_path=db_path)

        rows = get_all_analyses(db_path)
        assert len(rows) == 0
