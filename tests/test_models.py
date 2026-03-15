"""Tests for data models — serialization, computed properties, prompt generation."""
import pytest
from src.models import (
    FinancialStatements,
    MarketData,
    InsiderActivity,
    InstitutionalData,
    MacroContext,
    FilingText,
    PeerData,
    DataPackage,
    FinancialRatio,
    FinancialAnalysis,
    InvestmentCase,
    ConfidenceDriver,
    ConfidenceScore,
    InvestmentThesis,
    RevisionRequest,
    RevisedAnalysis,
    LimitationNote,
    Recommendation,
    ConfidenceLevel,
    CompanyType,
)


class TestEnums:
    def test_recommendation_values(self):
        assert Recommendation.BUY.value == "BUY"
        assert Recommendation.HOLD.value == "HOLD"
        assert Recommendation.SELL.value == "SELL"

    def test_confidence_level_values(self):
        assert ConfidenceLevel.HIGH.value == "HIGH"
        assert ConfidenceLevel.MEDIUM.value == "MEDIUM"
        assert ConfidenceLevel.LOW.value == "LOW"

    def test_company_type_values(self):
        assert CompanyType.GROWTH.value == "GROWTH"
        assert CompanyType.TURNAROUND.value == "TURNAROUND"


class TestLimitationNote:
    def test_round_trip(self):
        note = LimitationNote(source="yfinance", message="Rate limited", severity="warning")
        d = note.to_dict()
        restored = LimitationNote.from_dict(d)
        assert restored.source == "yfinance"
        assert restored.severity == "warning"


class TestDataPackage:
    def test_round_trip(self, sample_data_package):
        d = sample_data_package.to_dict()
        restored = DataPackage.from_dict(d)
        assert restored.ticker == sample_data_package.ticker
        assert restored.market_data.current_price == sample_data_package.market_data.current_price
        assert len(restored.warnings) == len(sample_data_package.warnings)

    def test_to_prompt_text(self, sample_data_package):
        text = sample_data_package.to_prompt_text()
        assert sample_data_package.ticker in text
        assert "Revenue" in text or "revenue" in text

    def test_data_completeness_score_all_sources(self, sample_data_package):
        score = sample_data_package.data_completeness_score
        assert score == 100  # all sources present

    def test_data_completeness_score_missing_fred(self, sample_data_package):
        sample_data_package.macro = None
        score = sample_data_package.data_completeness_score
        assert score == 75  # yfinance(40) + edgar(35)

    def test_data_completeness_score_missing_edgar(self, sample_data_package):
        sample_data_package.financials = None
        sample_data_package.filing_text = None
        sample_data_package.insider_activity = None
        score = sample_data_package.data_completeness_score
        assert score == 65  # yfinance(40) + fred(25)

    def test_data_completeness_score_missing_yfinance(self, sample_data_package):
        sample_data_package.market_data = None
        sample_data_package.price_history = None
        sample_data_package.institutional = None
        sample_data_package.peers = None
        score = sample_data_package.data_completeness_score
        assert score == 60  # edgar(35) + fred(25)


class TestConfidenceScore:
    def test_round_trip(self):
        drivers = [
            ConfidenceDriver("Data Completeness", 80, 0.20, "positive", "All sources available"),
            ConfidenceDriver("Earnings Quality", 70, 0.25, "positive", "Consistent earnings"),
            ConfidenceDriver("Valuation Clarity", 60, 0.20, "neutral", "Some peer data"),
            ConfidenceDriver("Company Predictability", 75, 0.20, "positive", "Stable revenue"),
            ConfidenceDriver("Insider Signal", 50, 0.10, "neutral", "No insider data"),
            ConfidenceDriver("Macro Conditions", 65, 0.05, "positive", "Clear macro"),
        ]
        cs = ConfidenceScore(
            score=69,
            level=ConfidenceLevel.MEDIUM,
            summary="Moderate confidence with good data coverage.",
            drivers=drivers,
        )
        d = cs.to_dict()
        restored = ConfidenceScore.from_dict(d)
        assert restored.score == 69
        assert restored.level == ConfidenceLevel.MEDIUM
        assert len(restored.drivers) == 6


class TestRevisionModels:
    def test_revision_request_round_trip(self):
        rr = RevisionRequest(
            questions=["Why are margins declining?"],
            factors_to_reexamine=["Earnings Quality"],
            context="Margins declining despite revenue growth",
        )
        d = rr.to_dict()
        restored = RevisionRequest.from_dict(d)
        assert restored.questions == ["Why are margins declining?"]

    def test_revised_analysis_round_trip(self):
        ra = RevisedAnalysis(
            revised_assessments={"margins": "Driven by one-time costs"},
            revised_subscores={"earnings_quality": 65},
            revision_rationale="Margins explained by restructuring charges",
        )
        d = ra.to_dict()
        restored = RevisedAnalysis.from_dict(d)
        assert restored.revised_subscores["earnings_quality"] == 65


class TestFinancialAnalysis:
    def test_round_trip(self, sample_financial_analysis):
        d = sample_financial_analysis.to_dict()
        restored = FinancialAnalysis.from_dict(d)
        assert restored.company_type == CompanyType.GROWTH
        assert restored.earnings_quality == 75
        assert restored.directional_lean == "BULLISH"


class TestInvestmentThesis:
    def test_round_trip(self, sample_investment_thesis):
        d = sample_investment_thesis.to_dict()
        restored = InvestmentThesis.from_dict(d)
        assert restored.recommendation == Recommendation.BUY
        assert restored.confidence.score == 72
