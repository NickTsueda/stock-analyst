"""Tests for the Data Collector agent — data fetching and DataPackage assembly."""
from unittest.mock import patch, MagicMock

import pytest

from src.agents.data_collector import DataCollectorAgent
from src.models import DataPackage, LimitationNote


# --- Realistic stub data matching data source return formats ---

STUB_MARKET_DATA = {
    "current_price": 178.50,
    "market_cap": 2_750_000_000_000,
    "pe_ratio": 28.5,
    "pb_ratio": 45.2,
    "ps_ratio": 7.3,
    "ev_ebitda": 22.1,
    "eps": 6.26,
    "dividend_yield": 0.55,
    "beta": 1.24,
    "fifty_two_week_high": 199.62,
    "fifty_two_week_low": 164.08,
    "sector": "Technology",
    "industry": "Consumer Electronics",
    "company_name": "Apple Inc.",
    "held_pct_institutions": 0.6526,
}

STUB_FINANCIALS = {
    "income_statement": {"Revenue": {"2024": 383_285_000_000}},
    "balance_sheet": {"Total Assets": {"2024": 352_583_000_000}},
    "cash_flow": {"Operating Cash Flow": {"2024": 118_254_000_000}},
    "quarterly_revenue": [94_930, 90_753, 85_777, 89_498, 94_836, 90_146, 81_797, 83_083],
}

STUB_PRICE_HISTORY = [
    {"date": "2024-01-02", "close": 185.64},
    {"date": "2024-01-03", "close": 184.25},
]

STUB_INSIDER_TXNS_YF = [
    {"name": "Tim Cook", "date": "2024-06-01", "type": "Sale", "shares": 100_000, "value": 19_500_000},
]

STUB_INSTITUTIONAL = [
    {"name": "Vanguard Group", "shares": 1_300_000_000, "pct": 8.5},
]

STUB_PEER_DATA = [
    {"ticker": "MSFT", "name": "Microsoft", "market_cap": 2_900_000_000_000,
     "pe_ratio": 35.2, "ps_ratio": 12.1, "revenue_growth": 0.16, "profit_margin": 0.36, "roe": 0.38},
]

STUB_CIK = "0000320193"

STUB_XBRL_FACTS = {
    "Revenues": [{"val": 383_285_000_000, "end": "2024-09-28", "fy": 2024, "fp": "FY"}],
    "RevenueFromContractWithCustomerExcludingAssessedTax": [
        {"val": 94_930_000_000, "end": "2024-12-28", "frame": "CY2024Q4"},
        {"val": 90_753_000_000, "end": "2024-09-28", "frame": "CY2024Q3"},
        {"val": 85_777_000_000, "end": "2024-06-29", "frame": "CY2024Q2"},
        {"val": 89_498_000_000, "end": "2024-03-30", "frame": "CY2024Q1"},
        {"val": 94_836_000_000, "end": "2023-12-30", "frame": "CY2023Q4"},
        {"val": 90_146_000_000, "end": "2023-09-30", "frame": "CY2023Q3"},
        {"val": 81_797_000_000, "end": "2023-07-01", "frame": "CY2023Q2"},
        {"val": 83_083_000_000, "end": "2023-04-01", "frame": "CY2023Q1"},
        {"val": 117_154_000_000, "end": "2022-12-31", "frame": "CY2022Q4"},
        {"val": 82_959_000_000, "end": "2022-07-02", "frame": "CY2022Q2"},
        # Annual entry (no Q in frame) — should be filtered out
        {"val": 383_285_000_000, "end": "2024-09-28", "frame": "CY2024"},
    ],
    "NetIncomeLoss": [{"val": 93_736_000_000, "end": "2024-09-28", "fy": 2024, "fp": "FY"}],
}

STUB_FILINGS = [
    {"accession_number": "0000320193-24-000123", "filing_date": "2024-11-01",
     "form": "10-K", "primary_document": "aapl-20240928.htm",
     "filing_url": "https://www.sec.gov/Archives/edgar/data/320193/000032019324000123/aapl-20240928.htm"},
]

STUB_FILING_TEXT = {
    "mda_text": "Management discussion and analysis text...",
    "risk_factors_text": "Risk factors text...",
}

STUB_EDGAR_INSIDER_TXNS = [
    {"name": "Tim Cook", "date": "2024-06-01", "shares": 100_000,
     "price": 195.0, "acquired_or_disposed": "D"},
]

STUB_MACRO = {
    "fed_funds_rate": 5.33,
    "gdp_growth": 2.8,
    "unemployment_rate": 3.7,
    "cpi_yoy": 3.1,
    "yield_spread": 0.15,
    "as_of_date": "2024-12-01",
}


def _patch_all_sources():
    """Return a dict of patch context managers for all data source functions."""
    return {
        "market_data": patch("src.agents.data_collector.yf.get_market_data", side_effect=lambda *a, **k: (dict(STUB_MARKET_DATA), [])),
        "financials": patch("src.agents.data_collector.yf.get_financial_statements", return_value=(STUB_FINANCIALS, [])),
        "price_history": patch("src.agents.data_collector.yf.get_price_history", return_value=(STUB_PRICE_HISTORY, [])),
        "insider_yf": patch("src.agents.data_collector.yf.get_insider_transactions", return_value=(STUB_INSIDER_TXNS_YF, [])),
        "institutional": patch("src.agents.data_collector.yf.get_institutional_holders", return_value=(STUB_INSTITUTIONAL, [])),
        "peers": patch("src.agents.data_collector.yf.get_peer_data", return_value=(STUB_PEER_DATA, [])),
        "cik": patch("src.agents.data_collector.edgar.get_cik_from_ticker", return_value=(STUB_CIK, [])),
        "xbrl": patch("src.agents.data_collector.edgar.get_financial_facts", return_value=(STUB_XBRL_FACTS, [])),
        "filings": patch("src.agents.data_collector.edgar.get_recent_filings", return_value=(STUB_FILINGS, [])),
        "filing_text": patch("src.agents.data_collector.edgar.get_filing_text", return_value=(STUB_FILING_TEXT, [])),
        "insider_edgar": patch("src.agents.data_collector.edgar.get_insider_transactions", return_value=(STUB_EDGAR_INSIDER_TXNS, [])),
        "macro": patch("src.agents.data_collector.fred.get_macro_context", return_value=(STUB_MACRO, [])),
    }


class TestDataCollectorHappyPath:
    """Test successful data collection with all sources available."""

    def test_returns_data_package(self):
        patches = _patch_all_sources()
        with patches["market_data"], patches["financials"], patches["price_history"], \
             patches["insider_yf"], patches["institutional"], patches["peers"], \
             patches["cik"], patches["xbrl"], patches["filings"], \
             patches["filing_text"], patches["insider_edgar"], patches["macro"]:

            agent = DataCollectorAgent()
            result = agent.run("AAPL")

            assert isinstance(result, DataPackage)
            assert result.ticker == "AAPL"
            assert result.company_name == "Apple Inc."

    def test_populates_market_data(self):
        patches = _patch_all_sources()
        with patches["market_data"], patches["financials"], patches["price_history"], \
             patches["insider_yf"], patches["institutional"], patches["peers"], \
             patches["cik"], patches["xbrl"], patches["filings"], \
             patches["filing_text"], patches["insider_edgar"], patches["macro"]:

            result = DataCollectorAgent().run("AAPL")

            assert result.market_data is not None
            assert result.market_data.current_price == 178.50
            assert result.market_data.sector == "Technology"

    def test_populates_financials(self):
        patches = _patch_all_sources()
        with patches["market_data"], patches["financials"], patches["price_history"], \
             patches["insider_yf"], patches["institutional"], patches["peers"], \
             patches["cik"], patches["xbrl"], patches["filings"], \
             patches["filing_text"], patches["insider_edgar"], patches["macro"]:

            result = DataCollectorAgent().run("AAPL")

            assert result.financials is not None
            assert result.financials.quarterly_revenue == STUB_FINANCIALS["quarterly_revenue"]

    def test_populates_macro(self):
        patches = _patch_all_sources()
        with patches["market_data"], patches["financials"], patches["price_history"], \
             patches["insider_yf"], patches["institutional"], patches["peers"], \
             patches["cik"], patches["xbrl"], patches["filings"], \
             patches["filing_text"], patches["insider_edgar"], patches["macro"]:

            result = DataCollectorAgent().run("AAPL")

            assert result.macro is not None
            assert result.macro.fed_funds_rate == 5.33

    def test_prefers_edgar_insider_data(self):
        """EDGAR is the primary source for insider data per design doc."""
        patches = _patch_all_sources()
        with patches["market_data"], patches["financials"], patches["price_history"], \
             patches["insider_yf"], patches["institutional"], patches["peers"], \
             patches["cik"], patches["xbrl"], patches["filings"], \
             patches["filing_text"], patches["insider_edgar"], patches["macro"]:

            result = DataCollectorAgent().run("AAPL")

            assert result.insider_activity is not None
            assert result.insider_activity.source == "edgar"

    def test_data_completeness_score_all_sources(self):
        """All sources available → score = 100."""
        patches = _patch_all_sources()
        with patches["market_data"], patches["financials"], patches["price_history"], \
             patches["insider_yf"], patches["institutional"], patches["peers"], \
             patches["cik"], patches["xbrl"], patches["filings"], \
             patches["filing_text"], patches["insider_edgar"], patches["macro"]:

            result = DataCollectorAgent().run("AAPL")
            assert result.data_completeness_score == 100

    def test_populates_peers(self):
        patches = _patch_all_sources()
        with patches["market_data"], patches["financials"], patches["price_history"], \
             patches["insider_yf"], patches["institutional"], patches["peers"], \
             patches["cik"], patches["xbrl"], patches["filings"], \
             patches["filing_text"], patches["insider_edgar"], patches["macro"]:

            result = DataCollectorAgent().run("AAPL")

            assert result.peers is not None
            assert len(result.peers) == 1
            assert result.peers[0].ticker == "MSFT"

    def test_populates_filing_text(self):
        patches = _patch_all_sources()
        with patches["market_data"], patches["financials"], patches["price_history"], \
             patches["insider_yf"], patches["institutional"], patches["peers"], \
             patches["cik"], patches["xbrl"], patches["filings"], \
             patches["filing_text"], patches["insider_edgar"], patches["macro"]:

            result = DataCollectorAgent().run("AAPL")

            assert result.filing_text is not None
            assert "Management discussion" in result.filing_text.mda_text

    def test_institutional_ownership_uses_info_total(self):
        """institutional_ownership_pct uses heldPercentInstitutions from info, not top-10 sum."""
        patches = _patch_all_sources()
        with patches["market_data"], patches["financials"], patches["price_history"], \
             patches["insider_yf"], patches["institutional"], patches["peers"], \
             patches["cik"], patches["xbrl"], patches["filings"], \
             patches["filing_text"], patches["insider_edgar"], patches["macro"]:

            result = DataCollectorAgent().run("AAPL")

            assert result.institutional is not None
            # STUB_MARKET_DATA has held_pct_institutions=0.6526 → 65.26%
            assert result.institutional.institutional_ownership_pct == 65.26

    def test_institutional_ownership_falls_back_to_sum(self):
        """If heldPercentInstitutions is missing, falls back to summing top holders."""
        patches = _patch_all_sources()
        # Override market data to not include held_pct_institutions
        market_data_no_inst = {k: v for k, v in STUB_MARKET_DATA.items() if k != "held_pct_institutions"}
        patches["market_data"] = patch(
            "src.agents.data_collector.yf.get_market_data",
            return_value=(market_data_no_inst, []),
        )
        with patches["market_data"], patches["financials"], patches["price_history"], \
             patches["insider_yf"], patches["institutional"], patches["peers"], \
             patches["cik"], patches["xbrl"], patches["filings"], \
             patches["filing_text"], patches["insider_edgar"], patches["macro"]:

            result = DataCollectorAgent().run("AAPL")

            assert result.institutional is not None
            # STUB_INSTITUTIONAL has one holder with pct=8.5
            assert result.institutional.institutional_ownership_pct == 8.5


class TestDataCollectorGracefulDegradation:
    """Test handling of partial failures."""

    def test_yfinance_failure_still_returns_package(self):
        """If yfinance fails entirely, we still get EDGAR + FRED data."""
        patches = _patch_all_sources()
        # Override yfinance functions to fail
        patches["market_data"] = patch("src.agents.data_collector.yf.get_market_data", return_value=({}, ["yfinance failed"]))
        patches["financials"] = patch("src.agents.data_collector.yf.get_financial_statements", return_value=({}, ["yfinance failed"]))
        patches["price_history"] = patch("src.agents.data_collector.yf.get_price_history", return_value=([], ["yfinance failed"]))
        patches["insider_yf"] = patch("src.agents.data_collector.yf.get_insider_transactions", return_value=([], []))
        patches["institutional"] = patch("src.agents.data_collector.yf.get_institutional_holders", return_value=([], []))
        patches["peers"] = patch("src.agents.data_collector.yf.get_peer_data", return_value=([], []))

        with patches["market_data"], patches["financials"], patches["price_history"], \
             patches["insider_yf"], patches["institutional"], patches["peers"], \
             patches["cik"], patches["xbrl"], patches["filings"], \
             patches["filing_text"], patches["insider_edgar"], patches["macro"]:

            result = DataCollectorAgent().run("AAPL")

            assert isinstance(result, DataPackage)
            assert result.market_data is None
            # EDGAR + FRED still work
            assert result.macro is not None
            assert result.filing_text is not None
            # Score reflects missing yfinance
            assert result.data_completeness_score == 60  # EDGAR 35 + FRED 25

    def test_edgar_failure_still_returns_package(self):
        """If EDGAR fails, we still get yfinance + FRED data."""
        patches = _patch_all_sources()
        patches["cik"] = patch("src.agents.data_collector.edgar.get_cik_from_ticker", return_value=("", ["CIK not found"]))

        with patches["market_data"], patches["financials"], patches["price_history"], \
             patches["insider_yf"], patches["institutional"], patches["peers"], \
             patches["cik"], patches["xbrl"], patches["filings"], \
             patches["filing_text"], patches["insider_edgar"], patches["macro"]:

            result = DataCollectorAgent().run("AAPL")

            assert result.market_data is not None
            assert result.financials is not None  # yfinance financials still present
            assert result.filing_text is None
            # yfinance financials count for the EDGAR points too (financials is not None)
            # Score: yfinance 40 + EDGAR 35 (financials present from yfinance) + FRED 25 = 100
            assert result.data_completeness_score == 100
            # But we should see a warning about EDGAR being unavailable
            warning_msgs = [w.message for w in result.warnings]
            assert any("CIK not found" in m for m in warning_msgs)

    def test_fred_failure_still_returns_package(self):
        """If FRED fails, analysis proceeds without macro data."""
        patches = _patch_all_sources()
        patches["macro"] = patch("src.agents.data_collector.fred.get_macro_context", return_value=({}, ["FRED unavailable"]))

        with patches["market_data"], patches["financials"], patches["price_history"], \
             patches["insider_yf"], patches["institutional"], patches["peers"], \
             patches["cik"], patches["xbrl"], patches["filings"], \
             patches["filing_text"], patches["insider_edgar"], patches["macro"]:

            result = DataCollectorAgent().run("AAPL")

            assert result.macro is None
            assert result.market_data is not None
            assert result.data_completeness_score == 75  # yfinance 40 + EDGAR 35

    def test_all_sources_fail(self):
        """Total failure returns empty DataPackage with warnings."""
        with patch("src.agents.data_collector.yf.get_market_data", return_value=({}, ["failed"])), \
             patch("src.agents.data_collector.yf.get_financial_statements", return_value=({}, ["failed"])), \
             patch("src.agents.data_collector.yf.get_price_history", return_value=([], ["failed"])), \
             patch("src.agents.data_collector.yf.get_insider_transactions", return_value=([], [])), \
             patch("src.agents.data_collector.yf.get_institutional_holders", return_value=([], [])), \
             patch("src.agents.data_collector.yf.get_peer_data", return_value=([], [])), \
             patch("src.agents.data_collector.edgar.get_cik_from_ticker", return_value=("", ["failed"])), \
             patch("src.agents.data_collector.fred.get_macro_context", return_value=({}, ["failed"])):

            result = DataCollectorAgent().run("AAPL")

            assert isinstance(result, DataPackage)
            assert result.data_completeness_score == 0
            assert len(result.warnings) > 0

    def test_warnings_propagated_from_sources(self):
        """Warnings from data sources are collected in DataPackage.warnings."""
        patches = _patch_all_sources()
        patches["market_data"] = patch(
            "src.agents.data_collector.yf.get_market_data",
            return_value=(STUB_MARKET_DATA, ["Minor yfinance warning"]),
        )

        with patches["market_data"], patches["financials"], patches["price_history"], \
             patches["insider_yf"], patches["institutional"], patches["peers"], \
             patches["cik"], patches["xbrl"], patches["filings"], \
             patches["filing_text"], patches["insider_edgar"], patches["macro"]:

            result = DataCollectorAgent().run("AAPL")

            warning_messages = [w.message for w in result.warnings]
            assert "Minor yfinance warning" in warning_messages


class TestCompanyPredictabilityScore:
    """Test the predictability score calculation from quarterly revenue CV."""

    def test_stable_revenue_high_score(self):
        """Low CV (< 0.05) → score 90-100."""
        # Very stable revenue: all values close to mean
        stable_revenue = [100_000, 100_500, 99_500, 100_200, 99_800, 100_100, 99_900, 100_300]
        patches = _patch_all_sources()
        financials = dict(STUB_FINANCIALS)
        financials["quarterly_revenue"] = stable_revenue
        patches["financials"] = patch(
            "src.agents.data_collector.yf.get_financial_statements",
            return_value=(financials, []),
        )
        # Clear XBRL revenue so yfinance values are used
        patches["xbrl"] = patch(
            "src.agents.data_collector.edgar.get_financial_facts",
            return_value=({"NetIncomeLoss": []}, []),
        )

        with patches["market_data"], patches["financials"], patches["price_history"], \
             patches["insider_yf"], patches["institutional"], patches["peers"], \
             patches["cik"], patches["xbrl"], patches["filings"], \
             patches["filing_text"], patches["insider_edgar"], patches["macro"]:

            result = DataCollectorAgent().run("AAPL")
            assert result.company_predictability_score >= 90

    def test_volatile_revenue_low_score(self):
        """High CV (> 0.50) → score 10-29."""
        volatile_revenue = [10_000, 200_000, 5_000, 180_000, 8_000, 150_000, 3_000, 250_000]
        patches = _patch_all_sources()
        financials = dict(STUB_FINANCIALS)
        financials["quarterly_revenue"] = volatile_revenue
        patches["financials"] = patch(
            "src.agents.data_collector.yf.get_financial_statements",
            return_value=(financials, []),
        )
        # Clear XBRL revenue so yfinance values are used
        patches["xbrl"] = patch(
            "src.agents.data_collector.edgar.get_financial_facts",
            return_value=({"NetIncomeLoss": []}, []),
        )

        with patches["market_data"], patches["financials"], patches["price_history"], \
             patches["insider_yf"], patches["institutional"], patches["peers"], \
             patches["cik"], patches["xbrl"], patches["filings"], \
             patches["filing_text"], patches["insider_edgar"], patches["macro"]:

            result = DataCollectorAgent().run("AAPL")
            assert result.company_predictability_score <= 29

    def test_insufficient_quarters_defaults_to_50(self):
        """Fewer than 8 quarters from both sources → default score of 50."""
        patches = _patch_all_sources()
        financials = dict(STUB_FINANCIALS)
        financials["quarterly_revenue"] = [100_000, 105_000, 98_000]  # Only 3 quarters
        patches["financials"] = patch(
            "src.agents.data_collector.yf.get_financial_statements",
            return_value=(financials, []),
        )
        # Clear XBRL revenue too
        patches["xbrl"] = patch(
            "src.agents.data_collector.edgar.get_financial_facts",
            return_value=({"NetIncomeLoss": []}, []),
        )

        with patches["market_data"], patches["financials"], patches["price_history"], \
             patches["insider_yf"], patches["institutional"], patches["peers"], \
             patches["cik"], patches["xbrl"], patches["filings"], \
             patches["filing_text"], patches["insider_edgar"], patches["macro"]:

            result = DataCollectorAgent().run("AAPL")
            assert result.company_predictability_score == 50

    def test_no_revenue_data_defaults_to_50(self):
        """No quarterly revenue data at all → default 50."""
        patches = _patch_all_sources()
        financials = dict(STUB_FINANCIALS)
        financials["quarterly_revenue"] = []
        patches["financials"] = patch(
            "src.agents.data_collector.yf.get_financial_statements",
            return_value=(financials, []),
        )
        # Also clear XBRL revenue data
        patches["xbrl"] = patch(
            "src.agents.data_collector.edgar.get_financial_facts",
            return_value=({"NetIncomeLoss": []}, []),
        )

        with patches["market_data"], patches["financials"], patches["price_history"], \
             patches["insider_yf"], patches["institutional"], patches["peers"], \
             patches["cik"], patches["xbrl"], patches["filings"], \
             patches["filing_text"], patches["insider_edgar"], patches["macro"]:

            result = DataCollectorAgent().run("AAPL")
            assert result.company_predictability_score == 50

    def test_xbrl_quarterly_revenue_used_for_predictability(self):
        """XBRL quarterly revenue (10+ quarters) should produce a real score, not default 50."""
        patches = _patch_all_sources()
        # yfinance only has 5 quarters (below threshold)
        financials = dict(STUB_FINANCIALS)
        financials["quarterly_revenue"] = [94_930, 90_753, 85_777, 89_498, 94_836]
        patches["financials"] = patch(
            "src.agents.data_collector.yf.get_financial_statements",
            return_value=(financials, []),
        )
        # XBRL has 10 quarterly entries via STUB_XBRL_FACTS (default)

        with patches["market_data"], patches["financials"], patches["price_history"], \
             patches["insider_yf"], patches["institutional"], patches["peers"], \
             patches["cik"], patches["xbrl"], patches["filings"], \
             patches["filing_text"], patches["insider_edgar"], patches["macro"]:

            result = DataCollectorAgent().run("AAPL")
            # AAPL has stable revenue — should score well above default 50
            assert result.company_predictability_score != 50
            assert result.company_predictability_score >= 70  # stable large-cap

    def test_xbrl_fallback_to_yfinance_when_no_xbrl_revenue(self):
        """When XBRL has no revenue concepts, use yfinance quarterly_revenue."""
        patches = _patch_all_sources()
        # yfinance has 8 stable quarters
        financials = dict(STUB_FINANCIALS)
        financials["quarterly_revenue"] = [100_000, 100_500, 99_500, 100_200, 99_800, 100_100, 99_900, 100_300]
        patches["financials"] = patch(
            "src.agents.data_collector.yf.get_financial_statements",
            return_value=(financials, []),
        )
        # XBRL has no revenue concepts
        patches["xbrl"] = patch(
            "src.agents.data_collector.edgar.get_financial_facts",
            return_value=({"NetIncomeLoss": []}, []),
        )

        with patches["market_data"], patches["financials"], patches["price_history"], \
             patches["insider_yf"], patches["institutional"], patches["peers"], \
             patches["cik"], patches["xbrl"], patches["filings"], \
             patches["filing_text"], patches["insider_edgar"], patches["macro"]:

            result = DataCollectorAgent().run("AAPL")
            assert result.company_predictability_score >= 90  # very stable


class TestInsiderDataSourcePriority:
    """Test that EDGAR is primary for insider data, yfinance is fallback."""

    def test_falls_back_to_yfinance_when_edgar_has_no_insider_data(self):
        """When EDGAR insider fetch returns empty, use yfinance insider data."""
        patches = _patch_all_sources()
        patches["insider_edgar"] = patch(
            "src.agents.data_collector.edgar.get_insider_transactions",
            return_value=([], []),
        )

        with patches["market_data"], patches["financials"], patches["price_history"], \
             patches["insider_yf"], patches["institutional"], patches["peers"], \
             patches["cik"], patches["xbrl"], patches["filings"], \
             patches["filing_text"], patches["insider_edgar"], patches["macro"]:

            result = DataCollectorAgent().run("AAPL")

            assert result.insider_activity is not None
            assert result.insider_activity.source == "yfinance"

    def test_edgar_net_buys_counts_mixed_transactions(self):
        """net_buys should be the delta: A=+1, D=-1, not total count."""
        patches = _patch_all_sources()
        mixed_txns = [
            {"name": "Cook", "date": "2024-06-01", "shares": 60000, "price": 0, "acquired_or_disposed": "A"},
            {"name": "Cook", "date": "2024-06-01", "shares": 30000, "price": 195.0, "acquired_or_disposed": "D"},
            {"name": "Cook", "date": "2024-06-01", "shares": 10000, "price": 195.0, "acquired_or_disposed": "D"},
        ]
        patches["insider_edgar"] = patch(
            "src.agents.data_collector.edgar.get_insider_transactions",
            return_value=(mixed_txns, []),
        )

        with patches["market_data"], patches["financials"], patches["price_history"], \
             patches["insider_yf"], patches["institutional"], patches["peers"], \
             patches["cik"], patches["xbrl"], patches["filings"], \
             patches["filing_text"], patches["insider_edgar"], patches["macro"]:

            result = DataCollectorAgent().run("AAPL")

            assert result.insider_activity is not None
            assert result.insider_activity.source == "edgar"
            # 1 buy - 2 sells = -1 (net selling)
            assert result.insider_activity.net_buys == -1
            assert len(result.insider_activity.transactions) == 3

    def test_yfinance_fallback_handles_empty_type_field(self):
        """yfinance insider data often has empty 'type' field — should not count all as buys."""
        patches = _patch_all_sources()
        patches["insider_edgar"] = patch(
            "src.agents.data_collector.edgar.get_insider_transactions",
            return_value=([], []),
        )
        yf_txns_empty_type = [
            {"name": "Cook", "date": "2024-06-01", "type": "", "shares": 60000, "value": 0},
            {"name": "Cook", "date": "2024-06-01", "type": "", "shares": 30000, "value": 5_850_000},
            {"name": "Cook", "date": "2024-06-01", "type": "", "shares": 10000, "value": 1_950_000},
        ]
        patches["insider_yf"] = patch(
            "src.agents.data_collector.yf.get_insider_transactions",
            return_value=(yf_txns_empty_type, []),
        )

        with patches["market_data"], patches["financials"], patches["price_history"], \
             patches["insider_yf"], patches["institutional"], patches["peers"], \
             patches["cik"], patches["xbrl"], patches["filings"], \
             patches["filing_text"], patches["insider_edgar"], patches["macro"]:

            result = DataCollectorAgent().run("AAPL")

            assert result.insider_activity is not None
            assert result.insider_activity.source == "yfinance"
            # With empty type fields, net_buys should NOT equal total count
            # Transactions with value > 0 and empty type are likely sales
            assert result.insider_activity.net_buys != len(yf_txns_empty_type)

    def test_no_insider_data_at_all(self):
        """When both EDGAR and yfinance have no insider data."""
        patches = _patch_all_sources()
        patches["insider_edgar"] = patch(
            "src.agents.data_collector.edgar.get_insider_transactions",
            return_value=([], []),
        )
        patches["insider_yf"] = patch(
            "src.agents.data_collector.yf.get_insider_transactions",
            return_value=([], []),
        )

        with patches["market_data"], patches["financials"], patches["price_history"], \
             patches["insider_yf"], patches["institutional"], patches["peers"], \
             patches["cik"], patches["xbrl"], patches["filings"], \
             patches["filing_text"], patches["insider_edgar"], patches["macro"]:

            result = DataCollectorAgent().run("AAPL")

            assert result.insider_activity is None
