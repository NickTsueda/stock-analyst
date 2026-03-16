"""SEC EDGAR data source — XBRL API for financials, HTML parsing for qualitative text.

Uses a hybrid approach:
- XBRL API (data.sec.gov/api/xbrl/companyfacts/) for reliable structured financial data
- BeautifulSoup HTML parsing for best-effort MD&A and Risk Factors extraction
- Form 4 XML parsing for insider transactions

All functions return (data, warnings) and never raise. SEC compliance:
User-Agent header required, 0.1s minimum between requests.
"""
from __future__ import annotations

import logging
import re
import time
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup

from src.config import settings

logger = logging.getLogger(__name__)

_BASE_URL = "https://data.sec.gov"
_EFTS_URL = "https://efts.sec.gov"
_ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data"


def _headers() -> dict:
    return {"User-Agent": settings.SEC_USER_AGENT, "Accept-Encoding": "gzip, deflate"}


def _rate_limit():
    """Respect SEC's 10 requests/second limit."""
    time.sleep(settings.SEC_REQUEST_DELAY)


# --- CIK Lookup ---


def get_cik_from_ticker(ticker: str) -> tuple[str, list[str]]:
    """Look up SEC CIK number from ticker symbol.

    Returns (cik_string_padded_to_10, warnings).
    """
    warnings = []
    try:
        resp = requests.get(
            f"{_EFTS_URL}/LATEST/search-index?q=%22{ticker}%22&dateRange=custom&startdt=2020-01-01&forms=10-K",
            headers=_headers(),
            timeout=10,
        )
        # Use the company tickers JSON — more reliable
        resp = requests.get(
            "https://www.sec.gov/files/company_tickers.json",
            headers=_headers(),
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()

        ticker_upper = ticker.upper()
        for entry in data.values():
            if entry.get("ticker", "").upper() == ticker_upper:
                cik = str(entry["cik_str"]).zfill(10)
                return cik, warnings

        warnings.append(f"Ticker '{ticker}' not found in SEC EDGAR")
        return "", warnings

    except Exception as e:
        logger.warning("SEC CIK lookup failed for %s: %s", ticker, e)
        return "", [f"SEC CIK lookup failed: {e}"]


# --- Recent Filings ---


def get_recent_filings(
    cik: str, form_type: str = "10-K", count: int = 3
) -> tuple[list[dict], list[str]]:
    """Fetch recent filings of a given type from SEC submissions API.

    Returns (list_of_filing_dicts, warnings).
    Each dict: accession_number, filing_date, form, primary_document, filing_url.
    """
    warnings = []
    try:
        _rate_limit()
        url = f"{_BASE_URL}/submissions/CIK{cik}.json"
        resp = requests.get(url, headers=_headers(), timeout=15)
        resp.raise_for_status()
        data = resp.json()

        recent = data.get("filings", {}).get("recent", {})
        accessions = recent.get("accessionNumber", [])
        dates = recent.get("filingDate", [])
        forms = recent.get("form", [])
        docs = recent.get("primaryDocument", [])

        filings = []
        for i in range(len(accessions)):
            if forms[i] == form_type:
                accession_formatted = accessions[i].replace("-", "")
                filing_url = (
                    f"{_ARCHIVES_URL}/{cik.lstrip('0')}/{accession_formatted}/{docs[i]}"
                )
                filings.append({
                    "accession_number": accessions[i],
                    "filing_date": dates[i],
                    "form": forms[i],
                    "primary_document": docs[i],
                    "filing_url": filing_url,
                })
                if len(filings) >= count:
                    break

        return filings, warnings

    except Exception as e:
        logger.warning("SEC filings fetch failed for CIK %s: %s", cik, e)
        return [], [f"SEC filings fetch failed: {e}"]


# --- XBRL Financial Facts ---

# Key US-GAAP concepts to extract (covers income, balance sheet, cash flow)
_KEY_CONCEPTS = [
    "Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
    "SalesRevenueNet", "SalesRevenueGoodsNet",
    "NetIncomeLoss", "GrossProfit", "OperatingIncomeLoss",
    "Assets", "Liabilities", "StockholdersEquity",
    "LongTermDebt", "ShortTermBorrowings", "LongTermDebtAndCapitalLeaseObligations",
    "CashAndCashEquivalentsAtCarryingValue",
    "NetCashProvidedByUsedInOperatingActivities",
    "NetCashProvidedByUsedInFinancingActivities",
    "NetCashProvidedByUsedInInvestingActivities",
    "EarningsPerShareBasic", "EarningsPerShareDiluted",
    "CommonStockSharesOutstanding",
    "CostOfGoodsAndServicesSold", "CostOfRevenue",
    "ResearchAndDevelopmentExpense",
    "OperatingExpenses",
    "Depreciation", "DepreciationDepletionAndAmortization",
    "DividendsCommonStockCash",
]


def get_financial_facts(cik: str) -> tuple[dict, list[str]]:
    """Fetch structured financial data from SEC XBRL API.

    Returns (facts_dict, warnings). facts_dict is keyed by concept name,
    values are lists of data points sorted by date (most recent first).
    Each data point: {val, end, fy, fp, form, filed}.
    """
    warnings = []
    try:
        _rate_limit()
        url = f"{_BASE_URL}/api/xbrl/companyfacts/CIK{cik}.json"
        resp = requests.get(url, headers=_headers(), timeout=15)
        resp.raise_for_status()
        data = resp.json()

        us_gaap = data.get("facts", {}).get("us-gaap", {})
        if not us_gaap:
            warnings.append("No US-GAAP data found in XBRL response")
            return {}, warnings

        facts = {}
        for concept in _KEY_CONCEPTS:
            if concept in us_gaap:
                units = us_gaap[concept].get("units", {})
                # Prefer USD, fall back to shares or other units
                values = units.get("USD", units.get("shares", []))
                if values:
                    # Sort by end date descending (most recent first)
                    sorted_vals = sorted(values, key=lambda x: x.get("end", ""), reverse=True)
                    facts[concept] = sorted_vals

        if not facts:
            warnings.append("XBRL data found but no matching financial concepts")

        return facts, warnings

    except Exception as e:
        logger.warning("SEC XBRL facts failed for CIK %s: %s", cik, e)
        return {}, [f"SEC XBRL financial facts failed: {e}"]


# --- Filing Text Extraction ---

# Regex patterns for section headers (case-insensitive)
_MDA_PATTERNS = [
    re.compile(
        r"item\s*7[\.\s]*[-—]?\s*management.s\s+discussion",
        re.IGNORECASE,
    ),
    re.compile(r"item\s*7[\.\s]", re.IGNORECASE),
]

_MDA_END_PATTERNS = [
    re.compile(r"item\s*7a[\.\s]", re.IGNORECASE),
    re.compile(r"item\s*8[\.\s]", re.IGNORECASE),
]

_RISK_PATTERNS = [
    re.compile(
        r"item\s*1a[\.\s]*[-—]?\s*risk\s+factors",
        re.IGNORECASE,
    ),
    re.compile(r"item\s*1a[\.\s]", re.IGNORECASE),
]

_RISK_END_PATTERNS = [
    re.compile(r"item\s*1b[\.\s]", re.IGNORECASE),
    re.compile(r"item\s*2[\.\s]", re.IGNORECASE),
]

_MAX_SECTION_CHARS = 15_000
_FALLBACK_CHARS = 15_000


def _extract_section(text: str, start_patterns: list, end_patterns: list) -> str:
    """Extract text between start and end section markers."""
    start_pos = None
    for pattern in start_patterns:
        match = pattern.search(text)
        if match:
            start_pos = match.end()
            break

    if start_pos is None:
        return ""

    # Find the end boundary
    end_pos = len(text)
    for pattern in end_patterns:
        match = pattern.search(text, start_pos)
        if match:
            end_pos = min(end_pos, match.start())
            break

    section = text[start_pos:end_pos].strip()
    return section[:_MAX_SECTION_CHARS]


def get_filing_text(filing_url: str) -> tuple[dict, list[str]]:
    """Extract MD&A and Risk Factors from an SEC filing HTML page.

    Best-effort qualitative extraction. Returns (dict, warnings).
    dict keys: mda_text, risk_factors_text.
    """
    warnings = []
    result = {"mda_text": "", "risk_factors_text": ""}
    try:
        _rate_limit()
        resp = requests.get(filing_url, headers=_headers(), timeout=30)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        # Remove script/style tags
        for tag in soup(["script", "style"]):
            tag.decompose()

        text = soup.get_text(separator=" ", strip=True)
        # Normalize whitespace
        text = re.sub(r"\s+", " ", text)

        mda = _extract_section(text, _MDA_PATTERNS, _MDA_END_PATTERNS)
        risk = _extract_section(text, _RISK_PATTERNS, _RISK_END_PATTERNS)

        if mda:
            result["mda_text"] = mda
        else:
            warnings.append("MD&A section not found — using fallback text")
            result["mda_text"] = text[:_FALLBACK_CHARS]

        if risk:
            result["risk_factors_text"] = risk
        else:
            warnings.append("Risk Factors section not found")

        return result, warnings

    except Exception as e:
        logger.warning("SEC filing text extraction failed for %s: %s", filing_url, e)
        return result, [f"SEC filing text extraction failed: {e}"]


# --- Insider Transactions (Form 4) ---


def get_insider_transactions(cik: str, max_filings: int = 20) -> tuple[list[dict], list[str]]:
    """Fetch insider transactions from Form 4 filings.

    Parses Form 4 XML to extract transaction details.
    Returns (list_of_transaction_dicts, warnings).
    Each dict: name, date, shares, price, acquired_or_disposed.
    """
    warnings = []
    try:
        # First, get recent Form 4 filings
        _rate_limit()
        url = f"{_BASE_URL}/submissions/CIK{cik}.json"
        resp = requests.get(url, headers=_headers(), timeout=15)
        resp.raise_for_status()
        data = resp.json()

        recent = data.get("filings", {}).get("recent", {})
        accessions = recent.get("accessionNumber", [])
        dates = recent.get("filingDate", [])
        forms = recent.get("form", [])
        docs = recent.get("primaryDocument", [])

        # Collect Form 4 filing URLs
        form4_urls = []
        for i in range(len(accessions)):
            if forms[i] == "4":
                acc_formatted = accessions[i].replace("-", "")
                filing_url = (
                    f"{_ARCHIVES_URL}/{cik.lstrip('0')}/{acc_formatted}/{docs[i]}"
                )
                form4_urls.append((filing_url, dates[i]))
                if len(form4_urls) >= max_filings:
                    break

        if not form4_urls:
            return [], []

        # Parse each Form 4
        transactions = []
        for url, filing_date in form4_urls:
            txns = _parse_form4(url, filing_date)
            transactions.extend(txns)

        return transactions, warnings

    except Exception as e:
        logger.warning("SEC insider transactions failed for CIK %s: %s", cik, e)
        return [], [f"SEC insider transactions failed: {e}"]


def _parse_form4(url: str, filing_date: str) -> list[dict]:
    """Parse a single Form 4 XML filing for transaction data."""
    try:
        _rate_limit()
        resp = requests.get(url, headers=_headers(), timeout=10)
        resp.raise_for_status()

        # Try XML parsing first, fall back to text extraction
        try:
            root = ElementTree.fromstring(resp.text)
        except ElementTree.ParseError:
            return []

        # Get reporting owner name
        owner_name = ""
        owner_el = root.find(".//rptOwnerName")
        if owner_el is not None and owner_el.text:
            owner_name = owner_el.text.strip()

        transactions = []

        # Non-derivative transactions
        for txn in root.findall(".//nonDerivativeTransaction"):
            date_el = txn.find(".//transactionDate/value")
            shares_el = txn.find(".//transactionShares/value")
            price_el = txn.find(".//transactionPricePerShare/value")
            code_el = txn.find(".//transactionAcquiredDisposedCode/value")

            txn_date = date_el.text if date_el is not None and date_el.text else filing_date
            shares = float(shares_el.text) if shares_el is not None and shares_el.text else 0
            price = float(price_el.text) if price_el is not None and price_el.text else 0
            code = code_el.text if code_el is not None and code_el.text else ""

            transactions.append({
                "name": owner_name,
                "date": txn_date,
                "shares": int(shares),
                "price": round(price, 2),
                "acquired_or_disposed": code,  # A = acquired, D = disposed
            })

        return transactions

    except Exception as e:
        logger.warning("Form 4 parsing failed for %s: %s", url, e)
        return []
