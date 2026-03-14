# Handoff: Requirements Phase

**Date:** 2026-03-14
**Status:** Complete
**Next phase:** Build — Phase 1

---

## What Was Done

Completed the full PRD and design doc through collaborative brainstorming and iterative review. The PRD covers Product Overview, User Journey, and V2 Considerations. The design doc covers Agent Architecture, Data Sources, Confidence Score Algorithm, Technical Constraints, and UI Architecture.

**Spec locations:**
- PRD: `docs/prd.md`
- Architecture & Design: `docs/design.md`

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
| Insider Signal | 10% | Orchestrator post-processing (Python heuristic scored against `directional_lean` + recommendation) |
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

Design and implementation planning are complete. Next session begins **Build — Phase 1**. See `docs/handoff-design.md` for details.

## Open Questions (Resolved in Design Phase)

- **MD&A parsing:** BeautifulSoup `get_text()` + regex for section headers. Fallback to first 15K chars. Only filings from 2000+. Best-effort — not a critical dependency since XBRL provides the numbers.
- **Prompt strategy:** Zero-shot with detailed rubrics and calibrated 5-tier anchors (not few-shot). Simpler, cheaper, and rubric anchors prevent score clustering.
- **Token budget:** ~4K tokens for MD&A text at extraction time. Target <8K tokens of data context per Claude call total. Historical data older than 4 years summarized rather than sent raw.
