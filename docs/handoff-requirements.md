# Handoff: Requirements Phase

**Date:** 2026-03-14
**Status:** Complete
**Next phase:** Design → Implementation Planning

---

## What Was Done

Completed the full PRD through collaborative brainstorming and iterative review. The spec covers 7 sections: Product Overview, User Journey, Agent Architecture, Data Sources, Confidence Score, Technical Constraints, and V2 Considerations.

**Spec location:** `docs/superpowers/specs/2026-03-14-prd-design.md`

## Key Decisions Made

### Product Scope
- **US public equities only** (V1) — clean scope where all data sources work reliably
- **Graceful degradation** over strict gatekeeping — analyze with whatever data is available, let the Confidence Score communicate uncertainty
- **Synchronous with streaming** — user sees agents work in real-time (45–120 seconds)
- **Always fresh** — no caching in V1, every analysis hits APIs from scratch
- **Hybrid dashboard/report** output — quick-glance dashboard on top, expandable detailed sections below

### Architecture
- **4-agent pipeline:** Orchestrator → Data Collector → Financial Analyst → Thesis Builder
- **Two separate LLM calls** (Analyst for quantitative reasoning, Thesis Builder for narrative synthesis)
- **Revision loop:** Thesis Builder self-critiques and sends targeted questions back to the Financial Analyst (max 1 iteration, 30s timeout). This was originally a V2 feature but was pulled into V1 because single-pass analysis is the #1 weakness vs real analyst workflows.

### Confidence Score (6 factors)
| Factor | Weight | Computed By |
|---|---|---|
| Data Completeness | 20% | Orchestrator (programmatic) |
| Earnings Quality | 25% | Financial Analyst (LLM-assessed) |
| Valuation Clarity | 20% | Financial Analyst (LLM-assessed) |
| Company Predictability | 20% | Data Collector (programmatic) |
| Insider Signal | 10% | Financial Analyst (LLM + programmatic) |
| Macro Conditions | 5% | Financial Analyst (LLM-assessed) |

All LLM-assessed factors use calibrated 5-tier rubric anchors to prevent score clustering.

### Design Decisions Driven by Real Analyst Workflow Review
1. **Peer comparison added** — analysts never evaluate a company in isolation. Data Collector fetches 3–5 sector peers constrained by market cap band (0.25x–4x).
2. **12-month forward outlook** — BUY/HOLD/SELL without a time horizon is ambiguous. All recommendations anchored to 12-month outlook.
3. **Forward-looking analysis** — Financial Analyst instructed to produce directional views (not just historical analysis), grounded in MD&A, trends, and macro context. Framed transparently as trend-based.
4. **Insider Signal made asymmetric** — buying is a strong signal, selling is noisy. Scored against Financial Analyst's directional lean, not the final thesis (avoids circular dependency).
5. **"Earnings Quality" reframed** — measures whether the financial picture is explainable within context, not whether all metrics point the same direction. Turnaround stories can still score high.

### Data Source Criticality
yfinance (essential, 40pts) > SEC EDGAR (important, 35pts) > FRED (nice-to-have, 25pts)

## What the Next Session Should Do

1. **Read the full spec** at `docs/superpowers/specs/2026-03-14-prd-design.md`
2. **Design the architecture** — define the typed data contracts (Python dataclasses/Pydantic models), module structure, and file layout
3. **Write the implementation plan** — break the build into phased steps with clear acceptance criteria per step
4. **Save the plan** to `docs/handoff-implementation-plan.md`

## Open Questions for Next Session

- How should MD&A HTML parsing handle edge cases (filings with non-standard headers, very old filing formats)?
- Should the Financial Analyst prompt use few-shot examples of good analysis, or rely on zero-shot with detailed rubrics?
- What's the right token budget split between MD&A text, financial data, and peer data within the ~8K data context target?
