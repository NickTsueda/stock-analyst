# AI Stock Analyst — Product Requirements Document

## 1. Product Overview

**Product:** AI Stock Analyst — a multi-agent system that takes a ticker symbol and produces a complete investment thesis with buy/sell/hold recommendation and transparent confidence scoring.

**Target User:** Self-directed retail investors managing $25K–$500K portfolios who:
- Want institutional-quality analysis without Bloomberg/FactSet costs ($20K+/yr)
- Currently rely on fragmented free sources (Seeking Alpha, Reddit, finviz) and lack a unified analytical framework
- Have enough financial literacy to interpret ratios and read a balance sheet, but don't have time to do the full analysis themselves

**User Problem:** Retail investors can access data, but tools rarely synthesize filings, financials, and macro signals into an explainable investment thesis comparable to a sell-side research report.

**Scope (V1):** US public equities only — companies with SEC filings and US exchange listings (NYSE, NASDAQ, AMEX).

**Key Behaviors:**
- Always-fresh analysis: every request hits all APIs and runs all agents from scratch (no caching in V1)
- Graceful degradation: analyze with whatever data is available, penalize the Confidence Score and clearly label missing sources rather than refusing
- Synchronous with streaming: user sees the analysis build in real-time as agents complete their stages

**Success Criteria (V1):**
- Produces a coherent, readable analysis for any US public equity within 120 seconds
- Confidence Score accurately reflects data completeness and analytical certainty
- A knowledgeable investor reads the output and finds it comparable to a junior analyst's work

**Non-Goals (V1):**
- Not a real-time trading tool (no live quotes, no alerts)
- Not portfolio management (single-ticker analysis only)
- No historical analysis storage or comparison
- No caching or user accounts

---

## 2. User Journey

The experience follows five stages, each mapping to a pipeline stage.

### Stage 1: Enter Ticker
- User lands on a single-page Streamlit app with a text input and "Analyze" button
- Validates input: must be a valid US exchange ticker (NYSE, NASDAQ, AMEX)
- On invalid input: inline error message ("Ticker not found. Please enter a valid US-listed stock symbol.")
- On valid input: transitions to Stage 2

### Stage 2: Watch Progress (Streaming)
- Progress panel shows the agent pipeline in real-time:
  - `Collecting market data...` → `Fetching SEC filings...` → `Pulling macro indicators...` → `Fetching peer comparisons...` → `Analyzing financials...` → `Building investment thesis...` → `Validating thesis (revision loop)...` → `Finalizing...`
- Each step shows a status indicator (pending / in-progress / complete / failed / skipped)
- If a data source fails, the step shows a warning (e.g., "SEC filings: unavailable — analysis will proceed with limited data") and the pipeline continues
- The revision step may show what's being re-examined (e.g., "Re-examining margin assumptions...")
- Revision step shows as "skipped" if the Thesis Builder's self-critique finds no substantive gaps
- Target: 45–120 seconds total

**Approximate time budget per stage:**
| Stage | Estimate | Notes |
|---|---|---|
| Data Collector | 10–20s | Parallel API calls; EDGAR parsing is slowest |
| Financial Analyst | 15–30s | Single Claude call with full data payload |
| Thesis Builder | 15–30s | Single Claude call for narrative synthesis |
| Revision Loop | 0–30s | Skipped if no gaps; 30s timeout if triggered |

### Stage 3: Read Analysis (Dashboard → Report Hybrid)
**Top section (dashboard):**
- Confidence Score gauge (0–100)
- Recommendation badge (BUY / HOLD / SELL — 12-Month Outlook)
- Current price, key metrics (P/E, revenue growth, debt-to-equity)

**Expandable sections below:**
- **Executive Summary** — 2–3 paragraph forward-looking thesis
- **Financial Analysis** — Revenue trends, margins, balance sheet health, with Plotly charts
- **Peer Comparison** — Key metrics vs 3–5 sector peers, relative valuation context
- **Forward Outlook (Trend-Based)** — Directional views on revenue, margins, and catalysts over next 12 months. Subtitle: *"Directional assessment based on available filings and historical patterns. Does not incorporate analyst consensus or recent earnings guidance."*
- **Bull / Base / Bear Cases** — 3-column layout with probability-weighted scenarios
- **Risks & Catalysts** — What could go wrong and what could accelerate the thesis
- **Macro Context** — How rates, GDP, sector trends affect this stock
- **Insider & Institutional Activity** — Recent Form 4 filings, institutional ownership changes

### Stage 4: Understand Confidence
- The dashboard gauge (Stage 3) is clickable/expandable to reveal the full breakdown panel
- Breakdown shows 6 contributing factors, each scored
- Each factor shows its score, a one-sentence explanation, and a directional indicator (helping / hurting the overall score)
- See design doc (`docs/design.md`) for full scoring design

### Stage 5: Take Action
- Disclaimer displayed: *"This is AI-generated analysis for educational purposes only. Not financial advice."*
- User can enter a new ticker to run another analysis
- No save/export in V1

---

## 3. V2 Considerations (Out of Scope for V1)

- Caching layer (data TTL + cached analyses)
- US public equities + major ADRs
- Earnings call transcript integration
- Sector-specific metric frameworks (bank-specific, SaaS-specific, REIT-specific)
- Multi-pass revision loop (>1 iteration)
- Save/export analysis as PDF
- User accounts and analysis history
- Portfolio-level analysis (multiple tickers)
