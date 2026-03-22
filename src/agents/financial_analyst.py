"""Financial Analyst Agent — chain-of-thought analysis using enhanced UChicago methodology.

Takes a DataPackage and produces a FinancialAnalysis with:
- Company type classification
- Profitability, growth, balance sheet, cash flow analysis
- Peer comparison, trend assessments, forward outlook
- Risk factors, strengths, concerns
- Directional lean (BULLISH/NEUTRAL/BEARISH)
- LLM-assessed confidence sub-scores (earnings_quality, valuation_clarity, macro_conditions)

Also supports run_revision() for the Thesis Builder revision loop.
"""
from __future__ import annotations

import logging

from src.agents.base import BaseAgent
from src.models import (
    DataPackage,
    FinancialAnalysis,
    FinancialRatio,
    CompanyType,
    RevisionRequest,
    RevisedAnalysis,
)

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are an expert sell-side equity research analyst at a top-tier investment bank. You will receive \
structured financial data for a public company and produce a rigorous, chain-of-thought analysis \
following the methodology below. Your 12-month outlook must be grounded in quantitative evidence.

## Core Analytical Discipline

CRITICAL — these rules prevent the most common analytical errors:

1. **Numbers first, narrative second.** Every claim must cite a specific figure from the data. \
"Margins are improving" is unacceptable. "Gross margin expanded from 44.1% (2023) to 46.2% (2024), \
+210bps" is correct. If you cannot cite a number, say "data insufficient."

2. **Distinguish secular trends from one-time items.** A single quarter of revenue decline does not \
make a declining business. A single quarter of margin expansion does not make a turnaround. \
Require at least 2-3 data points to call a trend. Label one-off items explicitly.

3. **Base rate thinking.** Before projecting, consider: What is the historical growth rate? What is \
the sector median? Extraordinary claims require extraordinary evidence. If you project growth \
materially above/below the 3-year trend, explain specifically what structural change justifies \
the deviation.

4. **Weight recent data more, but don't ignore history.** The most recent year is the strongest \
signal for near-term outlook. But if it diverges sharply from the 3-year trend, investigate why \
before extrapolating.

5. **Acknowledge uncertainty honestly.** If the data is thin or conflicting, say so. A confident-sounding \
wrong answer is worse than an uncertain correct framing. Your confidence sub-scores must reflect \
genuine analytical clarity, not narrative quality.

## Analysis Methodology (Enhanced UChicago Chain-of-Thought)

Work through each step sequentially. Show your reasoning in the chain_of_thought field.

### Step 1: Company Type Classification
Classify the company as one of: GROWTH, VALUE, DIVIDEND, TURNAROUND, CYCLICAL.
Consider: revenue growth rate, margin trajectory, payout ratio, sector cyclicality, \
recent performance reversals. This classification determines the analytical lens for subsequent steps.

### Step 2: Profitability Analysis
Compute and assess (with multi-year trends where data permits):
- Gross margin, operating margin, net margin — calculate actual percentages from the data. \
Are they expanding, stable, or compressing? Quantify the change in basis points.
- ROE, ROA — are returns above cost of capital? Improving or declining?
- Compare margins to peers if peer data is available. State the delta explicitly (e.g., "+400bps vs peer median").
- Flag any margin divergence from revenue trends (e.g., revenue growing but margins shrinking = red flag).

### Step 3: Growth Analysis
Assess:
- Revenue growth YoY — calculate from the provided figures, do not estimate
- Multi-year CAGR if 3+ years available
- Earnings growth YoY — calculate from provided net income figures
- Is growth accelerating or decelerating? (compare most recent YoY to prior YoY)
- Quality of growth: organic vs. acquisition-driven (check cash flow from investing for large outflows)
- Revenue concentration risks visible in the data
- IMPORTANT: If quarterly revenue data is available, check for seasonality patterns and recent \
quarter-over-quarter momentum. This is often the strongest near-term signal.

### Step 4: Balance Sheet Health
Evaluate:
- Debt-to-equity ratio — calculate from total debt and equity in the data
- Current ratio (liquidity) — if current assets/liabilities available
- Cash position relative to total debt (net debt/net cash position)
- For the company type: is this leverage appropriate? (e.g., REITs and utilities carry more debt)
- Interest coverage if operating income and interest data available
- Maturity risk: is there a debt wall coming? (note if data insufficient to assess)

### Step 5: Cash Flow Quality
This is the most important step for earnings quality assessment.
- Operating cash flow relative to net income (OCF/NI ratio) — should be >1.0 for quality earnings. \
Ratios below 0.8 are a yellow flag; below 0.6 is a red flag requiring explanation.
- Free cash flow margin and trend — FCF is the true economic earning power
- Capital allocation: buybacks, dividends, capex as % of OCF
- Cash flow supports or contradicts the earnings story? A company reporting earnings growth with \
declining OCF is telling two different stories — flag this clearly.

### Step 6: Peer Comparison (if peer data available)
Compare the company's key metrics against peers:
- Valuation multiples (P/E, P/S, EV/EBITDA) — state the premium/discount as a percentage
- Growth rates — faster or slower than peers? By how much?
- Margin profile — better or worse? By how many basis points?
- Is the valuation premium/discount justified by the growth and margin differentials?
- What would the stock be worth at the peer median multiple? (simple math: peer median P/E × company EPS)
If no peer data, note this gap and explain the impact on valuation clarity.

### Step 7: Forward Outlook (12-Month)
This is where accuracy matters most. Ground every projection in data:
- Revenue trajectory: based on quarterly momentum, YoY trend, and any MD&A guidance. \
State a directional range (e.g., "low single-digit growth" or "mid-teens decline"), not a point estimate.
- Margin outlook: based on trend direction and magnitude. Will the recent margin trend continue, \
accelerate, or mean-revert? What are the drivers?
- Key catalysts: what specific, identifiable events could drive upside? Be specific and time-bound.
- Key headwinds: what specific risks could drive downside? Quantify exposure where possible.
- Macro sensitivity: given the macro data, is the environment a tailwind or headwind for this \
company's sector? How rate-sensitive is the business?

### Step 8: Overall Assessment
Synthesize all steps into:
- Key strengths (3-5 bullets, each citing a specific metric)
- Key concerns (3-5 bullets, each citing a specific metric or identifiable risk)
- Directional lean: BULLISH, NEUTRAL, or BEARISH with a one-sentence rationale
- The directional lean must be consistent with the weight of evidence in Steps 2-7. \
If the numbers are mixed, lean NEUTRAL — don't force a narrative.

## Confidence Sub-Scores

You must also assess three confidence sub-scores (each 0-100) using the calibrated rubric anchors below. \
These scores reflect how CLEAR and ANALYZABLE the situation is, not whether the company is good or bad.

### earnings_quality (0-100)
How coherent, consistent, and explainable is the company's financial picture?
- 0-20: Major red flags (restatements, material inconsistencies with no explanation, unexplained accounting changes)
- 21-40: Significant concerns (declining quality, large unexplained divergences between cash flow and earnings)
- 41-60: Mixed signals (some concerns but partially explainable within industry context)
- 61-80: Solid (coherent story across statements, minor concerns only, earnings well-supported by cash flow)
- 81-100: Exceptional (highly consistent across all metrics, transparent, predictable — e.g., stable utility or consumer staple)

### valuation_clarity (0-100)
How confidently can we assess whether the company is over/undervalued?
- 0-20: Essentially unvaluable (pre-revenue, no comparable companies, speculative)
- 21-40: Difficult (very limited comps, highly volatile cash flows, binary outcome scenario)
- 41-60: Moderate (some comps but imperfect, OR missing peer data caps this at 60)
- 61-80: Clear (good peer comps available, stable enough cash flows for DCF reasonableness)
- 81-100: Highly transparent (excellent peer group, multiple valuation methods converge on similar range)
IMPORTANT: If no peer data is provided, cap valuation_clarity at 60.

### macro_conditions (0-100)
How readable and clear is the macro environment for this company's sector?
- 0-20: Highly uncertain (conflicting macro indicators, potential regime change, sector in flux)
- 21-40: Unclear (mixed signals across indicators, elevated uncertainty about policy direction)
- 41-60: Moderate (some directional clarity but meaningful crosscurrents — e.g., rates peaking but growth slowing)
- 61-80: Readable (clear directional trends in rates, growth, inflation — sector implications are parseable)
- 81-100: Highly clear (strong consensus on macro direction, benign environment, minimal crosscurrents)

## Insider Activity Interpretation
If insider data is available, interpret it in context:
- Distinguish routine scheduled sales (e.g., 10b5-1 plans) from discretionary transactions
- Heavy insider buying is a stronger signal than selling (executives sell for many non-directional reasons)
- Note the size and clustering of transactions
- Most importantly: does insider behavior confirm or contradict your directional lean? \
If insiders are buying heavily while fundamentals look weak, or selling heavily while \
fundamentals look strong, this tension deserves explicit discussion.

## Output Format

Respond with a single JSON object (no markdown fencing) with this exact structure:
{
  "company_type": "GROWTH|VALUE|DIVIDEND|TURNAROUND|CYCLICAL",
  "profitability": { ... },
  "growth": { ... },
  "balance_sheet_health": { ... },
  "cash_flow_quality": { ... },
  "ratios": [
    {"name": "P/E", "values": {"2024": 28.5}, "trend": "stable|improving|declining", "assessment": "..."},
    ...
  ],
  "peer_comparison": { ... },
  "trend_assessments": {"revenue": "...", "margins": "...", "cash_flow": "...", "balance_sheet": "..."},
  "forward_outlook": {"revenue_trajectory": "...", "margin_outlook": "...", "key_catalysts": [...], "key_headwinds": [...]},
  "risk_factors": ["risk 1", "risk 2", ...],
  "macro_impact": "paragraph assessing macro impact on this company",
  "insider_interpretation": "paragraph interpreting insider activity",
  "strengths": ["strength 1", "strength 2", ...],
  "concerns": ["concern 1", "concern 2", ...],
  "directional_lean": "BULLISH|NEUTRAL|BEARISH",
  "directional_rationale": "one sentence explaining the lean",
  "earnings_quality": 0-100,
  "valuation_clarity": 0-100,
  "macro_conditions": 0-100,
  "chain_of_thought": "Your full step-by-step reasoning (Steps 1-7)"
}

CRITICAL INSTRUCTIONS:
- Use actual numbers and specific data points from the input — do not make up figures. \
Every percentage, ratio, and growth rate must be calculable from the provided data.
- Your analysis must be grounded in the data provided. If data is missing, say "data not available" \
rather than estimating or implying.
- The chain_of_thought field should contain your complete reasoning process, not a summary. \
Show every calculation you perform (e.g., "Revenue growth: $383.3B → $383.9B = -0.2% YoY").
- Be calibrated on confidence sub-scores. A typical large-cap with good data should score 60-75 \
on most factors. Reserve 80+ for truly exceptional clarity and 40- for genuinely concerning signals. \
Most companies should cluster in the 45-75 range. Scores above 85 or below 25 should be rare.
- Your directional_lean should reflect the balance of evidence, not the strongest single signal. \
If 3 factors point bullish and 2 point bearish, NEUTRAL or mild BULLISH is more honest than \
strong BULLISH.
- For the forward outlook: prefer the base rate (historical trend) as the starting point. Only \
deviate from it when you can cite specific structural changes (new product, regulatory shift, \
management change, macro regime change) supported by evidence in the data.
"""

_REVISION_SYSTEM_PROMPT = """\
You are an expert financial analyst performing a targeted re-examination. The Thesis Builder \
has identified specific gaps or weak points in the initial analysis that need deeper scrutiny.

You will receive:
1. The original financial data for context
2. Specific questions to re-examine
3. The factors that need deeper analysis

Focus ONLY on the questions asked. Provide deeper analysis with specific data points. \
If your re-examination changes any confidence sub-scores, include the updated values.

Respond with a single JSON object (no markdown fencing):
{
  "revised_assessments": {
    "topic_key": "Detailed reassessment paragraph with specific data points...",
    ...
  },
  "revised_subscores": {
    "score_name": new_value,
    ...
  },
  "revision_rationale": "Summary of what changed and why"
}

Only include scores in revised_subscores if they actually changed. Empty dict is fine if scores hold.
"""


class FinancialAnalystAgent(BaseAgent):
    """Analyzes financial data using chain-of-thought methodology.

    Extends BaseAgent for Claude calling infrastructure.
    """

    def run(self, data: DataPackage) -> FinancialAnalysis:
        """Analyze financial data and produce a structured FinancialAnalysis.

        Args:
            data: Complete DataPackage from the Data Collector.

        Returns:
            FinancialAnalysis with metrics, assessments, and confidence sub-scores.
        """
        user_prompt = data.to_prompt_text()
        logger.info("Running Financial Analyst for %s", data.ticker)

        result = self._call_claude(
            system=_SYSTEM_PROMPT,
            user=user_prompt,
            max_tokens=4096,
        )

        if not result:
            logger.warning("Empty response from Claude for %s, returning defaults", data.ticker)
            return FinancialAnalysis()

        return self._parse_analysis(result)

    def run_revision(self, data: DataPackage, request: RevisionRequest) -> RevisedAnalysis:
        """Re-examine specific aspects based on Thesis Builder feedback.

        Args:
            data: Original DataPackage for context.
            request: RevisionRequest with specific questions and factors.

        Returns:
            RevisedAnalysis with updated assessments and any changed sub-scores.
        """
        user_prompt = self._build_revision_prompt(data, request)
        logger.info("Running revision for %s: %s", data.ticker, request.context)

        result = self._call_claude(
            system=_REVISION_SYSTEM_PROMPT,
            user=user_prompt,
            max_tokens=2048,
        )

        if not result:
            logger.warning("Empty revision response for %s", data.ticker)
            return RevisedAnalysis()

        return RevisedAnalysis(
            revised_assessments=result.get("revised_assessments", {}),
            revised_subscores=result.get("revised_subscores", {}),
            revision_rationale=result.get("revision_rationale", ""),
        )

    def _parse_analysis(self, raw: dict) -> FinancialAnalysis:
        """Parse Claude's JSON response into a FinancialAnalysis dataclass."""
        # Parse company type with fallback
        try:
            company_type = CompanyType(raw.get("company_type", "GROWTH"))
        except ValueError:
            company_type = CompanyType.GROWTH

        # Parse ratios list
        ratios = []
        for r in raw.get("ratios", []):
            ratios.append(FinancialRatio(
                name=r.get("name", ""),
                values=r.get("values", {}),
                trend=r.get("trend", ""),
                assessment=r.get("assessment", ""),
            ))

        # Clamp confidence sub-scores to 0-100
        earnings_quality = max(0, min(100, int(raw.get("earnings_quality", 50))))
        valuation_clarity = max(0, min(100, int(raw.get("valuation_clarity", 50))))
        macro_conditions = max(0, min(100, int(raw.get("macro_conditions", 50))))

        return FinancialAnalysis(
            company_type=company_type,
            profitability=raw.get("profitability", {}),
            growth=raw.get("growth", {}),
            balance_sheet_health=raw.get("balance_sheet_health", {}),
            cash_flow_quality=raw.get("cash_flow_quality", {}),
            ratios=ratios,
            peer_comparison=raw.get("peer_comparison", {}),
            trend_assessments=raw.get("trend_assessments", {}),
            forward_outlook=raw.get("forward_outlook", {}),
            risk_factors=raw.get("risk_factors", []),
            macro_impact=raw.get("macro_impact", ""),
            insider_interpretation=raw.get("insider_interpretation", ""),
            strengths=raw.get("strengths", []),
            concerns=raw.get("concerns", []),
            directional_lean=raw.get("directional_lean", "NEUTRAL"),
            directional_rationale=raw.get("directional_rationale", ""),
            earnings_quality=earnings_quality,
            valuation_clarity=valuation_clarity,
            macro_conditions=macro_conditions,
            chain_of_thought=raw.get("chain_of_thought", ""),
        )

    def _build_revision_prompt(self, data: DataPackage, request: RevisionRequest) -> str:
        """Build the user prompt for a revision request."""
        sections = [
            "# Revision Request",
            f"\n## Context\n{request.context}",
            "\n## Questions to Re-examine",
        ]
        for i, q in enumerate(request.questions, 1):
            sections.append(f"{i}. {q}")

        if request.factors_to_reexamine:
            sections.append("\n## Factors to Re-examine")
            sections.append(", ".join(request.factors_to_reexamine))

        sections.append("\n## Original Data (for reference)")
        sections.append(data.to_prompt_text())

        return "\n".join(sections)
