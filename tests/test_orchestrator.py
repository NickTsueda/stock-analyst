"""Tests for the Orchestrator agent — pipeline coordination and confidence scoring."""
from unittest.mock import MagicMock, patch, PropertyMock
import pytest

from tests.conftest import make_sample_data_package
from src.models import (
    DataPackage,
    FinancialAnalysis,
    InvestmentThesis,
    InvestmentCase,
    ConfidenceScore,
    ConfidenceDriver,
    ConfidenceLevel,
    LimitationNote,
    Recommendation,
    CompanyType,
    RevisionRequest,
    RevisedAnalysis,
    InsiderActivity,
)
from src.agents.orchestrator import OrchestratorAgent


# --- Fixtures ---


def _make_analysis(**overrides) -> FinancialAnalysis:
    defaults = dict(
        company_type=CompanyType.GROWTH,
        directional_lean="BULLISH",
        directional_rationale="Strong fundamentals",
        earnings_quality=75,
        valuation_clarity=65,
        macro_conditions=60,
        strengths=["Strong brand"],
        concerns=["China exposure"],
    )
    defaults.update(overrides)
    return FinancialAnalysis(**defaults)


def _make_thesis(**overrides) -> InvestmentThesis:
    defaults = dict(
        recommendation=Recommendation.BUY,
        executive_summary="Apple is a buy.",
        bull_case=InvestmentCase("bull", "Upside", ["AI"], 0.30),
        base_case=InvestmentCase("base", "Steady", ["iPhone"], 0.50),
        bear_case=InvestmentCase("bear", "Downside", ["China"], 0.20),
        risks=["China risk"],
        catalysts=["AI integration"],
        confidence=None,
    )
    defaults.update(overrides)
    return InvestmentThesis(**defaults)


@pytest.fixture
def mock_agents():
    """Mock all sub-agents the Orchestrator depends on."""
    data_pkg = make_sample_data_package()
    analysis = _make_analysis()
    thesis = _make_thesis()

    with patch("src.agents.orchestrator.DataCollectorAgent") as MockDC, \
         patch("src.agents.orchestrator.FinancialAnalystAgent") as MockFA, \
         patch("src.agents.orchestrator.ThesisBuilderAgent") as MockTB:

        dc_instance = MockDC.return_value
        dc_instance.run.return_value = data_pkg

        fa_instance = MockFA.return_value
        fa_instance.run.return_value = analysis

        tb_instance = MockTB.return_value
        tb_instance.run.return_value = thesis
        tb_instance.last_confidence_summary = "High confidence overall."
        tb_instance.last_confidence_driver_details = {
            "data_completeness": "All sources available",
            "earnings_quality": "Consistent earnings",
            "valuation_clarity": "Good peer comps",
            "company_predictability": "Stable revenue",
            "insider_signal": "Net selling, routine",
            "macro_conditions": "Mixed signals",
        }

        yield {
            "dc_cls": MockDC,
            "fa_cls": MockFA,
            "tb_cls": MockTB,
            "dc": dc_instance,
            "fa": fa_instance,
            "tb": tb_instance,
            "data_pkg": data_pkg,
            "analysis": analysis,
            "thesis": thesis,
        }


# --- Happy Path Tests ---


class TestOrchestratorPipeline:
    def test_run_returns_three_tuple(self, mock_agents):
        orch = OrchestratorAgent(client=MagicMock())
        data, analysis, thesis = orch.run("AAPL")

        assert data is not None
        assert analysis is not None
        assert thesis is not None

    def test_pipeline_calls_agents_in_order(self, mock_agents):
        orch = OrchestratorAgent(client=MagicMock())
        orch.run("AAPL")

        mock_agents["dc"].run.assert_called_once_with("AAPL")
        mock_agents["fa"].run.assert_called_once_with(mock_agents["data_pkg"])
        mock_agents["tb"].run.assert_called_once()

    def test_thesis_has_confidence_score(self, mock_agents):
        orch = OrchestratorAgent(client=MagicMock())
        _, _, thesis = orch.run("AAPL")

        assert thesis.confidence is not None
        assert isinstance(thesis.confidence, ConfidenceScore)
        assert 0 <= thesis.confidence.score <= 100
        assert len(thesis.confidence.drivers) == 6

    def test_ticker_uppercased(self, mock_agents):
        orch = OrchestratorAgent(client=MagicMock())
        orch.run("aapl")

        mock_agents["dc"].run.assert_called_once_with("AAPL")

    def test_progress_callback_called(self, mock_agents):
        callback = MagicMock()
        orch = OrchestratorAgent(client=MagicMock())
        orch.run("AAPL", progress_callback=callback)

        # Should report at least: data collection, analysis, thesis stages
        assert callback.call_count >= 3
        stages = [call.args[0] for call in callback.call_args_list]
        assert any("data" in s.lower() or "collect" in s.lower() for s in stages)


# --- Data Quality Gate Tests ---


class TestDataQualityGate:
    def test_abort_when_score_below_20(self, mock_agents):
        """Score < 20 → abort, return (DataPackage, None, None)."""
        # DataPackage with no data sources → score = 0
        empty_pkg = DataPackage(ticker="XXXXX", company_name="Unknown")
        mock_agents["dc"].run.return_value = empty_pkg

        orch = OrchestratorAgent(client=MagicMock())
        data, analysis, thesis = orch.run("XXXXX")

        assert data is not None
        assert analysis is None
        assert thesis is None
        # Financial Analyst should NOT have been called
        mock_agents["fa"].run.assert_not_called()

    def test_warn_when_score_20_to_49(self, mock_agents):
        """Score 20-49 → proceed with warning."""
        # Only FRED available → score = 25
        warn_pkg = DataPackage(
            ticker="TEST",
            company_name="Test Co",
            macro=make_sample_data_package().macro,
        )
        mock_agents["dc"].run.return_value = warn_pkg

        orch = OrchestratorAgent(client=MagicMock())
        data, analysis, thesis = orch.run("TEST")

        # Should still proceed
        mock_agents["fa"].run.assert_called_once()
        # Should have added a limitation warning
        has_warning = any(
            "completeness" in w.message.lower() or "incomplete" in w.message.lower()
            for w in data.warnings
        )
        assert has_warning

    def test_proceed_normally_when_score_gte_50(self, mock_agents):
        """Score >= 50 → proceed without extra warnings."""
        orch = OrchestratorAgent(client=MagicMock())
        data, _, _ = orch.run("AAPL")

        assert data.data_completeness_score >= 50
        mock_agents["fa"].run.assert_called_once()


# --- Revision Loop Tests ---


class TestRevisionLoop:
    def test_no_revision_when_no_request(self, mock_agents):
        """No RevisionRequest → no revision calls."""
        mock_agents["thesis"].revision_request = None

        orch = OrchestratorAgent(client=MagicMock())
        orch.run("AAPL")

        mock_agents["fa"].run_revision.assert_not_called()
        mock_agents["tb"].run_with_revision.assert_not_called()

    def test_revision_loop_triggered(self, mock_agents):
        """RevisionRequest → calls FA revision + TB revision."""
        revision_req = RevisionRequest(
            questions=["How sustainable is the margin expansion?"],
            factors_to_reexamine=["earnings_quality"],
            context="Margin trend seems too optimistic",
        )
        initial_thesis = _make_thesis(revision_request=revision_req)
        revised_thesis = _make_thesis(revision_request=None)
        revised_analysis = RevisedAnalysis(
            revised_assessments={"earnings_quality": "Margins are sustainable"},
            revised_subscores={"earnings_quality": 80},
            revision_rationale="Deeper analysis confirms margin sustainability",
        )

        mock_agents["tb"].run.return_value = initial_thesis
        mock_agents["fa"].run_revision.return_value = revised_analysis
        mock_agents["tb"].run_with_revision.return_value = revised_thesis

        orch = OrchestratorAgent(client=MagicMock())
        _, _, thesis = orch.run("AAPL")

        mock_agents["fa"].run_revision.assert_called_once()
        mock_agents["tb"].run_with_revision.assert_called_once()

    def test_revision_timeout_uses_pre_revision_thesis(self, mock_agents):
        """If revision exceeds 30s timeout, use pre-revision thesis."""
        revision_req = RevisionRequest(
            questions=["Check the margins"],
            factors_to_reexamine=["earnings_quality"],
            context="Need deeper look",
        )
        initial_thesis = _make_thesis(
            revision_request=revision_req,
            executive_summary="Pre-revision thesis",
        )
        mock_agents["tb"].run.return_value = initial_thesis

        # Make FA revision raise a timeout
        mock_agents["fa"].run_revision.side_effect = TimeoutError("Revision timed out")

        orch = OrchestratorAgent(client=MagicMock())
        _, _, thesis = orch.run("AAPL")

        # Should use the pre-revision thesis
        assert thesis.executive_summary == "Pre-revision thesis"


# --- Confidence Score Tests ---


class TestConfidenceScore:
    def test_weighted_average_computation(self, mock_agents):
        """Confidence score = weighted average of 6 factors."""
        orch = OrchestratorAgent(client=MagicMock())
        _, _, thesis = orch.run("AAPL")

        cs = thesis.confidence
        # Verify weighted average calculation
        expected = sum(d.score * d.weight for d in cs.drivers)
        assert cs.score == round(expected)

    def test_six_drivers_present(self, mock_agents):
        orch = OrchestratorAgent(client=MagicMock())
        _, _, thesis = orch.run("AAPL")

        driver_names = [d.factor for d in thesis.confidence.drivers]
        assert "Data Completeness" in driver_names
        assert "Earnings Quality" in driver_names
        assert "Valuation Clarity" in driver_names
        assert "Company Predictability" in driver_names
        assert "Insider Signal" in driver_names
        assert "Macro Conditions" in driver_names

    def test_weights_sum_to_one(self, mock_agents):
        orch = OrchestratorAgent(client=MagicMock())
        _, _, thesis = orch.run("AAPL")

        total_weight = sum(d.weight for d in thesis.confidence.drivers)
        assert abs(total_weight - 1.0) < 0.001

    def test_confidence_level_high(self, mock_agents):
        """Score >= 70 → HIGH."""
        # Set all sub-scores high
        mock_agents["data_pkg"].company_predictability_score = 90
        analysis = _make_analysis(
            earnings_quality=90,
            valuation_clarity=90,
            macro_conditions=90,
        )
        mock_agents["fa"].run.return_value = analysis

        orch = OrchestratorAgent(client=MagicMock())
        _, _, thesis = orch.run("AAPL")

        assert thesis.confidence.score >= 70
        assert thesis.confidence.level == ConfidenceLevel.HIGH

    def test_confidence_level_medium(self, mock_agents):
        """Score 40-69 → MEDIUM."""
        analysis = _make_analysis(
            earnings_quality=50,
            valuation_clarity=50,
            macro_conditions=50,
        )
        mock_agents["fa"].run.return_value = analysis
        mock_agents["data_pkg"].company_predictability_score = 50

        orch = OrchestratorAgent(client=MagicMock())
        _, _, thesis = orch.run("AAPL")

        assert 40 <= thesis.confidence.score <= 69
        assert thesis.confidence.level == ConfidenceLevel.MEDIUM

    def test_confidence_level_low(self, mock_agents):
        """Score < 40 → LOW."""
        analysis = _make_analysis(
            earnings_quality=20,
            valuation_clarity=20,
            macro_conditions=20,
        )
        mock_agents["fa"].run.return_value = analysis
        mock_agents["data_pkg"].company_predictability_score = 20
        # Remove insider data → neutral 50, but low enough overall
        mock_agents["data_pkg"].insider_activity = None

        orch = OrchestratorAgent(client=MagicMock())
        _, _, thesis = orch.run("AAPL")

        assert thesis.confidence.score < 40
        assert thesis.confidence.level == ConfidenceLevel.LOW

    def test_guardrail_data_completeness_below_30_caps_at_40(self, mock_agents):
        """If Data Completeness < 30, overall score capped at 40."""
        # Only FRED → score = 25
        warn_pkg = make_sample_data_package(
            market_data=None,
            financials=None,
            filing_text=None,
            macro=make_sample_data_package().macro,
        )
        mock_agents["dc"].run.return_value = warn_pkg

        # Set everything else high to prove the cap works
        analysis = _make_analysis(
            earnings_quality=95,
            valuation_clarity=95,
            macro_conditions=95,
        )
        mock_agents["fa"].run.return_value = analysis

        orch = OrchestratorAgent(client=MagicMock())
        _, _, thesis = orch.run("TEST")

        assert thesis.confidence.score <= 40

    def test_confidence_summary_from_thesis_builder(self, mock_agents):
        """Confidence summary comes from ThesisBuilder's stored attribute."""
        orch = OrchestratorAgent(client=MagicMock())
        _, _, thesis = orch.run("AAPL")

        assert thesis.confidence.summary == "High confidence overall."

    def test_driver_details_from_thesis_builder(self, mock_agents):
        """Driver detail strings come from ThesisBuilder's stored attribute."""
        orch = OrchestratorAgent(client=MagicMock())
        _, _, thesis = orch.run("AAPL")

        details = {d.factor: d.detail for d in thesis.confidence.drivers}
        assert details["Earnings Quality"] == "Consistent earnings"


# --- Insider Signal Heuristic Tests ---


class TestInsiderSignalHeuristic:
    def test_buying_plus_bullish(self, mock_agents):
        """Net buying + BULLISH lean → 80."""
        mock_agents["data_pkg"].insider_activity = InsiderActivity(
            transactions=[{"type": "Purchase"}], net_buys=5, source="edgar"
        )
        analysis = _make_analysis(directional_lean="BULLISH")
        mock_agents["fa"].run.return_value = analysis

        orch = OrchestratorAgent(client=MagicMock())
        _, _, thesis = orch.run("AAPL")

        insider_driver = next(
            d for d in thesis.confidence.drivers if d.factor == "Insider Signal"
        )
        assert insider_driver.score == 80

    def test_buying_plus_neutral(self, mock_agents):
        """Net buying + NEUTRAL lean → 70."""
        mock_agents["data_pkg"].insider_activity = InsiderActivity(
            transactions=[{"type": "Purchase"}], net_buys=3, source="edgar"
        )
        analysis = _make_analysis(directional_lean="NEUTRAL")
        mock_agents["fa"].run.return_value = analysis

        orch = OrchestratorAgent(client=MagicMock())
        _, _, thesis = orch.run("AAPL")

        insider_driver = next(
            d for d in thesis.confidence.drivers if d.factor == "Insider Signal"
        )
        assert insider_driver.score == 70

    def test_buying_plus_bearish(self, mock_agents):
        """Net buying + BEARISH lean → 60 (notable divergence)."""
        mock_agents["data_pkg"].insider_activity = InsiderActivity(
            transactions=[{"type": "Purchase"}], net_buys=2, source="edgar"
        )
        analysis = _make_analysis(directional_lean="BEARISH")
        mock_agents["fa"].run.return_value = analysis

        orch = OrchestratorAgent(client=MagicMock())
        _, _, thesis = orch.run("AAPL")

        insider_driver = next(
            d for d in thesis.confidence.drivers if d.factor == "Insider Signal"
        )
        assert insider_driver.score == 60

    def test_selling_plus_bullish(self, mock_agents):
        """Net selling + BULLISH lean → 35 (concerning divergence)."""
        mock_agents["data_pkg"].insider_activity = InsiderActivity(
            transactions=[{"type": "Sale"}], net_buys=-5, source="edgar"
        )
        analysis = _make_analysis(directional_lean="BULLISH")
        mock_agents["fa"].run.return_value = analysis

        orch = OrchestratorAgent(client=MagicMock())
        _, _, thesis = orch.run("AAPL")

        insider_driver = next(
            d for d in thesis.confidence.drivers if d.factor == "Insider Signal"
        )
        assert insider_driver.score == 35

    def test_selling_plus_neutral(self, mock_agents):
        """Net selling + NEUTRAL lean → 45."""
        mock_agents["data_pkg"].insider_activity = InsiderActivity(
            transactions=[{"type": "Sale"}], net_buys=-3, source="edgar"
        )
        analysis = _make_analysis(directional_lean="NEUTRAL")
        mock_agents["fa"].run.return_value = analysis

        orch = OrchestratorAgent(client=MagicMock())
        _, _, thesis = orch.run("AAPL")

        insider_driver = next(
            d for d in thesis.confidence.drivers if d.factor == "Insider Signal"
        )
        assert insider_driver.score == 45

    def test_selling_plus_bearish(self, mock_agents):
        """Net selling + BEARISH lean → 60 (weak confirmation)."""
        mock_agents["data_pkg"].insider_activity = InsiderActivity(
            transactions=[{"type": "Sale"}], net_buys=-4, source="edgar"
        )
        analysis = _make_analysis(directional_lean="BEARISH")
        mock_agents["fa"].run.return_value = analysis

        orch = OrchestratorAgent(client=MagicMock())
        _, _, thesis = orch.run("AAPL")

        insider_driver = next(
            d for d in thesis.confidence.drivers if d.factor == "Insider Signal"
        )
        assert insider_driver.score == 60

    def test_no_insider_data_neutral(self, mock_agents):
        """No insider data → 50 (neutral)."""
        mock_agents["data_pkg"].insider_activity = None

        orch = OrchestratorAgent(client=MagicMock())
        _, _, thesis = orch.run("AAPL")

        insider_driver = next(
            d for d in thesis.confidence.drivers if d.factor == "Insider Signal"
        )
        assert insider_driver.score == 50

    def test_neutral_insider_activity(self, mock_agents):
        """Net buys == 0 → 50."""
        mock_agents["data_pkg"].insider_activity = InsiderActivity(
            transactions=[{"type": "Purchase"}, {"type": "Sale"}],
            net_buys=0,
            source="edgar",
        )

        orch = OrchestratorAgent(client=MagicMock())
        _, _, thesis = orch.run("AAPL")

        insider_driver = next(
            d for d in thesis.confidence.drivers if d.factor == "Insider Signal"
        )
        assert insider_driver.score == 50


# --- Error Handling Tests ---


class TestErrorHandling:
    def test_financial_analyst_failure_returns_partial(self, mock_agents):
        """If FA fails, return (DataPackage, None, None)."""
        mock_agents["fa"].run.side_effect = Exception("Claude API error")

        orch = OrchestratorAgent(client=MagicMock())
        data, analysis, thesis = orch.run("AAPL")

        assert data is not None
        assert analysis is None
        assert thesis is None

    def test_thesis_builder_failure_returns_partial(self, mock_agents):
        """If TB fails, return (DataPackage, FinancialAnalysis, None)."""
        mock_agents["tb"].run.side_effect = Exception("Claude API error")

        orch = OrchestratorAgent(client=MagicMock())
        data, analysis, thesis = orch.run("AAPL")

        assert data is not None
        assert analysis is not None
        assert thesis is None

    def test_data_collector_failure_returns_empty_package(self, mock_agents):
        """If DC fails entirely, return empty DataPackage with error."""
        mock_agents["dc"].run.side_effect = Exception("All data sources failed")

        orch = OrchestratorAgent(client=MagicMock())
        data, analysis, thesis = orch.run("AAPL")

        assert data is not None
        assert analysis is None
        assert thesis is None

    def test_revision_failure_uses_pre_revision_thesis(self, mock_agents):
        """If revision loop fails, use the pre-revision thesis."""
        revision_req = RevisionRequest(
            questions=["Check margins"],
            factors_to_reexamine=["earnings_quality"],
            context="Need deeper look",
        )
        initial_thesis = _make_thesis(
            revision_request=revision_req,
            executive_summary="Original thesis",
        )
        mock_agents["tb"].run.return_value = initial_thesis
        mock_agents["fa"].run_revision.side_effect = Exception("Revision failed")

        orch = OrchestratorAgent(client=MagicMock())
        _, _, thesis = orch.run("AAPL")

        assert thesis.executive_summary == "Original thesis"
