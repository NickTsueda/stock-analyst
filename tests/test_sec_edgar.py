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
<p>Revenue increased 2% year over year driven by strong services growth. The Company's total net revenue was $383.3 billion for fiscal year 2024, compared to $383.9 billion for fiscal year 2023. The year-over-year performance reflects the continued strength of the Services segment.</p>
<p>Operating expenses grew 5% reflecting continued investment in R&D. Research and development expense was $31.4 billion, an increase of 6% year over year. Selling, general and administrative expense was $27.5 billion, an increase of 4%.</p>
<p>Gross margin improved to 46.2% from 44.1% in the prior year, driven by a favorable shift toward higher-margin Services revenue. The Company continues to invest heavily in innovation while maintaining strong profitability.</p>
<p><b>Item 7A. Quantitative and Qualitative Disclosures About Market Risk</b></p>
<p>Interest rate risk information here.</p>
<p><b>Item 1A. Risk Factors</b></p>
<p>The Company is subject to various risks and uncertainties that could materially affect its business and financial results. These risks include, but are not limited to, the factors described below.</p>
<p>Global economic conditions could materially adversely affect the Company. Adverse macroeconomic conditions, including inflation, slower growth, or recession, in the United States and internationally could negatively affect demand for the Company's products and services. The Company's operations span numerous countries around the world.</p>
<p>Supply chain disruptions could impact product availability. The Company depends on component and product manufacturing and logistical services provided by outsourcing partners, many of which are located outside the U.S. Disruptions to the supply chain could materially impact the Company's ability to deliver products on time.</p>
<p>The Company faces intense competition in its markets. The technology industry is characterized by rapid innovation and disruption. If the Company fails to compete effectively, its business and financial results could be materially adversely affected.</p>
<p><b>Item 2. Properties</b></p>
<p>Company headquarters info.</p>
</body>
</html>
"""


# Realistic 10-K with TOC before actual sections (reproduces Bug 3)
SAMPLE_FILING_HTML_WITH_TOC = """
<html>
<body>
<h1>APPLE INC. FORM 10-K</h1>
<p>TABLE OF CONTENTS</p>
<table>
<tr><td>Part I</td></tr>
<tr><td>Item 1. Business</td><td>1</td></tr>
<tr><td>Item 1A. Risk Factors</td><td>5</td></tr>
<tr><td>Item 1B. Unresolved Staff Comments</td><td>17</td></tr>
<tr><td>Part II</td></tr>
<tr><td>Item 7. Management's Discussion and Analysis of Financial Condition and Results of Operations</td><td>21</td></tr>
<tr><td>Item 7A. Quantitative and Qualitative Disclosures About Market Risk</td><td>35</td></tr>
<tr><td>Item 8. Financial Statements and Supplementary Data</td><td>36</td></tr>
</table>

<p>Part I</p>
<p><b>Item 1A. Risk Factors</b></p>
<p>The following summarizes factors that could have a material adverse effect on the Company's business, financial condition, results of operations, or stock price. These risk factors should be considered carefully.</p>
<p>The Company's products and services face intense competition. The technology industry is subject to rapid change, and the Company must continually introduce new products, services, and technologies to remain competitive. If the Company is unable to compete effectively, its financial results could be materially adversely affected.</p>
<p>Global economic conditions could negatively affect the Company's business. Adverse macroeconomic conditions, including inflation, slower growth, or recession could cause consumers and businesses to reduce spending on the Company's products and services.</p>
<p>The Company depends on component and product manufacturing and logistical services provided by outsourcing partners, many of which are located outside of the U.S. Disruptions could materially adversely affect the Company's business.</p>
<p>The Company is exposed to credit risk on its trade accounts receivable, vendor non-trade receivables, and prepayments related to long-term supply agreements.</p>
<p>Changes in tax rates, trade agreements, or the adoption of new tax legislation could affect future results.</p>
<p><b>Item 1B. Unresolved Staff Comments</b></p>
<p>None.</p>

<p>Part II</p>
<p><b>Item 7. Management's Discussion and Analysis of Financial Condition and Results of Operations</b></p>
<p>The following discussion should be read in conjunction with the consolidated financial statements and accompanying notes included in this Form 10-K. This section provides a narrative analysis of the Company's financial condition and results of operations for the fiscal years presented.</p>
<p>Revenue for fiscal year 2024 was $383.3 billion, an increase of 2% compared to fiscal year 2023. The growth was primarily driven by higher net sales of Services, partially offset by lower net sales of iPhone, Mac, and iPad. Services revenue reached $96.2 billion, representing a 13% increase year-over-year, driven by growth across all Services categories including advertising, the App Store, and cloud services.</p>
<p>Products revenue was $287.1 billion, a decrease of 1% compared to the prior year. iPhone revenue was $201.2 billion, relatively flat year-over-year. Mac revenue was $29.9 billion, an increase of 2%. iPad revenue was $26.7 billion, a decrease of 6%.</p>
<p>Gross margin was 46.2%, an increase from 44.1% in the prior year, driven by a favorable shift in the product and services mix toward Services, which carry higher margins. Operating expenses were $58.9 billion, an increase of 5%, driven by investments in research and development and advertising.</p>
<p>The Company returned over $100 billion to shareholders during the year through dividends and share repurchases. Cash and cash equivalents at end of year were $29.9 billion. Total debt was $97.0 billion, a decrease from $111.1 billion in the prior year, reflecting debt repayments.</p>
<p><b>Item 7A. Quantitative and Qualitative Disclosures About Market Risk</b></p>
<p>Interest rate and foreign exchange risk information here.</p>
<p><b>Item 8. Financial Statements and Supplementary Data</b></p>
<p>Financial statements begin here.</p>
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
    def test_skips_toc_entries_for_mda(self, mock_get, mock_sleep):
        """Bug 3: Filing with TOC should extract actual MD&A, not the TOC entry."""
        mock_get.return_value = _mock_response(text=SAMPLE_FILING_HTML_WITH_TOC)
        result, warnings = get_filing_text("https://www.sec.gov/Archives/edgar/data/0000320193/filing.htm")
        # Must contain actual prose, not a page number or short TOC snippet
        assert len(result["mda_text"]) > 500
        assert "Revenue for fiscal year" in result["mda_text"]

    @patch("src.data_sources.sec_edgar.time.sleep")
    @patch("src.data_sources.sec_edgar.requests.get")
    def test_skips_toc_entries_for_risk_factors(self, mock_get, mock_sleep):
        """Bug 3: Filing with TOC should extract actual Risk Factors, not page number."""
        mock_get.return_value = _mock_response(text=SAMPLE_FILING_HTML_WITH_TOC)
        result, warnings = get_filing_text("https://www.sec.gov/Archives/edgar/data/0000320193/filing.htm")
        # Must contain actual risk factor prose, not just "5"
        assert len(result["risk_factors_text"]) > 500
        assert "material adverse effect" in result["risk_factors_text"]

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
