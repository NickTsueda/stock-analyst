"""Tests for the Thesis Builder agent.

Tests use mocked Claude responses to verify:
- Narrative synthesis into InvestmentThesis
- Self-critique producing RevisionRequest when gaps found
- No RevisionRequest when self-critique finds no gaps
- run_with_revision() incorporating revised analysis
- Handling of incomplete/degraded data
- System prompt content (narrative synthesis instructions)
- User prompt includes both DataPackage and FinancialAnalysis
"""
import json
from unittest.mock import MagicMock

import pytest

from src.agents.thesis_builder import ThesisBuilderAgent
from src.models import (
    CompanyType,
    FinancialAnalysis,
    InvestmentThesis,
    InvestmentCase,
    Recommendation,
    RevisionRequest,
    RevisedAnalysis,
)
from tests.conftest import make_sample_data_package


# --- Realistic Claude Response Fixtures ---


def _make_thesis_response(requires_revision: bool = False) -> dict:
    """Realistic Claude JSON response for thesis synthesis."""
    response = {
        "recommendation": "BUY",
        "executive_summary": "Apple remains a compelling long-term investment anchored by its "
        "services-driven margin expansion and unmatched ecosystem. While iPhone revenue has "
        "plateaued, the shift toward higher-margin services — now 22% of revenue growing at "
        "2x the hardware rate — provides a durable earnings growth engine. At 28.5x trailing "
        "earnings, the stock trades at a premium to mega-cap peers, but this is justified by "
        "superior cash flow quality (1.26x OCF/NI ratio) and best-in-class profitability.\n\n"
        "The primary risk is geographic: China accounts for ~17% of revenue and is the key "
        "manufacturing hub. A severe regulatory crackdown could impact $65B+ in annual revenue. "
        "However, supply chain diversification to India is underway, and the installed base "
        "of 2B+ active devices provides significant recurring revenue insulation.",
        "bull_case": {
            "narrative": "Services accelerates to 25%+ growth as AI features drive App Store "
            "engagement. iPhone upgrade cycle re-accelerates with AI capabilities. China risks "
            "remain manageable.",
            "drivers": [
                "AI-powered features drive App Store revenue acceleration",
                "Services reaches 30% of revenue by 2026",
                "Emerging market smartphone share gains",
            ],
            "probability": 0.25,
        },
        "base_case": {
            "narrative": "Steady low-single-digit revenue growth with continued margin expansion "
            "from services mix shift. iPhone stable, services grows mid-teens.",
            "drivers": [
                "iPhone revenue flat to low-single-digit growth",
                "Services continues mid-teens growth trajectory",
                "Buybacks reduce share count 3-4% annually",
            ],
            "probability": 0.55,
        },
        "bear_case": {
            "narrative": "China regulatory crackdown materially impacts revenue. Smartphone market "
            "deterioration accelerates. Antitrust actions force App Store fee reductions.",
            "drivers": [
                "China revenue declines 20%+",
                "Global smartphone demand contraction",
                "App Store take rate reduced by regulation",
            ],
            "probability": 0.20,
        },
        "peer_comparison_narrative": "Apple trades at 28.5x P/E vs the mega-cap tech median of "
        "~30x. The modest discount reflects slower top-line growth, but Apple's margins (46% gross, "
        "32% operating) and cash conversion (1.26x OCF/NI) are best-in-class.",
        "forward_outlook": "12-month outlook: moderate upside driven by services margin expansion "
        "and potential AI catalyst. Revenue growth of 2-5% expected, with operating margin "
        "expanding 50-100bps from services mix shift. Key watch items: iPhone 16 cycle sell-through "
        "data and China regulatory developments.",
        "risks": [
            "China regulatory and geopolitical risk to revenue and supply chain",
            "Antitrust scrutiny on App Store fees in US and EU",
            "Consumer discretionary exposure in potential economic downturn",
            "Smartphone market maturation limiting iPhone growth",
        ],
        "catalysts": [
            "AI feature integration driving App Store engagement and upgrade cycles",
            "Services margin expansion as mix shifts to higher-margin revenue",
            "Capital return program — $90B+ annual buyback capacity",
            "Emerging market smartphone penetration gains",
        ],
        "macro_context": "The current macro environment is a modest headwind. Elevated rates "
        "(Fed Funds 5.33%) pressure growth stock valuations, but Apple's strong cash generation "
        "provides insulation. Rate cuts, if they materialize, would be a meaningful tailwind for "
        "the multiple. GDP growth of 2.8% supports consumer spending, though CPI at 3.1% may "
        "pressure discretionary budgets.",
        "insider_summary": "Net insider selling (-1 net buys) is consistent with routine executive "
        "compensation sales. Tim Cook's scheduled sales are well-disclosed 10b5-1 plans. The selling "
        "pattern does not signal directional concern — this is standard for mega-cap tech executives "
        "with large equity grants.",
        "confidence_summary": "Moderately high confidence supported by comprehensive data and "
        "consistent earnings quality. Valuation clarity is good but not exceptional due to Apple's "
        "unique positioning making direct peer comparison imperfect.",
        "confidence_driver_details": {
            "data_completeness": "All three data sources returned successfully — full financial "
            "statements, insider data, institutional holdings, and macro indicators available.",
            "earnings_quality": "Exceptional cash flow quality (1.26x OCF/NI) and consistent "
            "margin expansion support high earnings quality. No red flags in the financial statements.",
            "valuation_clarity": "Good peer group available (MSFT, GOOGL, AMZN) but Apple's "
            "hardware+services hybrid model makes direct comparison imperfect. Multiple valuation "
            "methods available but don't fully converge.",
            "company_predictability": "Revenue shows moderate seasonal variation but the underlying "
            "business is highly predictable. Services provides increasing recurring revenue stability.",
            "insider_signal": "Net selling is routine and well-disclosed. Consistent with "
            "compensation-driven sales, not directional concern.",
            "macro_conditions": "Mixed macro environment — strong GDP but elevated rates and "
            "inflation create crosscurrents for consumer discretionary names.",
        },
        "self_critique": {
            "weakest_assumptions": [
                "Services growth rate sustainability assumed without examining competitive threats",
            ],
            "contradictions": [],
            "gaps": [],
            "requires_revision": requires_revision,
            "revision_questions": [],
            "revision_factors": [],
            "revision_context": "",
        },
    }

    if requires_revision:
        response["self_critique"]["gaps"] = [
            "China revenue exposure not fully quantified against bull case assumptions",
        ]
        response["self_critique"]["revision_questions"] = [
            "What is Apple's specific China revenue exposure and how has it trended?",
            "Are services margins sustainable given increasing regulatory pressure on App Store fees?",
        ]
        response["self_critique"]["revision_factors"] = ["valuation_clarity", "earnings_quality"]
        response["self_critique"]["revision_context"] = (
            "Bull thesis relies on margin expansion from services, but regulatory risk to App "
            "Store fees and China concentration risk are underexamined."
        )

    return response


def _make_revised_thesis_response() -> dict:
    """Realistic Claude response for run_with_revision() — thesis incorporating revised analysis."""
    base = _make_thesis_response(requires_revision=False)
    base["executive_summary"] = (
        "Apple remains a compelling investment, though with clearer risk calibration after "
        "deeper examination. China revenue exposure (~17%, trending down) is meaningful but "
        "manageable given active supply chain diversification. Services margin sustainability "
        "is supported by ecosystem lock-in, though App Store fee regulation could trim 200-300bps "
        "from services margins.\n\n"
        "The revised analysis strengthens the base case: even with regulatory headwinds on App Store "
        "fees, blended margin expansion from services mix shift remains intact. The bear case "
        "probability increases slightly to account for the tail risk of simultaneous China "
        "disruption and regulatory action."
    )
    base["bear_case"]["probability"] = 0.25
    base["base_case"]["probability"] = 0.50
    base["bull_case"]["probability"] = 0.25
    return base


def _make_sample_analysis() -> FinancialAnalysis:
    """Create a sample FinancialAnalysis for testing."""
    return FinancialAnalysis(
        company_type=CompanyType.GROWTH,
        profitability={"gross_margin": {"2024": 0.462, "2023": 0.441}},
        growth={"revenue_growth_yoy": -0.002},
        balance_sheet_health={"debt_to_equity": 1.87},
        cash_flow_quality={"ocf_to_net_income": 1.26},
        ratios=[],
        peer_comparison={"pe_vs_median": "above"},
        trend_assessments={"revenue": "stable", "margins": "improving"},
        forward_outlook={"revenue_trajectory": "Low single-digit growth"},
        risk_factors=["China risk", "Antitrust"],
        macro_impact="Elevated rates pressure valuation",
        insider_interpretation="Routine selling",
        strengths=["Best-in-class margins", "Services growth"],
        concerns=["iPhone saturation", "China exposure"],
        directional_lean="BULLISH",
        directional_rationale="Services tailwind supports premium valuation",
        earnings_quality=78,
        valuation_clarity=62,
        macro_conditions=55,
        chain_of_thought="Step 1: Growth company...",
    )


def _configure_mock_response(mock_client, response_dict: dict):
    """Configure mock Claude client to return a specific JSON response."""
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text=json.dumps(response_dict))],
        usage=MagicMock(input_tokens=8000, output_tokens=3500),
    )


# --- Tests ---


class TestThesisBuilderRun:
    """Tests for the main run() method."""

    def test_run_returns_investment_thesis(self, mock_claude_client):
        """run() should return an InvestmentThesis from Claude's JSON response."""
        _configure_mock_response(mock_claude_client, _make_thesis_response())
        agent = ThesisBuilderAgent(mock_claude_client)
        data = make_sample_data_package()
        analysis = _make_sample_analysis()

        result = agent.run(data, analysis)

        assert isinstance(result, InvestmentThesis)
        assert result.recommendation == Recommendation.BUY

    def test_run_parses_executive_summary(self, mock_claude_client):
        """run() should extract the executive summary."""
        _configure_mock_response(mock_claude_client, _make_thesis_response())
        agent = ThesisBuilderAgent(mock_claude_client)
        data = make_sample_data_package()
        analysis = _make_sample_analysis()

        result = agent.run(data, analysis)

        assert "services" in result.executive_summary.lower()
        assert len(result.executive_summary) > 100

    def test_run_parses_bull_base_bear_cases(self, mock_claude_client):
        """run() should parse all three investment cases with probabilities."""
        _configure_mock_response(mock_claude_client, _make_thesis_response())
        agent = ThesisBuilderAgent(mock_claude_client)
        data = make_sample_data_package()
        analysis = _make_sample_analysis()

        result = agent.run(data, analysis)

        assert isinstance(result.bull_case, InvestmentCase)
        assert isinstance(result.base_case, InvestmentCase)
        assert isinstance(result.bear_case, InvestmentCase)
        # Probabilities should sum to 1.0
        total = result.bull_case.probability + result.base_case.probability + result.bear_case.probability
        assert abs(total - 1.0) < 0.01

    def test_run_parses_risks_and_catalysts(self, mock_claude_client):
        """run() should extract risks and catalysts lists."""
        _configure_mock_response(mock_claude_client, _make_thesis_response())
        agent = ThesisBuilderAgent(mock_claude_client)
        data = make_sample_data_package()
        analysis = _make_sample_analysis()

        result = agent.run(data, analysis)

        assert len(result.risks) >= 3
        assert len(result.catalysts) >= 3
        assert any("china" in r.lower() for r in result.risks)

    def test_run_parses_all_narrative_sections(self, mock_claude_client):
        """run() should populate peer comparison, forward outlook, macro, insider sections."""
        _configure_mock_response(mock_claude_client, _make_thesis_response())
        agent = ThesisBuilderAgent(mock_claude_client)
        data = make_sample_data_package()
        analysis = _make_sample_analysis()

        result = agent.run(data, analysis)

        assert len(result.peer_comparison_narrative) > 0
        assert len(result.forward_outlook) > 0
        assert len(result.macro_context) > 0
        assert len(result.insider_summary) > 0

    def test_run_extracts_confidence_details(self, mock_claude_client):
        """run() should store confidence qualitative details for Orchestrator."""
        _configure_mock_response(mock_claude_client, _make_thesis_response())
        agent = ThesisBuilderAgent(mock_claude_client)
        data = make_sample_data_package()
        analysis = _make_sample_analysis()

        result = agent.run(data, analysis)

        # Confidence details should be stored for Orchestrator post-processing
        assert hasattr(agent, "last_confidence_summary")
        assert hasattr(agent, "last_confidence_driver_details")
        assert "confidence" in agent.last_confidence_summary.lower()
        assert "data_completeness" in agent.last_confidence_driver_details
        assert "earnings_quality" in agent.last_confidence_driver_details


class TestThesisBuilderSelfCritique:
    """Tests for self-critique and revision request generation."""

    def test_no_revision_when_critique_finds_no_gaps(self, mock_claude_client):
        """run() should return thesis with no RevisionRequest when no substantive gaps."""
        _configure_mock_response(mock_claude_client, _make_thesis_response(requires_revision=False))
        agent = ThesisBuilderAgent(mock_claude_client)
        data = make_sample_data_package()
        analysis = _make_sample_analysis()

        result = agent.run(data, analysis)

        assert result.revision_request is None

    def test_revision_request_when_critique_finds_gaps(self, mock_claude_client):
        """run() should produce RevisionRequest when self-critique identifies substantive gaps."""
        _configure_mock_response(mock_claude_client, _make_thesis_response(requires_revision=True))
        agent = ThesisBuilderAgent(mock_claude_client)
        data = make_sample_data_package()
        analysis = _make_sample_analysis()

        result = agent.run(data, analysis)

        assert result.revision_request is not None
        assert isinstance(result.revision_request, RevisionRequest)
        assert len(result.revision_request.questions) >= 1
        assert len(result.revision_request.questions) <= 3
        assert len(result.revision_request.context) > 0

    def test_revision_request_has_factors_to_reexamine(self, mock_claude_client):
        """RevisionRequest should specify which factors need deeper scrutiny."""
        _configure_mock_response(mock_claude_client, _make_thesis_response(requires_revision=True))
        agent = ThesisBuilderAgent(mock_claude_client)
        data = make_sample_data_package()
        analysis = _make_sample_analysis()

        result = agent.run(data, analysis)

        assert len(result.revision_request.factors_to_reexamine) >= 1


class TestThesisBuilderRevision:
    """Tests for run_with_revision() method."""

    def test_run_with_revision_returns_thesis(self, mock_claude_client):
        """run_with_revision() should return an updated InvestmentThesis."""
        _configure_mock_response(mock_claude_client, _make_revised_thesis_response())
        agent = ThesisBuilderAgent(mock_claude_client)
        data = make_sample_data_package()
        analysis = _make_sample_analysis()
        revised = RevisedAnalysis(
            revised_assessments={"china_risk": "China revenue ~17%, trending down"},
            revised_subscores={"valuation_clarity": 58},
            revision_rationale="Deepened China risk analysis",
        )

        result = agent.run_with_revision(data, analysis, revised)

        assert isinstance(result, InvestmentThesis)
        assert result.recommendation == Recommendation.BUY

    def test_run_with_revision_incorporates_revised_data(self, mock_claude_client):
        """run_with_revision() should send revised analysis in the prompt."""
        _configure_mock_response(mock_claude_client, _make_revised_thesis_response())
        agent = ThesisBuilderAgent(mock_claude_client)
        data = make_sample_data_package()
        analysis = _make_sample_analysis()
        revised = RevisedAnalysis(
            revised_assessments={"china_risk": "China revenue declined 8% YoY"},
            revised_subscores={},
            revision_rationale="Deepened China risk analysis",
        )

        agent.run_with_revision(data, analysis, revised)

        call_args = mock_claude_client.messages.create.call_args
        user_msg = call_args.kwargs["messages"][0]["content"]
        assert "China revenue declined" in user_msg
        assert "Deepened China risk" in user_msg

    def test_run_with_revision_no_revision_request(self, mock_claude_client):
        """run_with_revision() should not produce a new RevisionRequest."""
        _configure_mock_response(mock_claude_client, _make_revised_thesis_response())
        agent = ThesisBuilderAgent(mock_claude_client)
        data = make_sample_data_package()
        analysis = _make_sample_analysis()
        revised = RevisedAnalysis(
            revised_assessments={"china_risk": "Detailed assessment"},
            revised_subscores={},
            revision_rationale="Analysis updated",
        )

        result = agent.run_with_revision(data, analysis, revised)

        assert result.revision_request is None


class TestThesisBuilderDegraded:
    """Tests for handling incomplete/missing data."""

    def test_run_with_no_peers(self, mock_claude_client):
        """Thesis should be generated even without peer data."""
        _configure_mock_response(mock_claude_client, _make_thesis_response())
        agent = ThesisBuilderAgent(mock_claude_client)
        data = make_sample_data_package(peers=None)
        analysis = _make_sample_analysis()

        result = agent.run(data, analysis)

        assert isinstance(result, InvestmentThesis)

    def test_run_with_no_macro(self, mock_claude_client):
        """Thesis should be generated even without macro data."""
        _configure_mock_response(mock_claude_client, _make_thesis_response())
        agent = ThesisBuilderAgent(mock_claude_client)
        data = make_sample_data_package(macro=None)
        analysis = _make_sample_analysis()

        result = agent.run(data, analysis)

        assert isinstance(result, InvestmentThesis)

    def test_run_with_empty_claude_response(self, mock_claude_client):
        """run() should return a default InvestmentThesis on parse failure."""
        _configure_mock_response(mock_claude_client, {})
        agent = ThesisBuilderAgent(mock_claude_client)
        data = make_sample_data_package()
        analysis = _make_sample_analysis()

        result = agent.run(data, analysis)

        assert isinstance(result, InvestmentThesis)
        assert result.recommendation == Recommendation.HOLD


class TestThesisBuilderPrompts:
    """Tests for system and user prompt content."""

    def test_system_prompt_contains_synthesis_instructions(self, mock_claude_client):
        """System prompt should include narrative synthesis methodology."""
        _configure_mock_response(mock_claude_client, _make_thesis_response())
        agent = ThesisBuilderAgent(mock_claude_client)
        data = make_sample_data_package()
        analysis = _make_sample_analysis()

        agent.run(data, analysis)

        call_args = mock_claude_client.messages.create.call_args
        system = call_args.kwargs["system"][0]["text"]
        assert "recommendation" in system.lower()
        assert "bull" in system.lower()
        assert "bear" in system.lower()
        assert "self-critique" in system.lower() or "self_critique" in system.lower()

    def test_user_prompt_includes_data_and_analysis(self, mock_claude_client):
        """User prompt should include both DataPackage and FinancialAnalysis."""
        _configure_mock_response(mock_claude_client, _make_thesis_response())
        agent = ThesisBuilderAgent(mock_claude_client)
        data = make_sample_data_package()
        analysis = _make_sample_analysis()

        agent.run(data, analysis)

        call_args = mock_claude_client.messages.create.call_args
        user_msg = call_args.kwargs["messages"][0]["content"]
        assert "AAPL" in user_msg
        # Should include analysis results
        assert "BULLISH" in user_msg
        assert "earnings_quality" in user_msg

    def test_system_prompt_contains_disclaimer_requirement(self, mock_claude_client):
        """System prompt should require the disclaimer in outputs."""
        _configure_mock_response(mock_claude_client, _make_thesis_response())
        agent = ThesisBuilderAgent(mock_claude_client)
        data = make_sample_data_package()
        analysis = _make_sample_analysis()

        agent.run(data, analysis)

        call_args = mock_claude_client.messages.create.call_args
        system = call_args.kwargs["system"][0]["text"]
        assert "not financial advice" in system.lower() or "educational" in system.lower()
