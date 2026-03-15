"""Tests for FRED data source — unit tests with mocked fredapi."""
import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from datetime import datetime

import pandas as pd

from src.data_sources.fred import get_macro_context


# --- Fixtures ---


def _mock_fred_client():
    """Create a mocked fredapi.Fred with realistic data."""
    mock_fred = MagicMock()

    def get_series(series_id, **kwargs):
        data = {
            "FEDFUNDS": pd.Series([5.33, 5.33, 5.33], index=pd.to_datetime(["2024-10-01", "2024-11-01", "2024-12-01"])),
            "GDPC1": pd.Series([22_225.4, 22_490.7], index=pd.to_datetime(["2024-04-01", "2024-07-01"])),
            "UNRATE": pd.Series([3.7, 3.8, 4.0], index=pd.to_datetime(["2024-10-01", "2024-11-01", "2024-12-01"])),
            "CPIAUCSL": pd.Series([310.0, 315.0], index=pd.to_datetime(["2023-12-01", "2024-12-01"])),
            "T10Y2Y": pd.Series([0.15, 0.20], index=pd.to_datetime(["2024-11-01", "2024-12-01"])),
        }
        if series_id in data:
            return data[series_id]
        raise ValueError(f"Unknown series: {series_id}")

    mock_fred.get_series = MagicMock(side_effect=get_series)
    return mock_fred


# --- Tests ---


class TestGetMacroContext:
    @patch("src.data_sources.fred.Fred")
    def test_returns_all_indicators(self, mock_fred_cls):
        mock_fred_cls.return_value = _mock_fred_client()
        result, warnings = get_macro_context()
        assert result["fed_funds_rate"] == 5.33
        assert result["unemployment_rate"] == 4.0
        assert "yield_spread" in result
        assert len(warnings) == 0

    @patch("src.data_sources.fred.Fred")
    def test_computes_cpi_yoy(self, mock_fred_cls):
        mock_fred_cls.return_value = _mock_fred_client()
        result, warnings = get_macro_context()
        # CPI YoY: (315 - 310) / 310 * 100 ≈ 1.61%
        assert result["cpi_yoy"] is not None
        assert abs(result["cpi_yoy"] - 1.61) < 0.1

    @patch("src.data_sources.fred.Fred")
    def test_computes_gdp_growth(self, mock_fred_cls):
        mock_fred_cls.return_value = _mock_fred_client()
        result, warnings = get_macro_context()
        # GDP growth: (22490.7 - 22225.4) / 22225.4 * 100 ≈ 1.19%
        assert result["gdp_growth"] is not None
        assert result["gdp_growth"] > 0

    @patch("src.data_sources.fred.Fred")
    def test_handles_missing_api_key(self, mock_fred_cls):
        mock_fred_cls.side_effect = ValueError("FRED API key required")
        result, warnings = get_macro_context()
        assert result == {}
        assert len(warnings) > 0

    @patch("src.data_sources.fred.Fred")
    def test_handles_partial_failure(self, mock_fred_cls):
        mock_fred = MagicMock()

        call_count = 0

        def partial_get_series(series_id, **kwargs):
            if series_id == "FEDFUNDS":
                return pd.Series([5.33], index=pd.to_datetime(["2024-12-01"]))
            if series_id == "UNRATE":
                return pd.Series([4.0], index=pd.to_datetime(["2024-12-01"]))
            raise Exception(f"Series {series_id} unavailable")

        mock_fred.get_series = MagicMock(side_effect=partial_get_series)
        mock_fred_cls.return_value = mock_fred

        result, warnings = get_macro_context()
        # Should still return what it can
        assert result["fed_funds_rate"] == 5.33
        assert result["unemployment_rate"] == 4.0
        assert len(warnings) > 0  # Should warn about failed series

    @patch("src.data_sources.fred.Fred")
    def test_handles_empty_series(self, mock_fred_cls):
        mock_fred = MagicMock()
        mock_fred.get_series.return_value = pd.Series([], dtype=float)
        mock_fred_cls.return_value = mock_fred

        result, warnings = get_macro_context()
        assert len(warnings) > 0

    @patch("src.data_sources.fred.Fred")
    def test_includes_as_of_date(self, mock_fred_cls):
        mock_fred_cls.return_value = _mock_fred_client()
        result, warnings = get_macro_context()
        assert "as_of_date" in result
        assert result["as_of_date"] != ""


# --- Integration Tests ---


@pytest.mark.integration
class TestFredIntegration:
    """Integration tests that hit real FRED API. Run with: pytest -m integration
    Requires FRED_API_KEY environment variable."""

    def test_fetches_macro_context(self):
        result, warnings = get_macro_context()
        # If FRED_API_KEY is set, we should get data
        if not result:
            pytest.skip("FRED_API_KEY not configured")
        assert result.get("fed_funds_rate") is not None
        assert result.get("unemployment_rate") is not None
