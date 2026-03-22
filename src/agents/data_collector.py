"""Data Collector agent — fetches and assembles data from all sources.

Does NOT call Claude. Pure data orchestration:
1. Fetch from yfinance, SEC EDGAR, FRED
2. Assemble into DataPackage
3. Compute company_predictability_score from quarterly revenue volatility
4. Track warnings from each source

Standalone class (does not extend BaseAgent).
"""
from __future__ import annotations

import logging
import statistics

from src.data_sources import yahoo_finance as yf
from src.data_sources import sec_edgar as edgar
from src.data_sources import fred
from src.models import (
    DataPackage,
    FinancialStatements,
    MarketData,
    InsiderActivity,
    InstitutionalData,
    MacroContext,
    FilingText,
    PeerData,
    LimitationNote,
)

logger = logging.getLogger(__name__)


class DataCollectorAgent:
    """Fetches raw data from all sources and assembles a DataPackage."""

    def __init__(self):
        self._company_name: str = ""
        self._held_pct_institutions: float | None = None

    def run(self, ticker: str) -> DataPackage:
        """Collect all data for a ticker and return a DataPackage.

        Each data source is independent — one failure doesn't block others.
        """
        warnings: list[LimitationNote] = []
        ticker = ticker.upper()

        # --- Yahoo Finance ---
        market_data_obj = self._fetch_market_data(ticker, warnings)
        financials_obj = self._fetch_financials(ticker, warnings)
        price_history = self._fetch_price_history(ticker, warnings)
        insider_yf, insider_yf_warnings = yf.get_insider_transactions(ticker)
        institutional_obj = self._fetch_institutional(ticker, warnings)

        # --- SEC EDGAR ---
        cik, filing_text_obj, xbrl_facts, edgar_insider_txns = self._fetch_edgar(ticker, warnings)

        # --- FRED ---
        macro_obj = self._fetch_macro(warnings)

        # --- Peer data (needs market data for market cap band) ---
        peers_obj = self._fetch_peers(ticker, market_data_obj, warnings)

        # --- Merge EDGAR financial facts into financials if yfinance is missing ---
        if financials_obj is None and xbrl_facts:
            financials_obj = self._financials_from_xbrl(xbrl_facts)

        # --- Insider data: EDGAR primary, yfinance fallback ---
        insider_obj = self._resolve_insider_data(edgar_insider_txns, insider_yf, warnings)

        # --- Company predictability score ---
        # EDGAR XBRL primary (28+ quarters), yfinance fallback (5 quarters)
        quarterly_revenue = self._extract_quarterly_revenue_from_xbrl(xbrl_facts)
        if len(quarterly_revenue) < 8:
            quarterly_revenue = financials_obj.quarterly_revenue if financials_obj else []
        predictability_score = self._compute_predictability_score(quarterly_revenue)

        # --- Company name ---
        company_name = ""
        if market_data_obj:
            company_name = market_data_obj.sector  # fallback
        # market_data dict had company_name — let's check
        # We need to get company_name from the raw market data

        return DataPackage(
            ticker=ticker,
            company_name=self._company_name,
            financials=financials_obj,
            market_data=market_data_obj,
            price_history=price_history if price_history else None,
            insider_activity=insider_obj,
            institutional=institutional_obj,
            macro=macro_obj,
            filing_text=filing_text_obj,
            peers=[PeerData(**p) for p in peers_obj] if peers_obj else None,
            company_predictability_score=predictability_score,
            warnings=warnings,
        )

    # --- Private fetch methods ---

    def _fetch_market_data(self, ticker: str, warnings: list[LimitationNote]) -> MarketData | None:
        data, warns = yf.get_market_data(ticker)
        self._add_warnings(warnings, "yfinance", warns)

        if not data:
            warnings.append(LimitationNote("yfinance", "Market data unavailable", "warning"))
            self._company_name = ""
            self._held_pct_institutions = None
            return None

        self._company_name = data.pop("company_name", "")
        self._held_pct_institutions = data.pop("held_pct_institutions", None)
        return MarketData(**data)

    def _fetch_financials(self, ticker: str, warnings: list[LimitationNote]) -> FinancialStatements | None:
        data, warns = yf.get_financial_statements(ticker)
        self._add_warnings(warnings, "yfinance", warns)

        if not data:
            return None

        return FinancialStatements(
            income_statement=data.get("income_statement", {}),
            balance_sheet=data.get("balance_sheet", {}),
            cash_flow=data.get("cash_flow", {}),
            quarterly_revenue=data.get("quarterly_revenue", []),
        )

    def _fetch_price_history(self, ticker: str, warnings: list[LimitationNote]) -> list[dict]:
        data, warns = yf.get_price_history(ticker)
        self._add_warnings(warnings, "yfinance", warns)
        return data

    def _fetch_institutional(self, ticker: str, warnings: list[LimitationNote]) -> InstitutionalData | None:
        data, warns = yf.get_institutional_holders(ticker)
        self._add_warnings(warnings, "yfinance", warns)

        if not data:
            return None

        # Use total from yfinance info (covers all holders, not just top 10)
        # Falls back to summing top holders if info field unavailable
        held_pct = getattr(self, "_held_pct_institutions", None)
        if held_pct is not None:
            total_pct = round(held_pct * 100, 2)
        else:
            total_pct = round(sum(h.get("pct", 0) for h in data), 2)
        return InstitutionalData(holders=data, institutional_ownership_pct=total_pct)

    def _fetch_edgar(
        self, ticker: str, warnings: list[LimitationNote]
    ) -> tuple[str, FilingText | None, dict, list[dict]]:
        """Fetch all SEC EDGAR data. Returns (cik, filing_text, xbrl_facts, insider_txns)."""
        cik, warns = edgar.get_cik_from_ticker(ticker)
        self._add_warnings(warnings, "sec_edgar", warns)

        if not cik:
            warnings.append(LimitationNote("sec_edgar", "CIK not found — EDGAR data unavailable", "warning"))
            return "", None, {}, []

        # XBRL financial facts
        xbrl_facts, warns = edgar.get_financial_facts(cik)
        self._add_warnings(warnings, "sec_edgar", warns)

        # Filing text (MD&A, risk factors)
        filing_text_obj = None
        filings, warns = edgar.get_recent_filings(cik, form_type="10-K", count=1)
        self._add_warnings(warnings, "sec_edgar", warns)

        if filings:
            text_data, warns = edgar.get_filing_text(filings[0]["filing_url"])
            self._add_warnings(warnings, "sec_edgar", warns)

            if text_data.get("mda_text") or text_data.get("risk_factors_text"):
                filing_text_obj = FilingText(
                    mda_text=text_data.get("mda_text", ""),
                    risk_factors_text=text_data.get("risk_factors_text", ""),
                    filing_date=filings[0].get("filing_date", ""),
                    filing_type="10-K",
                )

        # Insider transactions (Form 4)
        insider_txns, warns = edgar.get_insider_transactions(cik)
        self._add_warnings(warnings, "sec_edgar", warns)

        return cik, filing_text_obj, xbrl_facts, insider_txns

    def _fetch_macro(self, warnings: list[LimitationNote]) -> MacroContext | None:
        data, warns = fred.get_macro_context()
        self._add_warnings(warnings, "fred", warns)

        if not data:
            warnings.append(LimitationNote("fred", "Macro data unavailable", "warning"))
            return None

        return MacroContext(
            fed_funds_rate=data.get("fed_funds_rate"),
            gdp_growth=data.get("gdp_growth"),
            unemployment_rate=data.get("unemployment_rate"),
            cpi_yoy=data.get("cpi_yoy"),
            yield_spread=data.get("yield_spread"),
            as_of_date=data.get("as_of_date", ""),
        )

    def _fetch_peers(
        self, ticker: str, market_data: MarketData | None, warnings: list[LimitationNote]
    ) -> list[dict]:
        if not market_data or not market_data.industry:
            return []

        peers, warns = yf.get_peer_data(
            ticker=ticker,
            industry=market_data.industry,
            market_cap=market_data.market_cap,
            sector=market_data.sector,
        )
        self._add_warnings(warnings, "yfinance", warns)
        return peers

    # --- Helper methods ---

    def _resolve_insider_data(
        self,
        edgar_txns: list[dict],
        yf_txns: list[dict],
        warnings: list[LimitationNote],
    ) -> InsiderActivity | None:
        """Use EDGAR insider data as primary, yfinance as fallback. Do not merge."""
        if edgar_txns:
            net_buys = sum(
                1 if t.get("acquired_or_disposed") == "A" else -1
                for t in edgar_txns
            )
            return InsiderActivity(
                transactions=edgar_txns,
                net_buys=net_buys,
                source="edgar",
            )

        if yf_txns:
            net_buys = 0
            for t in yf_txns:
                txn_type = t.get("type", "").lower()
                if "sale" in txn_type or "sell" in txn_type:
                    net_buys -= 1
                elif "purchase" in txn_type or "buy" in txn_type:
                    net_buys += 1
                # Empty or unrecognized type → neutral (0), not a buy
            return InsiderActivity(
                transactions=yf_txns,
                net_buys=net_buys,
                source="yfinance",
            )

        return None

    def _financials_from_xbrl(self, xbrl_facts: dict) -> FinancialStatements:
        """Build FinancialStatements from XBRL facts when yfinance is unavailable."""
        income = {}
        balance = {}
        cash = {}

        # Map XBRL concepts to readable names
        income_concepts = {
            "Revenues": "Revenue",
            "RevenueFromContractWithCustomerExcludingAssessedTax": "Revenue",
            "SalesRevenueNet": "Revenue",
            "NetIncomeLoss": "Net Income",
            "GrossProfit": "Gross Profit",
            "OperatingIncomeLoss": "Operating Income",
        }
        balance_concepts = {
            "Assets": "Total Assets",
            "Liabilities": "Total Liabilities",
            "StockholdersEquity": "Stockholders Equity",
            "CashAndCashEquivalentsAtCarryingValue": "Cash and Equivalents",
        }
        cash_concepts = {
            "NetCashProvidedByUsedInOperatingActivities": "Operating Cash Flow",
            "NetCashProvidedByUsedInInvestingActivities": "Investing Cash Flow",
            "NetCashProvidedByUsedInFinancingActivities": "Financing Cash Flow",
        }

        for concept, label in income_concepts.items():
            if concept in xbrl_facts and label not in income:
                entries = xbrl_facts[concept]
                # Get annual (10-K) entries only
                annual = [e for e in entries if e.get("form") == "10-K"]
                if annual:
                    income[label] = {str(e.get("fy", "")): e["val"] for e in annual[:4]}

        for concept, label in balance_concepts.items():
            if concept in xbrl_facts and label not in balance:
                entries = xbrl_facts[concept]
                annual = [e for e in entries if e.get("form") == "10-K"]
                if annual:
                    balance[label] = {str(e.get("fy", "")): e["val"] for e in annual[:4]}

        for concept, label in cash_concepts.items():
            if concept in xbrl_facts and label not in cash:
                entries = xbrl_facts[concept]
                annual = [e for e in entries if e.get("form") == "10-K"]
                if annual:
                    cash[label] = {str(e.get("fy", "")): e["val"] for e in annual[:4]}

        return FinancialStatements(
            income_statement=income,
            balance_sheet=balance,
            cash_flow=cash,
        )

    @staticmethod
    def _extract_quarterly_revenue_from_xbrl(xbrl_facts: dict) -> list[dict]:
        """Extract quarterly revenue entries from XBRL facts.

        Returns list of dicts with 'frame' and 'val' keys, sorted by frame
        descending. Frame format: 'CY2024Q4'. Only includes entries with
        'Q' in the frame (single-quarter, not annual).
        """
        revenue_concepts = [
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "Revenues",
            "SalesRevenueNet",
            "SalesRevenueGoodsNet",
        ]

        for concept in revenue_concepts:
            entries = xbrl_facts.get(concept, [])
            # Filter for quarterly entries: must have 'frame' with 'Q' in it
            quarterly = [
                e for e in entries
                if "frame" in e and "Q" in e.get("frame", "")
            ]
            if len(quarterly) >= 8:
                quarterly.sort(key=lambda e: e["frame"], reverse=True)
                return [{"frame": e["frame"], "val": e["val"]} for e in quarterly]

        return []

    @staticmethod
    def _compute_predictability_score(quarterly_entries: list[dict | float]) -> int:
        """Compute company predictability from quarterly revenue patterns.

        Deseasonalized method (preferred): computes YoY growth rates for
        same-quarter pairs (e.g., Q1 2024 vs Q1 2023), then measures the
        CV of those growth rates. This captures consistency of the company's
        growth pattern without penalizing seasonality or steady growth.

        Fallback (raw CV): used when frame info is unavailable. Measures
        raw revenue dispersion — penalizes seasonal and growth companies.

        Requires >= 8 quarters of data; defaults to 50 if insufficient.
        """
        if len(quarterly_entries) < 8:
            return 50

        # Try deseasonalized YoY method if we have frame info
        if quarterly_entries and isinstance(quarterly_entries[0], dict):
            yoy_rates = DataCollectorAgent._compute_yoy_growth_rates(quarterly_entries)
            if len(yoy_rates) >= 4:
                cv = statistics.stdev(yoy_rates) if len(yoy_rates) > 1 else 0.0
                return DataCollectorAgent._cv_to_score(cv)

        # Fallback: raw CV of revenue values
        values = [
            (e["val"] if isinstance(e, dict) else e)
            for e in quarterly_entries
        ]
        valid = [v for v in values if isinstance(v, (int, float)) and v > 0]
        if len(valid) < 8:
            return 50

        mean = statistics.mean(valid)
        if mean == 0:
            return 50

        cv = statistics.stdev(valid) / mean
        return DataCollectorAgent._cv_to_score(cv)

    @staticmethod
    def _compute_yoy_growth_rates(entries: list[dict]) -> list[float]:
        """Compute YoY growth rates from same-quarter pairs.

        Parses frames like 'CY2024Q4' into (year, quarter), groups by quarter,
        then computes (this_year - last_year) / last_year for consecutive years.
        """
        # Parse frames into (year, quarter, value)
        parsed = []
        for e in entries:
            frame = e.get("frame", "")
            val = e.get("val", 0)
            if not frame or val is None or val <= 0:
                continue
            # Parse CY2024Q4 → year=2024, quarter=4
            try:
                q_idx = frame.index("Q")
                year = int(frame[2:q_idx])
                quarter = int(frame[q_idx + 1:])
                parsed.append((year, quarter, val))
            except (ValueError, IndexError):
                continue

        # Group by quarter number
        from collections import defaultdict
        by_quarter: dict[int, list[tuple[int, float]]] = defaultdict(list)
        for year, quarter, val in parsed:
            by_quarter[quarter].append((year, val))

        # For each quarter, sort by year and compute consecutive YoY rates
        yoy_rates = []
        for _q, year_vals in by_quarter.items():
            year_vals.sort()  # ascending by year
            for i in range(1, len(year_vals)):
                prev_year, prev_val = year_vals[i - 1]
                curr_year, curr_val = year_vals[i]
                if curr_year == prev_year + 1 and prev_val > 0:
                    rate = (curr_val - prev_val) / prev_val
                    yoy_rates.append(rate)

        return yoy_rates

    @staticmethod
    def _cv_to_score(cv: float) -> int:
        """Map coefficient of variation to predictability score (0-100).

        5 bands with linear interpolation within each band.
        """
        bands = [
            (0.00, 0.05, 90, 100),   # Very stable
            (0.05, 0.15, 70, 89),    # Stable growth
            (0.15, 0.30, 50, 69),    # Moderate volatility
            (0.30, 0.50, 30, 49),    # High volatility
            (0.50, float("inf"), 10, 29),  # Very unpredictable
        ]

        for cv_low, cv_high, score_high, score_low in bands:
            if cv_low <= cv < cv_high:
                if cv_high == float("inf"):
                    return max(score_high, score_low - int((cv - cv_low) * 20))
                t = (cv - cv_low) / (cv_high - cv_low)
                return round(score_low - t * (score_low - score_high))

        return 50

    @staticmethod
    def _add_warnings(
        warnings: list[LimitationNote], source: str, source_warnings: list[str]
    ) -> None:
        for msg in source_warnings:
            warnings.append(LimitationNote(source=source, message=msg, severity="warning"))
