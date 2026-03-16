"""Tests for SEC EDGAR data source — unit tests with mocked HTTP responses."""
import json
import pytest
from unittest.mock import patch, MagicMock

from src.data_sources.sec_edgar import (
    get_cik_from_ticker,
    get_recent_filings,
    get_financial_facts,
    get_filing_text,
    get_insider_transactions,
)


# --- Fixtures ---


SAMPLE_COMPANY_TICKERS = {
    "0": {
        "cik_str": 320193,
        "ticker": "AAPL",
        "title": "Apple Inc.",
    },
    "1": {
        "cik_str": 789019,
        "ticker": "MSFT",
        "title": "Microsoft Corp",
    },
}


SAMPLE_SUBMISSIONS = {
    "cik": "0000320193",
    "entityType": "operating",
    "name": "Apple Inc.",
    "filings": {
        "recent": {
            "accessionNumber": [
                "0000320193-24-000123",
                "0000320193-24-000100",
                "0000320193-23-000108",
            ],
            "filingDate": ["2024-11-01", "2024-08-02", "2023-11-03"],
            "form": ["10-K", "10-Q", "10-K"],
            "primaryDocument": ["aapl-20240928.htm", "aapl-20240629.htm", "aapl-20230930.htm"],
        }
    },
}


SAMPLE_XBRL_FACTS = {
    "cik": 320193,
    "entityName": "Apple Inc.",
    "facts": {
        "us-gaap": {
            "Revenues": {
                "label": "Revenues",
                "units": {
                    "USD": [
                        {
                            "val": 383_285_000_000,
                            "end": "2024-09-28",
                            "fy": 2024,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2024-11-01",
                        },
                        {
                            "val": 383_933_000_000,
                            "end": "2023-09-30",
                            "fy": 2023,
                            "fp": "FY",
                            "form": "10-K",
                            "filed": "2023-11-03",
                        },
                    ]
                },
            },
            "NetIncomeLoss": {
                "label": "Net Income (Loss)",
                "units": {
                    "USD": [
                        {
                            "val": 93_736_000_000,
                            "end": "2024-09-28",
                            "fy": 2024,
                            "fp": "FY",
                            "form": "10-K",
                        },
                    ]
                },
            },
            "Assets": {
                "label": "Assets",
                "units": {
                    "USD": [
                        {
                            "val": 352_583_000_000,
                            "end": "2024-09-28",
                            "fy": 2024,
                            "fp": "FY",
                            "form": "10-K",
                        },
                    ]
                },
            },
        }
    },
}


SAMPLE_FILING_HTML = """
<html>
<body>
<p>Some preamble text about the company.</p>
<p><b>Item 7. Management's Discussion and Analysis of Financial Condition and Results of Operations</b></p>
<p>The following discussion should be read in conjunction with the consolidated financial statements.</p>
<p>Revenue increased 2% year over year driven by strong services growth.</p>
<p>Operating expenses grew 5% reflecting continued investment in R&D.</p>
<p><b>Item 7A. Quantitative and Qualitative Disclosures About Market Risk</b></p>
<p>Interest rate risk information here.</p>
<p><b>Item 1A. Risk Factors</b></p>
<p>The Company is subject to various risks and uncertainties.</p>
<p>Global economic conditions could materially adversely affect the Company.</p>
<p>Supply chain disruptions could impact product availability.</p>
<p><b>Item 2. Properties</b></p>
<p>Company headquarters info.</p>
</body>
</html>
"""


SAMPLE_FORM4_XML = """<?xml version="1.0"?>
<ownershipDocument>
    <issuer>
        <issuerCik>0000320193</issuerCik>
        <issuerName>Apple Inc.</issuerName>
    </issuer>
    <reportingOwner>
        <reportingOwnerId>
            <rptOwnerName>COOK TIMOTHY D</rptOwnerName>
        </reportingOwnerId>
    </reportingOwner>
    <nonDerivativeTable>
        <nonDerivativeTransaction>
            <transactionDate><value>2024-04-01</value></transactionDate>
            <transactionAmounts>
                <transactionShares><value>100000</value></transactionShares>
                <transactionPricePerShare><value>171.00</value></transactionPricePerShare>
                <transactionAcquiredDisposedCode><value>D</value></transactionAcquiredDisposedCode>
            </transactionAmounts>
        </nonDerivativeTransaction>
    </nonDerivativeTable>
</ownershipDocument>
"""


def _mock_response(json_data=None, text="", status_code=200):
    """Create a mock requests.Response."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.text = text
    resp.json.return_value = json_data if json_data else {}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    return resp


# --- CIK Lookup ---


class TestGetCikFromTicker:
    @patch("src.data_sources.sec_edgar.requests.get")
    def test_finds_cik(self, mock_get):
        mock_get.return_value = _mock_response(json_data=SAMPLE_COMPANY_TICKERS)
        cik, warnings = get_cik_from_ticker("AAPL")
        assert cik == "0000320193"
        assert len(warnings) == 0

    @patch("src.data_sources.sec_edgar.requests.get")
    def test_pads_cik_to_10_digits(self, mock_get):
        mock_get.return_value = _mock_response(json_data=SAMPLE_COMPANY_TICKERS)
        cik, warnings = get_cik_from_ticker("AAPL")
        assert len(cik) == 10

    @patch("src.data_sources.sec_edgar.requests.get")
    def test_ticker_not_found(self, mock_get):
        mock_get.return_value = _mock_response(json_data=SAMPLE_COMPANY_TICKERS)
        cik, warnings = get_cik_from_ticker("XXXXX")
        assert cik == ""
        assert len(warnings) > 0

    @patch("src.data_sources.sec_edgar.requests.get")
    def test_handles_network_error(self, mock_get):
        mock_get.side_effect = Exception("Network error")
        cik, warnings = get_cik_from_ticker("AAPL")
        assert cik == ""
        assert len(warnings) > 0


# --- Recent Filings ---


class TestGetRecentFilings:
    @patch("src.data_sources.sec_edgar.time.sleep")
    @patch("src.data_sources.sec_edgar.requests.get")
    def test_returns_filings(self, mock_get, mock_sleep):
        mock_get.return_value = _mock_response(json_data=SAMPLE_SUBMISSIONS)
        filings, warnings = get_recent_filings("0000320193", form_type="10-K")
        assert len(filings) == 2  # 2 10-K filings in sample
        assert filings[0]["filing_date"] == "2024-11-01"
        assert "10-K" in filings[0]["form"]

    @patch("src.data_sources.sec_edgar.time.sleep")
    @patch("src.data_sources.sec_edgar.requests.get")
    def test_filters_by_form_type(self, mock_get, mock_sleep):
        mock_get.return_value = _mock_response(json_data=SAMPLE_SUBMISSIONS)
        filings, warnings = get_recent_filings("0000320193", form_type="10-Q")
        assert len(filings) == 1
        assert filings[0]["form"] == "10-Q"

    @patch("src.data_sources.sec_edgar.time.sleep")
    @patch("src.data_sources.sec_edgar.requests.get")
    def test_handles_network_error(self, mock_get, mock_sleep):
        mock_get.side_effect = Exception("Network error")
        filings, warnings = get_recent_filings("0000320193")
        assert filings == []
        assert len(warnings) > 0


# --- XBRL Financial Facts ---


class TestGetFinancialFacts:
    @patch("src.data_sources.sec_edgar.time.sleep")
    @patch("src.data_sources.sec_edgar.requests.get")
    def test_returns_structured_data(self, mock_get, mock_sleep):
        mock_get.return_value = _mock_response(json_data=SAMPLE_XBRL_FACTS)
        facts, warnings = get_financial_facts("0000320193")
        assert "Revenues" in facts
        assert facts["Revenues"][0]["val"] == 383_285_000_000

    @patch("src.data_sources.sec_edgar.time.sleep")
    @patch("src.data_sources.sec_edgar.requests.get")
    def test_extracts_multiple_concepts(self, mock_get, mock_sleep):
        mock_get.return_value = _mock_response(json_data=SAMPLE_XBRL_FACTS)
        facts, warnings = get_financial_facts("0000320193")
        assert "NetIncomeLoss" in facts
        assert "Assets" in facts

    @patch("src.data_sources.sec_edgar.time.sleep")
    @patch("src.data_sources.sec_edgar.requests.get")
    def test_handles_network_error(self, mock_get, mock_sleep):
        mock_get.side_effect = Exception("EDGAR unavailable")
        facts, warnings = get_financial_facts("0000320193")
        assert facts == {}
        assert len(warnings) > 0


# --- Filing Text Extraction ---


class TestGetFilingText:
    @patch("src.data_sources.sec_edgar.time.sleep")
    @patch("src.data_sources.sec_edgar.requests.get")
    def test_extracts_mda(self, mock_get, mock_sleep):
        mock_get.return_value = _mock_response(text=SAMPLE_FILING_HTML)
        result, warnings = get_filing_text("https://www.sec.gov/Archives/edgar/data/0000320193/filing.htm")
        assert "Revenue increased" in result["mda_text"]

    @patch("src.data_sources.sec_edgar.time.sleep")
    @patch("src.data_sources.sec_edgar.requests.get")
    def test_extracts_risk_factors(self, mock_get, mock_sleep):
        mock_get.return_value = _mock_response(text=SAMPLE_FILING_HTML)
        result, warnings = get_filing_text("https://www.sec.gov/Archives/edgar/data/0000320193/filing.htm")
        assert "risks and uncertainties" in result["risk_factors_text"]

    @patch("src.data_sources.sec_edgar.time.sleep")
    @patch("src.data_sources.sec_edgar.requests.get")
    def test_fallback_on_no_sections(self, mock_get, mock_sleep):
        mock_get.return_value = _mock_response(text="<html><body>Just some text with no sections.</body></html>")
        result, warnings = get_filing_text("https://www.sec.gov/Archives/edgar/data/0000320193/filing.htm")
        # Should fall back to raw text
        assert result["mda_text"] != "" or result["risk_factors_text"] != "" or len(warnings) > 0

    @patch("src.data_sources.sec_edgar.time.sleep")
    @patch("src.data_sources.sec_edgar.requests.get")
    def test_handles_network_error(self, mock_get, mock_sleep):
        mock_get.side_effect = Exception("Network error")
        result, warnings = get_filing_text("https://www.sec.gov/Archives/edgar/data/0000320193/filing.htm")
        assert result["mda_text"] == ""
        assert len(warnings) > 0


# --- Insider Transactions ---


class TestGetInsiderTransactions:
    @patch("src.data_sources.sec_edgar.time.sleep")
    @patch("src.data_sources.sec_edgar.requests.get")
    def test_returns_transactions(self, mock_get, mock_sleep):
        # First call: submissions to find Form 4 filings
        submissions_with_form4 = {
            "cik": "0000320193",
            "filings": {
                "recent": {
                    "accessionNumber": ["0000320193-24-000200"],
                    "filingDate": ["2024-04-02"],
                    "form": ["4"],
                    "primaryDocument": ["xslF345X05/form4.xml"],
                }
            },
        }
        # Second call: the Form 4 XML
        mock_get.side_effect = [
            _mock_response(json_data=submissions_with_form4),
            _mock_response(text=SAMPLE_FORM4_XML),
        ]
        txns, warnings = get_insider_transactions("0000320193")
        assert len(txns) > 0
        assert txns[0]["name"] == "COOK TIMOTHY D"
        assert txns[0]["shares"] == 100000

    @patch("src.data_sources.sec_edgar.time.sleep")
    @patch("src.data_sources.sec_edgar.requests.get")
    def test_handles_no_form4s(self, mock_get, mock_sleep):
        submissions_no_form4 = {
            "cik": "0000320193",
            "filings": {
                "recent": {
                    "accessionNumber": ["0000320193-24-000123"],
                    "filingDate": ["2024-11-01"],
                    "form": ["10-K"],
                    "primaryDocument": ["aapl-20240928.htm"],
                }
            },
        }
        mock_get.return_value = _mock_response(json_data=submissions_no_form4)
        txns, warnings = get_insider_transactions("0000320193")
        assert txns == []

    @patch("src.data_sources.sec_edgar.time.sleep")
    @patch("src.data_sources.sec_edgar.requests.get")
    def test_handles_network_error(self, mock_get, mock_sleep):
        mock_get.side_effect = Exception("Network error")
        txns, warnings = get_insider_transactions("0000320193")
        assert txns == []
        assert len(warnings) > 0


# --- Integration Tests ---


@pytest.mark.integration
class TestSecEdgarIntegration:
    """Integration tests that hit real SEC EDGAR API. Run with: pytest -m integration"""

    def test_aapl_cik_lookup(self):
        cik, warnings = get_cik_from_ticker("AAPL")
        assert cik == "0000320193"

    def test_aapl_financial_facts(self):
        facts, warnings = get_financial_facts("0000320193")
        # AAPL should have revenue data
        revenue_keys = [k for k in facts if "revenue" in k.lower()]
        assert len(revenue_keys) > 0

    def test_aapl_recent_filings(self):
        filings, warnings = get_recent_filings("0000320193", form_type="10-K", count=2)
        assert len(filings) > 0
        assert filings[0]["form"] == "10-K"
