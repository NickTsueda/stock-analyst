"""Orchestrator Agent — pipeline coordination, quality gates, and confidence scoring.

Coordinates the full analysis pipeline:
1. Data Collector → DataPackage
2. Data quality gate (deterministic, no Claude call)
3. Financial Analyst → FinancialAnalysis
4. Thesis Builder → InvestmentThesis (with self-critique)
5. Revision loop (max 1 iteration, 30s timeout)
6. Confidence Score post-processing (6-factor weighted average in Python)

Returns: tuple[DataPackage, FinancialAnalysis | None, InvestmentThesis | None]
"""
from __future__ import annotations

import logging
import time
from typing import Callable

import anthropic

from src.agents.data_collector import DataCollectorAgent
from src.agents.financial_analyst import FinancialAnalystAgent
from src.agents.thesis_builder import ThesisBuilderAgent
from src.models import (
    ConfidenceDriver,
    ConfidenceLevel,
    ConfidenceScore,
    DataPackage,
    FinancialAnalysis,
    InvestmentThesis,
    LimitationNote,
)

logger = logging.getLogger(__name__)

# Confidence factor weights (must sum to 1.0)
_WEIGHTS = {
    "Data Completeness": 0.20,
    "Earnings Quality": 0.25,
    "Valuation Clarity": 0.20,
    "Company Predictability": 0.20,
    "Insider Signal": 0.10,
    "Macro Conditions": 0.05,
}

# Insider signal lookup: (direction, lean) → score
_INSIDER_SIGNAL_MAP = {
    ("BUYING", "BULLISH"): 80,
    ("BUYING", "NEUTRAL"): 70,
    ("BUYING", "BEARISH"): 60,
    ("SELLING", "BEARISH"): 60,
    ("SELLING", "NEUTRAL"): 45,
    ("SELLING", "BULLISH"): 35,
}

_REVISION_TIMEOUT = 30  # seconds


class OrchestratorAgent:
    """Coordinates the analysis pipeline, enforces quality gates, computes confidence."""

    def __init__(self, client: anthropic.Anthropic, model: str | None = None):
        self.client = client
        self.model = model
        self._data_collector = DataCollectorAgent()
        self._financial_analyst = FinancialAnalystAgent(client, model)
        self._thesis_builder = ThesisBuilderAgent(client, model)

    def run(
        self,
        ticker: str,
        progress_callback: Callable[[str, str], None] | None = None,
    ) -> tuple[DataPackage, FinancialAnalysis | None, InvestmentThesis | None]:
        """Run the full analysis pipeline for a ticker.

        Args:
            ticker: Stock ticker symbol (e.g., "AAPL").
            progress_callback: Optional (stage, status) callback for UI updates.

        Returns:
            (DataPackage, FinancialAnalysis | None, InvestmentThesis | None)
        """
        ticker = ticker.upper()

        def _report(stage: str, status: str) -> None:
            if progress_callback:
                progress_callback(stage, status)

        # --- Step 1: Data Collection ---
        _report("Collecting market data", "in_progress")
        try:
            data = self._data_collector.run(ticker)
        except Exception as e:
            logger.error("Data Collector failed: %s", e)
            _report("Collecting market data", "failed")
            error_pkg = DataPackage(
                ticker=ticker,
                warnings=[LimitationNote("orchestrator", f"Data collection failed: {e}", "error")],
            )
            return error_pkg, None, None
        _report("Collecting market data", "complete")

        # --- Step 2: Data Quality Gate ---
        score = data.data_completeness_score
        if score < 20:
            logger.warning("Data completeness %d < 20, aborting analysis for %s", score, ticker)
            _report("Data quality check", "failed")
            data.warnings.append(LimitationNote(
                "orchestrator",
                f"Data completeness score is {score}/100. Insufficient data to produce analysis.",
                "error",
            ))
            return data, None, None

        # Abort if market data is a zero-value shell (nonexistent ticker)
        # yfinance returns MarketData with price=0 for invalid tickers instead of None
        _zero_price_shell = (
            data.market_data is not None
            and (data.market_data.current_price or 0) == 0
            and (data.market_data.market_cap or 0) == 0
        )
        if _zero_price_shell and data.filing_text is None:
            logger.warning("Zero-price market data for %s, aborting analysis", ticker)
            _report("Data quality check", "failed")
            data.warnings.append(LimitationNote(
                "orchestrator",
                "No meaningful data found. Ticker may be invalid or delisted.",
                "error",
            ))
            return data, None, None

        if score < 50:
            logger.warning("Data completeness %d < 50 for %s, proceeding with warning", score, ticker)
            data.warnings.append(LimitationNote(
                "orchestrator",
                f"Data completeness score is {score}/100. Analysis may be incomplete.",
                "warning",
            ))

        # --- Step 3: Financial Analyst ---
        _report("Analyzing financials", "in_progress")
        try:
            analysis = self._financial_analyst.run(data)
        except Exception as e:
            logger.error("Financial Analyst failed: %s", e)
            _report("Analyzing financials", "failed")
            return data, None, None
        _report("Analyzing financials", "complete")

        # --- Step 4: Thesis Builder (initial) ---
        _report("Building investment thesis", "in_progress")
        try:
            thesis = self._thesis_builder.run(data, analysis)
        except Exception as e:
            logger.error("Thesis Builder failed: %s", e)
            _report("Building investment thesis", "failed")
            return data, analysis, None
        _report("Building investment thesis", "complete")

        # --- Step 5: Revision Loop (max 1 iteration) ---
        revised_subscores = None
        if thesis.revision_request:
            _report("Validating thesis (revision loop)", "in_progress")
            revised_thesis, revised_subscores = self._run_revision(data, analysis, thesis)
            if revised_thesis is not None:
                thesis = revised_thesis
            _report("Validating thesis (revision loop)", "complete")

        # --- Step 6: Confidence Score Post-Processing ---
        _report("Computing confidence score", "in_progress")
        confidence = self._compute_confidence(data, analysis, revised_subscores)
        thesis.confidence = confidence
        _report("Computing confidence score", "complete")

        return data, analysis, thesis

    def _run_revision(
        self,
        data: DataPackage,
        analysis: FinancialAnalysis,
        thesis: InvestmentThesis,
    ) -> tuple[InvestmentThesis | None, dict | None]:
        """Run the revision loop with timeout. Returns (revised_thesis, revised_subscores)."""
        try:
            start = time.time()
            revised_analysis = self._financial_analyst.run_revision(
                data, thesis.revision_request
            )
            elapsed = time.time() - start
            if elapsed > _REVISION_TIMEOUT:
                logger.warning("Revision took %.1fs (>%ds), using pre-revision thesis",
                               elapsed, _REVISION_TIMEOUT)
                return None, None

            revised_thesis = self._thesis_builder.run_with_revision(
                data, analysis, revised_analysis
            )
            total = time.time() - start
            if total > _REVISION_TIMEOUT:
                logger.warning("Total revision %.1fs exceeded %ds timeout", total, _REVISION_TIMEOUT)
                return None, None

            return revised_thesis, revised_analysis.revised_subscores
        except Exception as e:
            logger.warning("Revision loop failed: %s, using pre-revision thesis", e)
            return None, None

    def _compute_confidence(
        self,
        data: DataPackage,
        analysis: FinancialAnalysis,
        revised_subscores: dict | None = None,
    ) -> ConfidenceScore:
        """Compute the 6-factor weighted confidence score."""
        # Get qualitative details from Thesis Builder
        details = self._thesis_builder.last_confidence_driver_details
        summary = self._thesis_builder.last_confidence_summary

        # Compute sub-scores
        data_completeness = data.data_completeness_score
        earnings_quality = analysis.earnings_quality
        valuation_clarity = analysis.valuation_clarity
        predictability = data.company_predictability_score
        insider_signal = self._compute_insider_signal(data, analysis)
        macro_conditions = analysis.macro_conditions

        # Merge revised sub-scores from revision loop (if any)
        if revised_subscores:
            earnings_quality = revised_subscores.get("earnings_quality", earnings_quality)
            valuation_clarity = revised_subscores.get("valuation_clarity", valuation_clarity)
            macro_conditions = revised_subscores.get("macro_conditions", macro_conditions)

        # Cap valuation_clarity at 60 when no peer data (per design doc)
        if data.peers is None or len(data.peers) == 0:
            valuation_clarity = min(valuation_clarity, 60)

        # Build drivers
        sub_scores = {
            "Data Completeness": data_completeness,
            "Earnings Quality": earnings_quality,
            "Valuation Clarity": valuation_clarity,
            "Company Predictability": predictability,
            "Insider Signal": insider_signal,
            "Macro Conditions": macro_conditions,
        }

        detail_keys = {
            "Data Completeness": "data_completeness",
            "Earnings Quality": "earnings_quality",
            "Valuation Clarity": "valuation_clarity",
            "Company Predictability": "company_predictability",
            "Insider Signal": "insider_signal",
            "Macro Conditions": "macro_conditions",
        }

        drivers = []
        for factor, weight in _WEIGHTS.items():
            score = sub_scores[factor]
            impact = "positive" if score >= 60 else ("negative" if score < 40 else "neutral")
            drivers.append(ConfidenceDriver(
                factor=factor,
                score=score,
                weight=weight,
                impact=impact,
                detail=details.get(detail_keys[factor], ""),
            ))

        # Compute weighted average
        raw_score = sum(d.score * d.weight for d in drivers)
        final_score = round(raw_score)

        # Guardrail: Data Completeness < 30 caps overall at 40
        if data_completeness < 30:
            final_score = min(final_score, 40)

        # Derive level
        if final_score >= 70:
            level = ConfidenceLevel.HIGH
        elif final_score >= 40:
            level = ConfidenceLevel.MEDIUM
        else:
            level = ConfidenceLevel.LOW

        return ConfidenceScore(
            score=final_score,
            level=level,
            summary=summary,
            drivers=drivers,
        )

    def _compute_insider_signal(
        self,
        data: DataPackage,
        analysis: FinancialAnalysis,
    ) -> int:
        """Compute insider signal sub-score using the asymmetric heuristic."""
        if data.insider_activity is None:
            return 50  # neutral

        net_buys = data.insider_activity.net_buys
        if net_buys == 0:
            return 50  # neutral

        direction = "BUYING" if net_buys > 0 else "SELLING"
        lean = analysis.directional_lean.upper()

        return _INSIDER_SIGNAL_MAP.get((direction, lean), 50)
