"""Thesis Builder Agent — narrative synthesis with self-critique and revision support.

Takes a DataPackage + FinancialAnalysis and produces an InvestmentThesis with:
- BUY/HOLD/SELL recommendation (12-month forward outlook)
- Executive summary, bull/base/bear cases with probabilities
- Peer comparison, forward outlook, risks, catalysts
- Macro context, insider summary
- Self-critique → optional RevisionRequest for the Financial Analyst
- Qualitative confidence details for Orchestrator post-processing

Also supports run_with_revision() to incorporate RevisedAnalysis from the revision loop.
"""
from __future__ import annotations

import json
import logging

from src.agents.base import BaseAgent
from src.models import (
    DataPackage,
    FinancialAnalysis,
    InvestmentCase,
    InvestmentThesis,
    Recommendation,
    RevisionRequest,
    RevisedAnalysis,
)

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a senior investment strategist at a top-tier research firm. You will receive structured \
financial data AND a completed financial analysis for a public company. Your job is to synthesize \
everything into a clear, actionable investment thesis with a 12-month forward outlook.

## Core Principles

1. **Synthesis, not repetition.** The Financial Analyst has already computed the numbers and \
identified trends. Your job is to interpret what they MEAN for an investor. Do not restate the \
analysis — synthesize it into a narrative that answers: "Should I buy, hold, or sell this stock \
over the next 12 months, and why?"

2. **Evidence-weighted recommendation.** Your recommendation must reflect the balance of evidence. \
If the analyst's directional lean is BULLISH but with significant concerns, a cautious BUY or HOLD \
is more honest than a strong BUY. Never force a narrative — let the evidence speak.

3. **Probability-calibrated scenarios.** Bull/base/bear probabilities must reflect genuine \
uncertainty. If you assign >60% to any single scenario, explain why the situation is so clear-cut. \
The three probabilities MUST sum to exactly 100%.

4. **Forward-looking, not backward-looking.** The executive summary and recommendation should be \
about the NEXT 12 months, not a summary of what happened. Historical data is context, not conclusion.

5. **Honest about limitations.** If data is missing, the analysis is thin, or the situation is \
genuinely uncertain, say so. A thesis that acknowledges its weak spots is more useful than one \
that papers over them.

## Thesis Construction

### Executive Summary (2-3 paragraphs)
Write a forward-looking investment narrative that:
- Opens with the core investment thesis (1-2 sentences): why own or avoid this stock?
- Explains the primary growth/value driver and how it creates shareholder value
- Addresses the biggest risk and why it is or isn't a dealbreaker
- Grounds every claim in a specific metric from the analysis (not vague qualitative assertions)

### Recommendation
Choose BUY, HOLD, or SELL for a 12-month horizon:
- **BUY:** The risk/reward is favorable. Expected return exceeds the market, or a clear catalyst \
will unlock value within 12 months.
- **HOLD:** The stock is fairly valued. No compelling reason to add or reduce exposure. OR the \
situation is too uncertain to make a directional call.
- **SELL:** The risk/reward is unfavorable. Overvalued relative to peers and growth prospects, \
or identifiable headwinds will likely drag the stock.

Do not default to HOLD as a safe answer. If the evidence leans directional, make the call.

### Bull / Base / Bear Cases
For each scenario:
- 2-4 sentence narrative of what happens
- 3-4 specific, concrete drivers (not generic platitudes)
- Probability (must sum to 100%)

Guidance on probabilities:
- Base case should typically be 40-60% (it's the most likely outcome by definition)
- Bull and bear should typically be 15-35% each
- Extreme splits (e.g., 10/80/10) are rare — most situations have meaningful uncertainty

### Peer Comparison Narrative
How does this company stack up against its peers? Focus on:
- Valuation premium/discount and whether it's justified
- Relative growth and margin positioning
- What would the stock be worth at peer median multiples?

### Forward Outlook
Specific, time-bound outlook for the next 12 months:
- Revenue and margin trajectory
- Key catalysts with timing
- Key risks with probability assessment

### Risks & Catalysts
- 3-5 specific risks (not generic), ranked by potential impact
- 3-5 specific catalysts (not generic), ranked by probability

### Macro Context
How do current macro conditions (rates, GDP, inflation, yield curve) affect this specific company?

### Insider Summary
Interpret insider activity in context — is it routine compensation management or a directional signal?

## Self-Critique

After completing the thesis, step back and ask yourself:
1. What are the weakest assumptions in this thesis?
2. What contradictions did I gloss over?
3. What would a skeptical analyst challenge?

If you identify SUBSTANTIVE gaps (not cosmetic or stylistic), set `requires_revision` to true \
and provide 1-3 specific questions for the Financial Analyst to re-examine. Substantive gaps include:
- A key risk that isn't quantified
- Contradictory signals that weren't resolved
- A critical assumption with no supporting evidence
- Missing analysis on a factor that could change the recommendation

Do NOT request revision for:
- Minor wording improvements
- Additional detail that wouldn't change the conclusion
- Cosmetic gaps

## Confidence Details

Provide qualitative details for the confidence scoring system. You do NOT compute numeric scores — \
that happens in post-processing. Your job is to explain, in plain English, how each factor \
affects analytical confidence.

For each of the 6 factors, write a 1-2 sentence explanation of its impact:
- data_completeness: How complete is the data we're working with?
- earnings_quality: How coherent and trustworthy is the earnings picture?
- valuation_clarity: How clearly can we assess fair value?
- company_predictability: How predictable is this business?
- insider_signal: What does insider activity tell us (or not)?
- macro_conditions: How clear is the macro environment for this sector?

Also provide a 1-2 sentence confidence_summary that captures the overall analytical confidence.

## Output Format

Respond with a single JSON object (no markdown fencing):
{
  "recommendation": "BUY|HOLD|SELL",
  "executive_summary": "2-3 paragraph forward-looking thesis...",
  "bull_case": {
    "narrative": "...",
    "drivers": ["driver 1", "driver 2", "driver 3"],
    "probability": 0.25
  },
  "base_case": {
    "narrative": "...",
    "drivers": ["driver 1", "driver 2", "driver 3"],
    "probability": 0.55
  },
  "bear_case": {
    "narrative": "...",
    "drivers": ["driver 1", "driver 2", "driver 3"],
    "probability": 0.20
  },
  "peer_comparison_narrative": "...",
  "forward_outlook": "...",
  "risks": ["risk 1", "risk 2", ...],
  "catalysts": ["catalyst 1", "catalyst 2", ...],
  "macro_context": "...",
  "insider_summary": "...",
  "confidence_summary": "1-2 sentence overall confidence summary",
  "confidence_driver_details": {
    "data_completeness": "...",
    "earnings_quality": "...",
    "valuation_clarity": "...",
    "company_predictability": "...",
    "insider_signal": "...",
    "macro_conditions": "..."
  },
  "self_critique": {
    "weakest_assumptions": ["assumption 1", ...],
    "contradictions": ["contradiction 1", ...],
    "gaps": ["gap 1", ...],
    "requires_revision": false,
    "revision_questions": [],
    "revision_factors": [],
    "revision_context": ""
  }
}

CRITICAL INSTRUCTIONS:
- Every claim in the executive summary must reference a specific metric or data point.
- Probabilities for bull/base/bear MUST sum to exactly 1.0.
- The recommendation must be consistent with the weight of evidence and the base case scenario.
- If the analyst's directional lean and your recommendation diverge, explain why in the executive summary.
- This analysis is for educational purposes only. It is not financial advice.
"""

_REVISION_SYSTEM_PROMPT = """\
You are a senior investment strategist revising an investment thesis based on new analysis. \
The Financial Analyst has re-examined specific areas at your request and provided updated \
assessments. Incorporate these revisions into an improved thesis.

Key rules:
- Integrate the revised assessments naturally — don't just append them
- Adjust probabilities and recommendation if the new information warrants it
- Maintain the same output format as the initial thesis
- Do NOT include a self_critique section — revision is one-and-done
- Probabilities for bull/base/bear MUST sum to exactly 1.0
- This analysis is for educational purposes only. It is not financial advice.

Respond with a single JSON object (no markdown fencing) with the same structure as the initial \
thesis, minus the self_critique section. Include confidence_summary and confidence_driver_details.
"""


class ThesisBuilderAgent(BaseAgent):
    """Synthesizes financial analysis into an investment thesis with self-critique.

    Extends BaseAgent for Claude calling infrastructure.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Store qualitative confidence details for Orchestrator post-processing
        self.last_confidence_summary: str = ""
        self.last_confidence_driver_details: dict[str, str] = {}

    def run(self, data: DataPackage, analysis: FinancialAnalysis) -> InvestmentThesis:
        """Synthesize data and analysis into an investment thesis.

        Includes self-critique — may produce a RevisionRequest if substantive
        gaps are identified.

        Args:
            data: Complete DataPackage from the Data Collector.
            analysis: FinancialAnalysis from the Financial Analyst.

        Returns:
            InvestmentThesis with optional RevisionRequest for revision loop.
        """
        user_prompt = self._build_user_prompt(data, analysis)
        logger.info("Running Thesis Builder for %s", data.ticker)

        result = self._call_claude(
            system=_SYSTEM_PROMPT,
            user=user_prompt,
            max_tokens=4096,
        )

        if not result:
            logger.warning("Empty response from Claude for %s, returning defaults", data.ticker)
            return InvestmentThesis()

        return self._parse_thesis(result)

    def run_with_revision(
        self,
        data: DataPackage,
        analysis: FinancialAnalysis,
        revised: RevisedAnalysis,
    ) -> InvestmentThesis:
        """Produce an updated thesis incorporating revised analysis.

        Called by the Orchestrator after the Financial Analyst has re-examined
        specific aspects. Uses a shorter system prompt (no self-critique needed).

        Args:
            data: Original DataPackage.
            analysis: Original FinancialAnalysis.
            revised: RevisedAnalysis from the Financial Analyst's revision.

        Returns:
            Updated InvestmentThesis (no RevisionRequest — revision is one-and-done).
        """
        user_prompt = self._build_revision_user_prompt(data, analysis, revised)
        logger.info("Running Thesis Builder revision for %s", data.ticker)

        result = self._call_claude(
            system=_REVISION_SYSTEM_PROMPT,
            user=user_prompt,
            max_tokens=4096,
        )

        if not result:
            logger.warning("Empty revision response for %s", data.ticker)
            return InvestmentThesis()

        # Parse without self-critique (revision doesn't trigger another round)
        return self._parse_thesis(result, allow_revision=False)

    def _parse_thesis(self, raw: dict, allow_revision: bool = True) -> InvestmentThesis:
        """Parse Claude's JSON response into an InvestmentThesis dataclass."""
        # Parse recommendation with fallback
        try:
            recommendation = Recommendation(raw.get("recommendation", "HOLD"))
        except ValueError:
            recommendation = Recommendation.HOLD

        # Parse investment cases
        bull_case = self._parse_case(raw.get("bull_case", {}), "bull")
        base_case = self._parse_case(raw.get("base_case", {}), "base")
        bear_case = self._parse_case(raw.get("bear_case", {}), "bear")

        # Parse self-critique → RevisionRequest
        revision_request = None
        if allow_revision:
            critique = raw.get("self_critique", {})
            if critique.get("requires_revision", False):
                questions = critique.get("revision_questions", [])
                if questions:
                    revision_request = RevisionRequest(
                        questions=questions[:3],  # Cap at 3 per design
                        factors_to_reexamine=critique.get("revision_factors", []),
                        context=critique.get("revision_context", ""),
                    )

        # Store confidence details for Orchestrator
        self.last_confidence_summary = raw.get("confidence_summary", "")
        self.last_confidence_driver_details = raw.get("confidence_driver_details", {})

        return InvestmentThesis(
            recommendation=recommendation,
            executive_summary=raw.get("executive_summary", ""),
            bull_case=bull_case,
            base_case=base_case,
            bear_case=bear_case,
            peer_comparison_narrative=raw.get("peer_comparison_narrative", ""),
            forward_outlook=raw.get("forward_outlook", ""),
            risks=raw.get("risks", []),
            catalysts=raw.get("catalysts", []),
            macro_context=raw.get("macro_context", ""),
            insider_summary=raw.get("insider_summary", ""),
            confidence=None,  # Computed by Orchestrator post-processing
            revision_request=revision_request,
        )

    def _parse_case(self, raw: dict, scenario: str) -> InvestmentCase | None:
        """Parse a single investment case from Claude's response."""
        if not raw:
            return None
        return InvestmentCase(
            scenario=scenario,
            narrative=raw.get("narrative", ""),
            drivers=raw.get("drivers", []),
            probability=float(raw.get("probability", 0.0)),
        )

    def _build_user_prompt(self, data: DataPackage, analysis: FinancialAnalysis) -> str:
        """Build the user prompt with both raw data and analysis results."""
        sections = [
            "# Investment Thesis Request",
            f"\nAnalyze {data.ticker} ({data.company_name}) and produce a complete "
            "investment thesis with a 12-month forward outlook.",
        ]

        # Include raw data for context
        sections.append("\n## Raw Financial Data")
        sections.append(data.to_prompt_text())

        # Include the Financial Analyst's analysis
        sections.append("\n## Financial Analyst's Assessment")
        analysis_dict = analysis.to_dict()
        sections.append(f"\n### Company Type: {analysis_dict['company_type']}")
        sections.append(f"\n### Directional Lean: {analysis_dict['directional_lean']}")
        sections.append(f"Rationale: {analysis_dict['directional_rationale']}")

        sections.append("\n### Profitability")
        sections.append(json.dumps(analysis_dict["profitability"], indent=2))

        sections.append("\n### Growth")
        sections.append(json.dumps(analysis_dict["growth"], indent=2))

        sections.append("\n### Balance Sheet Health")
        sections.append(json.dumps(analysis_dict["balance_sheet_health"], indent=2))

        sections.append("\n### Cash Flow Quality")
        sections.append(json.dumps(analysis_dict["cash_flow_quality"], indent=2))

        if analysis_dict.get("peer_comparison"):
            sections.append("\n### Peer Comparison")
            sections.append(json.dumps(analysis_dict["peer_comparison"], indent=2))

        sections.append("\n### Forward Outlook")
        sections.append(json.dumps(analysis_dict["forward_outlook"], indent=2))

        sections.append(f"\n### Macro Impact\n{analysis_dict['macro_impact']}")
        sections.append(f"\n### Insider Interpretation\n{analysis_dict['insider_interpretation']}")

        sections.append("\n### Strengths")
        for s in analysis_dict.get("strengths", []):
            sections.append(f"- {s}")

        sections.append("\n### Concerns")
        for c in analysis_dict.get("concerns", []):
            sections.append(f"- {c}")

        # Include confidence sub-scores so the thesis can reference them
        sections.append("\n### Analyst Confidence Sub-Scores")
        sections.append(f"- earnings_quality: {analysis.earnings_quality}/100")
        sections.append(f"- valuation_clarity: {analysis.valuation_clarity}/100")
        sections.append(f"- macro_conditions: {analysis.macro_conditions}/100")

        return "\n".join(sections)

    def _build_revision_user_prompt(
        self,
        data: DataPackage,
        analysis: FinancialAnalysis,
        revised: RevisedAnalysis,
    ) -> str:
        """Build the user prompt for a revised thesis."""
        sections = [
            "# Revised Investment Thesis Request",
            f"\nRevise the investment thesis for {data.ticker} ({data.company_name}) "
            "incorporating the Financial Analyst's updated assessment below.",
        ]

        # Include the revised analysis prominently
        sections.append("\n## Revised Analysis (NEW — integrate this)")
        sections.append(f"\n### Revision Rationale\n{revised.revision_rationale}")

        sections.append("\n### Updated Assessments")
        for topic, assessment in revised.revised_assessments.items():
            sections.append(f"\n**{topic}:** {assessment}")

        if revised.revised_subscores:
            sections.append("\n### Updated Confidence Sub-Scores")
            for score_name, value in revised.revised_subscores.items():
                sections.append(f"- {score_name}: {value}/100")

        # Include original context
        sections.append("\n## Original Data (for reference)")
        sections.append(data.to_prompt_text())

        sections.append("\n## Original Financial Analysis (for reference)")
        sections.append(f"Directional Lean: {analysis.directional_lean}")
        sections.append(f"Rationale: {analysis.directional_rationale}")
        sections.append(f"Earnings Quality: {analysis.earnings_quality}/100")
        sections.append(f"Valuation Clarity: {analysis.valuation_clarity}/100")
        sections.append(f"Macro Conditions: {analysis.macro_conditions}/100")

        return "\n".join(sections)
