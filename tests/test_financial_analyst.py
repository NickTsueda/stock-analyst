"""Tests for the Financial Analyst agent.

Tests use mocked Claude responses to verify:
- System prompt construction with UChicago methodology
- JSON response parsing into FinancialAnalysis dataclass
- Handling of incomplete/degraded data
- Revision flow (run_revision method)
- LLM-assessed confidence sub-scores are extracted
"""
import json
from unittest.mock import MagicMock

import pytest

from src.agents.financial_analyst import FinancialAnalystAgent
from src.models import (
    CompanyType,
    DataPackage,
    FinancialAnalysis,
    MarketData,
    RevisionRequest,
    RevisedAnalysis,
)
from tests.conftest import make_sample_data_package


# --- Realistic Claude Response Fixtures ---


def _make_analysis_response() -> dict:
    """Realistic Claude JSON response for AAPL analysis."""
    return {
        "company_type": "GROWTH",
        "profitability": {
            "gross_margin": {"2024": 0.462, "2023": 0.441},
            "operating_margin": {"2024": 0.316, "2023": 0.298},
            "net_margin": {"2024": 0.245, "2023": 0.253},
            "roe": {"2024": 1.61},
            "roa": {"2024": 0.266},
        },
        "growth": {
            "revenue_growth_yoy": -0.002,
            "earnings_growth_yoy": -0.034,
            "revenue_3yr_cagr": 0.08,
            "acceleration": "decelerating",
        },
        "balance_sheet_health": {
            "debt_to_equity": 1.87,
            "current_ratio": 0.99,
            "cash_position": 29_943_000_000,
            "assessment": "Leveraged but manageable given cash flows",
        },
        "cash_flow_quality": {
            "ocf_to_net_income": 1.26,
            "fcf_margin": 0.284,
            "fcf_trend": "stable",
            "assessment": "Exceptional cash conversion",
        },
        "ratios": [
            {
                "name": "P/E",
                "values": {"2024": 28.5, "2023": 26.1},
                "trend": "expanding",
                "assessment": "Premium to peers, supported by quality",
            },
            {
                "name": "EV/EBITDA",
                "values": {"2024": 22.1},
                "trend": "stable",
                "assessment": "In line with mega-cap tech",
            },
        ],
        "peer_comparison": {
            "pe_vs_median": "above",
            "growth_vs_median": "in line",
            "margin_vs_median": "above",
            "summary": "Premium valuation justified by superior margins and cash flow",
        },
        "trend_assessments": {
            "revenue": "stable",
            "margins": "improving",
            "cash_flow": "stable",
            "balance_sheet": "stable",
        },
        "forward_outlook": {
            "revenue_trajectory": "Low single-digit growth, services accelerating",
            "margin_outlook": "Gradual expansion from services mix shift",
            "key_catalysts": ["AI features", "Services growth", "Emerging markets"],
            "key_headwinds": ["Smartphone saturation", "China regulatory risk"],
        },
        "risk_factors": [
            "Geographic concentration in China for manufacturing and sales",
            "Regulatory antitrust scrutiny on App Store",
            "Consumer discretionary exposure in economic downturn",
        ],
        "macro_impact": "Elevated rates pressure valuation multiples, but strong balance sheet provides cushion. Rate cuts would be a tailwind.",
        "insider_interpretation": "Net insider selling is routine for executives with large equity compensation. Pattern consistent with scheduled sales, not directional signal.",
        "strengths": [
            "Best-in-class margins among hardware peers",
            "Services revenue growing at 2x hardware rate",
            "Unmatched ecosystem lock-in and brand loyalty",
        ],
        "concerns": [
            "iPhone revenue plateauing",
            "China sales declining amid geopolitical tensions",
            "High debt-to-equity ratio despite strong cash flows",
        ],
        "directional_lean": "BULLISH",
        "directional_rationale": "Services growth and margin expansion provide a durable growth engine. Premium valuation is supported by quality metrics. Near-term headwinds are well-understood.",
        "earnings_quality": 78,
        "valuation_clarity": 62,
        "macro_conditions": 55,
        "chain_of_thought": "Step 1: Company Type Classification\nApple is best classified as GROWTH...\n\nStep 2: Profitability Analysis\nGross margins expanded from 44.1% to 46.2%...\n\nStep 3: Growth Analysis\nRevenue was essentially flat YoY...",
    }


def _make_revision_response() -> dict:
    """Realistic Claude JSON response for a revision request."""
    return {
        "revised_assessments": {
            "china_risk": "China revenue declined 8% YoY, now 17% of total. Supply chain diversification to India is underway but will take 2-3 years. A severe crackdown could impact ~$65B in revenue.",
            "margin_sustainability": "Services margin (~70%) is 3x hardware margin (~36%). As services grows from 22% to projected 28% of revenue by 2026, blended margins should expand 100-150bps annually.",
        },
        "revised_subscores": {
            "valuation_clarity": 58,
        },
        "revision_rationale": "Deepened China risk analysis with specific revenue exposure data. Margin sustainability thesis strengthened with services mix-shift projections. Reduced valuation clarity slightly due to geopolitical uncertainty premium.",
    }


def _configure_mock_response(mock_client, response_dict: dict):
    """Configure mock Claude client to return a specific JSON response."""
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text=json.dumps(response_dict))],
        usage=MagicMock(input_tokens=5000, output_tokens=2500),
    )


# --- Tests ---


class TestFinancialAnalystRun:
    """Tests for the main run() method."""

    def test_run_returns_financial_analysis(self, mock_claude_client):
        """run() should return a FinancialAnalysis from Claude's JSON response."""
        _configure_mock_response(mock_claude_client, _make_analysis_response())
        agent = FinancialAnalystAgent(mock_claude_client)
        data = make_sample_data_package()

        result = agent.run(data)

        assert isinstance(result, FinancialAnalysis)
        assert result.company_type == CompanyType.GROWTH
        assert result.directional_lean == "BULLISH"

    def test_run_parses_confidence_subscores(self, mock_claude_client):
        """run() should extract LLM-assessed confidence sub-scores."""
        _configure_mock_response(mock_claude_client, _make_analysis_response())
        agent = FinancialAnalystAgent(mock_claude_client)
        data = make_sample_data_package()

        result = agent.run(data)

        assert result.earnings_quality == 78
        assert result.valuation_clarity == 62
        assert result.macro_conditions == 55

    def test_run_parses_ratios(self, mock_claude_client):
        """run() should parse ratio list into FinancialRatio objects."""
        _configure_mock_response(mock_claude_client, _make_analysis_response())
        agent = FinancialAnalystAgent(mock_claude_client)
        data = make_sample_data_package()

        result = agent.run(data)

        assert len(result.ratios) == 2
        assert result.ratios[0].name == "P/E"
        assert result.ratios[0].values["2024"] == 28.5

    def test_run_parses_strengths_concerns(self, mock_claude_client):
        """run() should capture strengths and concerns lists."""
        _configure_mock_response(mock_claude_client, _make_analysis_response())
        agent = FinancialAnalystAgent(mock_claude_client)
        data = make_sample_data_package()

        result = agent.run(data)

        assert len(result.strengths) == 3
        assert len(result.concerns) == 3
        assert "Services" in result.strengths[1]

    def test_run_includes_chain_of_thought(self, mock_claude_client):
        """run() should preserve the chain-of-thought reasoning."""
        _configure_mock_response(mock_claude_client, _make_analysis_response())
        agent = FinancialAnalystAgent(mock_claude_client)
        data = make_sample_data_package()

        result = agent.run(data)

        assert "Step 1" in result.chain_of_thought
        assert "Company Type" in result.chain_of_thought

    def test_run_sends_data_as_prompt_text(self, mock_claude_client):
        """run() should send DataPackage.to_prompt_text() as the user message."""
        _configure_mock_response(mock_claude_client, _make_analysis_response())
        agent = FinancialAnalystAgent(mock_claude_client)
        data = make_sample_data_package()

        agent.run(data)

        call_args = mock_claude_client.messages.create.call_args
        user_msg = call_args.kwargs["messages"][0]["content"]
        assert "AAPL" in user_msg
        assert "Revenue" in user_msg

    def test_run_system_prompt_contains_methodology(self, mock_claude_client):
        """System prompt should reference chain-of-thought methodology steps."""
        _configure_mock_response(mock_claude_client, _make_analysis_response())
        agent = FinancialAnalystAgent(mock_claude_client)
        data = make_sample_data_package()

        agent.run(data)

        call_args = mock_claude_client.messages.create.call_args
        system = call_args.kwargs["system"][0]["text"]
        assert "company type" in system.lower()
        assert "profitability" in system.lower()
        assert "balance sheet" in system.lower()
        assert "cash flow" in system.lower()

    def test_run_system_prompt_contains_rubric_anchors(self, mock_claude_client):
        """System prompt should include calibrated rubric anchors for LLM-assessed scores."""
        _configure_mock_response(mock_claude_client, _make_analysis_response())
        agent = FinancialAnalystAgent(mock_claude_client)
        data = make_sample_data_package()

        agent.run(data)

        call_args = mock_claude_client.messages.create.call_args
        system = call_args.kwargs["system"][0]["text"]
        assert "earnings_quality" in system
        assert "valuation_clarity" in system
        assert "macro_conditions" in system


class TestFinancialAnalystDegraded:
    """Tests for handling incomplete/missing data."""

    def test_run_with_no_macro_data(self, mock_claude_client):
        """Analysis should proceed when macro data is missing."""
        _configure_mock_response(mock_claude_client, _make_analysis_response())
        agent = FinancialAnalystAgent(mock_claude_client)
        data = make_sample_data_package(macro=None)

        result = agent.run(data)

        assert isinstance(result, FinancialAnalysis)

    def test_run_with_no_filing_text(self, mock_claude_client):
        """Analysis should proceed when filing text is missing."""
        _configure_mock_response(mock_claude_client, _make_analysis_response())
        agent = FinancialAnalystAgent(mock_claude_client)
        data = make_sample_data_package(filing_text=None)

        result = agent.run(data)

        assert isinstance(result, FinancialAnalysis)

    def test_run_with_no_peers(self, mock_claude_client):
        """Analysis should proceed when peer data is missing."""
        _configure_mock_response(mock_claude_client, _make_analysis_response())
        agent = FinancialAnalystAgent(mock_claude_client)
        data = make_sample_data_package(peers=None)

        result = agent.run(data)

        assert isinstance(result, FinancialAnalysis)

    def test_run_with_empty_claude_response(self, mock_claude_client):
        """run() should return a default FinancialAnalysis on parse failure."""
        _configure_mock_response(mock_claude_client, {})
        agent = FinancialAnalystAgent(mock_claude_client)
        data = make_sample_data_package()

        result = agent.run(data)

        assert isinstance(result, FinancialAnalysis)
        # Should have defaults, not crash
        assert result.directional_lean == "NEUTRAL"


class TestFinancialAnalystRevision:
    """Tests for the run_revision() method."""

    def test_run_revision_returns_revised_analysis(self, mock_claude_client):
        """run_revision() should return a RevisedAnalysis."""
        _configure_mock_response(mock_claude_client, _make_revision_response())
        agent = FinancialAnalystAgent(mock_claude_client)
        data = make_sample_data_package()
        request = RevisionRequest(
            questions=["How exposed is Apple to China regulatory risk?"],
            factors_to_reexamine=["valuation_clarity"],
            context="Bull thesis relies on margin expansion but China risk underexamined",
        )

        result = agent.run_revision(data, request)

        assert isinstance(result, RevisedAnalysis)
        assert "china_risk" in result.revised_assessments
        assert result.revised_subscores.get("valuation_clarity") == 58
        assert len(result.revision_rationale) > 0

    def test_run_revision_sends_revision_context(self, mock_claude_client):
        """run_revision() should include the revision questions in the prompt."""
        _configure_mock_response(mock_claude_client, _make_revision_response())
        agent = FinancialAnalystAgent(mock_claude_client)
        data = make_sample_data_package()
        request = RevisionRequest(
            questions=["What is the China revenue exposure?"],
            factors_to_reexamine=["valuation_clarity"],
            context="Need deeper China risk analysis",
        )

        agent.run_revision(data, request)

        call_args = mock_claude_client.messages.create.call_args
        user_msg = call_args.kwargs["messages"][0]["content"]
        assert "China revenue exposure" in user_msg

    def test_run_revision_with_empty_response(self, mock_claude_client):
        """run_revision() should return default RevisedAnalysis on parse failure."""
        _configure_mock_response(mock_claude_client, {})
        agent = FinancialAnalystAgent(mock_claude_client)
        data = make_sample_data_package()
        request = RevisionRequest(
            questions=["Test question"],
            factors_to_reexamine=[],
            context="Test",
        )

        result = agent.run_revision(data, request)

        assert isinstance(result, RevisedAnalysis)
        assert result.revision_rationale == ""
