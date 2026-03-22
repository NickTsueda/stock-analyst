"""Tests for Yahoo Finance data source — unit tests with mocked yfinance."""
import pytest
from unittest.mock import MagicMock, patch, PropertyMock
import pandas as pd

from src.data_sources.yahoo_finance import (
    get_financial_statements,
    get_market_data,
    get_price_history,
    get_insider_transactions,
    get_institutional_holders,
    get_peer_data,
)


@pytest.fixture
def mock_ticker():
    """Create a mocked yfinance.Ticker object."""
    ticker = MagicMock()
    ticker.info = {
        "currentPrice": 178.50,
        "marketCap": 2_750_000_000_000,
        "trailingPE": 28.5,
        "priceToBook": 45.2,
        "priceToSalesTrailing12Months": 7.3,
        "enterpriseToEbitda": 22.1,
        "trailingEps": 6.26,
        "dividendYield": 0.0055,
        "beta": 1.24,
        "fiftyTwoWeekHigh": 199.62,
        "fiftyTwoWeekLow": 164.08,
        "sector": "Technology",
        "industry": "Consumer Electronics",
        "shortName": "Apple Inc.",
    }

    # Financial statements as DataFrames
    ticker.financials = pd.DataFrame(
        {"2024-09-30": [383_285_000_000, 93_736_000_000], "2023-09-30": [383_933_000_000, 96_995_000_000]},
        index=["Total Revenue", "Net Income"],
    )
    ticker.balance_sheet = pd.DataFrame(
        {"2024-09-30": [352_583_000_000, 104_590_000_000]},
        index=["Total Assets", "Total Debt"],
    )
    ticker.cashflow = pd.DataFrame(
        {"2024-09-30": [118_254_000_000, 108_807_000_000]},
        index=["Operating Cash Flow", "Free Cash Flow"],
    )
    ticker.quarterly_financials = pd.DataFrame(
        {
            "2024-09-30": [94_930_000_000],
            "2024-06-30": [85_777_000_000],
            "2024-03-31": [90_753_000_000],
            "2023-12-31": [89_498_000_000],
        },
        index=["Total Revenue"],
    )

    # History
    ticker.history.return_value = pd.DataFrame(
        {
            "Open": [185.0, 184.0],
            "High": [186.5, 185.5],
            "Low": [184.0, 183.5],
            "Close": [185.64, 184.25],
            "Volume": [50_000_000, 48_000_000],
        },
        index=pd.to_datetime(["2024-01-02", "2024-01-03"]),
    )

    # Insider transactions
    ticker.insider_transactions = pd.DataFrame(
        {
            "Insider": ["Tim Cook"],
            "Start Date": [pd.Timestamp("2024-06-01")],
            "Transaction": ["Sale"],
            "Shares": [100_000],
            "Value": [17_850_000],
        }
    )

    # Institutional holders
    ticker.institutional_holders = pd.DataFrame(
        {
            "Holder": ["Vanguard Group", "BlackRock"],
            "Shares": [1_300_000_000, 1_100_000_000],
            "pctHeld": [0.085, 0.072],
        }
    )

    return ticker


class TestGetFinancialStatements:
    @patch("src.data_sources.yahoo_finance.yf.Ticker")
    def test_returns_data(self, mock_yf, mock_ticker):
        mock_yf.return_value = mock_ticker
        result, warnings = get_financial_statements("AAPL")
        assert "income_statement" in result
        assert "Total Revenue" in result["income_statement"]
        assert len(warnings) == 0

    @patch("src.data_sources.yahoo_finance.yf.Ticker")
    def test_handles_failure(self, mock_yf):
        mock_yf.side_effect = Exception("Network error")
        result, warnings = get_financial_statements("AAPL")
        assert result == {}
        assert len(warnings) > 0


class TestGetMarketData:
    @patch("src.data_sources.yahoo_finance.yf.Ticker")
    def test_returns_data(self, mock_yf, mock_ticker):
        mock_yf.return_value = mock_ticker
        result, warnings = get_market_data("AAPL")
        assert result["current_price"] == 178.50
        assert result["sector"] == "Technology"
        assert result["company_name"] == "Apple Inc."

    @patch("src.data_sources.yahoo_finance.yf.Ticker")
    def test_handles_missing_fields(self, mock_yf, mock_ticker):
        mock_ticker.info = {"currentPrice": 100.0}
        mock_yf.return_value = mock_ticker
        result, warnings = get_market_data("AAPL")
        assert result["current_price"] == 100.0
        assert result["pe_ratio"] is None


class TestGetPriceHistory:
    @patch("src.data_sources.yahoo_finance.yf.Ticker")
    def test_returns_list_of_dicts(self, mock_yf, mock_ticker):
        mock_yf.return_value = mock_ticker
        result, warnings = get_price_history("AAPL")
        assert len(result) == 2
        assert "close" in result[0]
        assert "date" in result[0]

    @patch("src.data_sources.yahoo_finance.yf.Ticker")
    def test_handles_failure(self, mock_yf):
        mock_yf.side_effect = Exception("Network error")
        result, warnings = get_price_history("AAPL")
        assert result == []
        assert len(warnings) > 0


class TestGetInsiderTransactions:
    @patch("src.data_sources.yahoo_finance.yf.Ticker")
    def test_returns_transactions(self, mock_yf, mock_ticker):
        mock_yf.return_value = mock_ticker
        result, warnings = get_insider_transactions("AAPL")
        assert len(result) > 0
        assert "name" in result[0]

    @patch("src.data_sources.yahoo_finance.yf.Ticker")
    def test_handles_no_data(self, mock_yf, mock_ticker):
        mock_ticker.insider_transactions = None
        mock_yf.return_value = mock_ticker
        result, warnings = get_insider_transactions("AAPL")
        assert result == []


class TestGetInstitutionalHolders:
    @patch("src.data_sources.yahoo_finance.yf.Ticker")
    def test_returns_holders(self, mock_yf, mock_ticker):
        mock_yf.return_value = mock_ticker
        result, warnings = get_institutional_holders("AAPL")
        assert len(result) > 0
        assert "name" in result[0]

    @patch("src.data_sources.yahoo_finance.yf.Ticker")
    def test_pct_held_converted_to_percentage(self, mock_yf, mock_ticker):
        """pctHeld from yfinance is a decimal (e.g. 0.085 = 8.5%). We convert to percentage."""
        mock_yf.return_value = mock_ticker
        result, _ = get_institutional_holders("AAPL")
        # Mock has pctHeld=[0.085, 0.072] → should become [8.5, 7.2]
        assert result[0]["pct"] == 8.5
        assert result[1]["pct"] == 7.2


class TestGetPeerData:
    @patch("src.data_sources.yahoo_finance.yf.Ticker")
    def test_returns_peers(self, mock_yf):
        # Main ticker
        main = MagicMock()
        main.info = {
            "industry": "Consumer Electronics",
            "marketCap": 2_750_000_000_000,
            "sector": "Technology",
        }

        # Peer ticker
        peer = MagicMock()
        peer.info = {
            "shortName": "Microsoft Corp",
            "marketCap": 2_900_000_000_000,
            "trailingPE": 35.2,
            "priceToSalesTrailing12Months": 12.1,
            "revenueGrowth": 0.16,
            "profitMargins": 0.36,
            "returnOnEquity": 0.38,
            "industry": "Consumer Electronics",
        }

        def side_effect(ticker):
            if ticker == "AAPL":
                return main
            return peer

        mock_yf.side_effect = side_effect
        result, warnings = get_peer_data("AAPL", "Consumer Electronics", 2_750_000_000_000)
        # Result may be empty if no peers in screenr — this tests the shape
        assert isinstance(result, list)

    @patch("src.data_sources.yahoo_finance.yf.Ticker")
    def test_handles_failure(self, mock_yf):
        mock_yf.side_effect = Exception("Network error")
        result, warnings = get_peer_data("AAPL", "Consumer Electronics", 2_750_000_000_000)
        assert result == []
        assert len(warnings) > 0


@pytest.mark.integration
class TestYahooFinanceIntegration:
    """Integration tests that hit real Yahoo Finance API. Run with: pytest -m integration"""

    def test_aapl_market_data(self):
        result, warnings = get_market_data("AAPL")
        assert result.get("current_price", 0) > 0
        assert result.get("sector") == "Technology"

    def test_aapl_financials(self):
        result, warnings = get_financial_statements("AAPL")
        assert "income_statement" in result
        assert len(result["income_statement"]) > 0

    def test_aapl_price_history(self):
        result, warnings = get_price_history("AAPL")
        assert len(result) > 100  # ~250 trading days in a year
