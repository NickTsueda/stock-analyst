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
- **Bull Case** — Key arguments supporting the investment thesis
- **Risk Factors** — Bear case arguments and what could go wrong
- **Macro Context** — How rates, GDP, sector trends affect this stock
- **Insider & Institutional Activity** — Recent Form 4 filings, institutional ownership changes

### Stage 4: Understand Confidence
- The dashboard gauge (Stage 3) is clickable/expandable to reveal the full breakdown panel
- Breakdown shows 6 contributing factors, each scored
- Each factor shows its score, a one-sentence explanation, and a directional indicator (helping / hurting the overall score)
- See Section 5 for full scoring design

### Stage 5: Take Action
- Disclaimer displayed: *"This is AI-generated analysis for educational purposes only. Not financial advice."*
- User can enter a new ticker to run another analysis
- No save/export in V1

---

## 3. Agent Architecture & Data Contracts

Four agents in a primarily sequential pipeline with a revision loop between the Thesis Builder and Financial Analyst. Each agent is a plain Python class with typed inputs/outputs — no framework dependencies.

### Pipeline Flow

```
Orchestrator → Data Collector → Financial Analyst → Thesis Builder
                                       ↑                    │
                                       └── Revision Loop ───┘
                                          (max 1 iteration)
```

### Agent 1: Orchestrator

- **Responsibility:** Validates ticker, dispatches agents in sequence, manages the revision loop, handles failures, assembles final output, computes the Data Completeness confidence sub-score (since it knows which sources succeeded/failed)
- **Input:** Ticker string (e.g., `"AAPL"`)
- **Output:** Complete `AnalysisReport` object containing all sections
- **Computes:** `data_completeness_score` (see Section 5 for formula)
- **Error handling:** If Data Collector returns partial data, continues with what's available. If Financial Analyst or Thesis Builder fails entirely, returns an error state to the UI. If the revision loop times out, uses the pre-revision thesis.

### Agent 2: Data Collector

- **Responsibility:** Fetches raw data from all sources in parallel, normalizes into a unified structure
- **Input:** Validated ticker
- **Output:** `CompanyData` object containing:
  - Market data (price, volume, ratios, historical prices) — from yfinance
  - Filing data (income statement, balance sheet, cash flow, MD&A section from recent 10-K/10-Q) — from SEC EDGAR. MD&A extraction: locate "Item 7" (10-K) or "Item 2" (10-Q) header in filing HTML, extract text until next item header, truncate to ~4,000 tokens for the LLM prompt.
  - Macro data (fed funds rate, GDP growth, unemployment, CPI, yield curve) — from FRED
  - Insider transactions (recent Form 4 buys/sells) — from SEC EDGAR
  - Peer data (3–5 companies in same industry: key ratios, market cap, growth rates) — from yfinance
  - Metadata: which sources succeeded/failed, timestamps
- **Key behaviors:**
  - Each data source fetch is independent — one failure doesn't block others. Returns a `data_completeness` flag per source.
  - **Peer selection:** Uses yfinance's `industry` field. Constrains peers to a market cap band of 0.25x–4x the target's market cap, then selects 3–5 largest within that band. If fewer than 3 peers fit, widens the band and flags the mismatch in metadata. If `industry` is missing or overly generic (e.g., "Conglomerates"), falls back to `sector` field and flags reduced peer relevance. If neither yields usable peers, skips peer comparison and penalizes Valuation Clarity score.
  - **Computes:** `company_predictability_score` — programmatic calculation based on historical revenue/earnings volatility (coefficient of variation). Requires at least 8 quarters of data; if fewer are available, defaults to 50 with a note.

### Agent 3: Financial Analyst

- **Responsibility:** Takes raw data, computes derived metrics, identifies trends, produces structured financial analysis with forward-looking assessments. Calls Claude.
- **Input:** `CompanyData` object. On revision: receives `CompanyData` + `RevisionRequest` (specific questions from the Thesis Builder).
- **Output:** `FinancialAnalysis` object containing:
  - Computed metrics (revenue growth rates, margin trends, debt ratios over time)
  - Peer-relative metrics (how each metric compares to sector peers)
  - Trend assessments (improving/stable/declining for each metric category)
  - Forward-looking directional views (revenue trajectory, margin outlook, catalysts/headwinds — grounded in historical trends, MD&A, and macro context)
  - Risk factors identified
  - Macro impact assessment
  - Insider signal interpretation
  - `directional_lean` (BULLISH / NEUTRAL / BEARISH) with one-sentence rationale — the Analyst's overall read on the numbers before thesis synthesis
  - Confidence sub-scores for: Earnings Quality, Valuation Clarity, Insider Signal, Macro Conditions (LLM-assessed factors). Note: Data Completeness is computed by the Orchestrator, Company Predictability is computed by the Data Collector.
- **On revision:** Produces a `RevisedAnalysis` (see data contract below) that focuses specifically on the questions raised, with deeper examination and any corrected assessments.

### Agent 4: Thesis Builder

- **Responsibility:** Synthesizes the financial analysis into a human-readable investment thesis with a 12-month forward outlook recommendation. Calls Claude. After initial synthesis, performs a self-critique to identify weak points.
- **Input:** `FinancialAnalysis` object + `CompanyData` (for raw context)
- **Output:** `InvestmentThesis` object containing:
  - Recommendation (BUY / HOLD / SELL) with explicit 12-month forward outlook
  - Executive summary (2–3 paragraphs, forward-looking)
  - Bull case / Bear case arguments
  - Peer comparison narrative
  - Forward outlook section (directional views on key drivers over 12 months)
  - Overall Confidence Score (0–100) with breakdown
  - Section narratives (financial analysis, risk factors, macro context, insider activity)
- **Revision behavior:** After generating the initial thesis, the Thesis Builder self-critiques by asking: *"What are the weakest assumptions in this thesis? What contradictions did I gloss over? What would a skeptical analyst challenge?"* If it identifies substantive gaps (not cosmetic), it produces a `RevisionRequest` with 1–3 specific questions and sends it back to the Financial Analyst. After receiving the `RevisedAnalysis`, it produces a final strengthened thesis. Revision is skipped if self-critique finds no substantive gaps.

### Data Contracts: Revision Types

**`RevisionRequest`:**
- `questions: list[str]` — 1–3 specific questions the Thesis Builder wants re-examined
- `factors_to_reexamine: list[str]` — which confidence factors or analysis areas need deeper scrutiny (e.g., `["insider_signal", "margin_trends"]`)
- `context: str` — brief explanation of what triggered the revision (e.g., "Thesis is BUY but insider selling is heavy and accelerating")

**`RevisedAnalysis`:**
- `revised_assessments: dict[str, str]` — updated assessments keyed by factor/area
- `revised_subscores: dict[str, int]` — any confidence sub-scores that changed
- `revision_rationale: str` — summary of what changed and why

### Revision Loop Details

- Max 1 revision iteration (keeps latency bounded)
- The Orchestrator enforces a timeout: if the revision loop hasn't completed within 30 seconds of the revision request being sent, use the pre-revision thesis
- If revision occurs, the UI streams: `"Validating thesis — re-examining [topic]..."`

### Why This Architecture

**Two separate LLM agents (Analyst + Thesis Builder):** Separation of concerns — the Analyst focuses on quantitative reasoning (what do the numbers say?), the Thesis Builder focuses on narrative synthesis (what does it mean for an investor?). This mirrors how research teams work and makes each prompt more focused and debuggable.

**Revision loop:** Single-pass analysis is the #1 difference between mediocre and good analyst work. A junior analyst's first draft always has blind spots — the value comes from a senior analyst asking "but what about X?" The revision loop simulates this dynamic. Concretely: if the Thesis Builder says "BUY" but notices that insider selling is heavy and margins are compressing, the revision sends targeted questions back to the Financial Analyst to stress-test those specific signals before finalizing.

---

## 4. Data Sources & Failure Modes

Each data source is a standalone module that returns a typed result or a graceful failure. No source failure should crash the pipeline.

### SEC EDGAR
- **What we fetch:** Most recent 10-K and 10-Q filings (financial statements and MD&A section), Form 4 insider transactions (last 12 months)
- **API constraints:** Must include `User-Agent` header with contact email. Rate limit: max 10 requests/second (we'll self-throttle to 0.1s between requests).
- **Failure modes:** Company not found (foreign filer, too new), EDGAR down/slow, filing format changed. All return empty data + flag.
- **Impact of failure:** Confidence Score penalizes Data Completeness. Financial analysis proceeds using yfinance fundamentals as fallback for basic ratios. Forward Outlook loses MD&A grounding and is flagged accordingly.

### Yahoo Finance (yfinance)
- **What we fetch:** Current price, historical prices (1yr), key ratios (P/E, P/B, EPS, market cap), institutional holdings summary, industry classification, and key ratios for 3–5 sector peers
- **API constraints:** Unofficial scraper — no guaranteed uptime or rate limits. Can break without notice.
- **Failure modes:** Ticker not found (our validation gate), data structure changes, temporary blocking. Returns empty data + flag. Peer fetch failure is independent — if peers can't be fetched, analysis proceeds without peer context and Valuation Clarity score is penalized.
- **Impact of failure:** This is the most critical source — if yfinance fails entirely, we likely can't produce a useful analysis. Orchestrator should surface a clear error rather than a hollow report.

### FRED (Federal Reserve Economic Data)
- **What we fetch:** Fed funds rate, GDP growth (quarterly), unemployment rate, CPI (inflation), 10Y-2Y yield spread (yield curve)
- **API constraints:** Requires free API key. Rate limit: 120 requests/minute (generous).
- **Failure modes:** Invalid API key, FRED down. Returns empty data + flag.
- **Impact of failure:** Least critical for individual stock analysis. Macro Context section shows "Macro data unavailable" and Confidence Score penalizes Macro Conditions factor.

### Criticality Ranking

yfinance (essential) > SEC EDGAR (important) > FRED (nice-to-have)

---

## 5. Confidence Score Design

The headline differentiator — a 0–100 score with full transparency into what drives it.

### Overall Score

Weighted average of 6 sub-scores, each 0–100:

| Factor | Weight | What It Measures |
|---|---|---|
| Data Completeness | 20% | How many data sources returned usable data |
| Earnings Quality | 25% | Whether the financial picture is explainable and coherent within context |
| Valuation Clarity | 20% | How clearly we can assess whether the stock is over/undervalued |
| Company Predictability | 20% | How volatile/erratic are the company's historical financials |
| Insider Signal | 10% | Whether insider transactions provide a meaningful directional signal |
| Macro Conditions | 5% | How stable/readable is the macro environment for this sector |

### How Each Sub-Score Is Determined

**Data Completeness** — Programmatic. Weighted by source criticality:
- yfinance: 40 points (essential)
- SEC EDGAR: 35 points (important)
- FRED: 25 points (nice-to-have)
- Score = sum of points for successful sources. Examples: all 3 = 100, yfinance only = 40, yfinance + EDGAR = 75, yfinance + FRED = 65, EDGAR + FRED only = 60 (no yfinance triggers error state before this is reached in most cases).

**Earnings Quality** — LLM-assessed with calibrated rubric. Claude evaluates whether the financial picture is explainable and coherent within the company's context. A turnaround story with declining revenue but improving margins can still score high if the inconsistencies are explainable.

Rubric anchors:
- 0–20: Major red flags (restatements, inconsistencies with no explanation, potential fraud indicators)
- 21–40: Significant concerns (declining quality, unexplained divergences between metrics)
- 41–60: Mixed signals (some concerns but partially explainable)
- 61–80: Solid (coherent story, minor concerns only)
- 81–100: Exceptional (highly consistent, transparent, predictable earnings)

**Valuation Clarity** — LLM-assessed with calibrated rubric. Claude evaluates how clearly we can assess valuation: Are P/E, P/B, and PEG ratios available? Are peer multiples available for relative comparison? Is there enough data to sketch a basic DCF? A stock with clear comps and stable cash flows scores high; a pre-revenue biotech with no peers scores low. Peer data unavailable = score capped at 60 for this factor.

Rubric anchors:
- 0–20: Essentially unvaluable (pre-revenue, no comps, no cash flow history)
- 21–40: Difficult (limited comps, volatile cash flows, unusual business model)
- 41–60: Moderate (some comps available but imperfect, or missing peer data)
- 61–80: Clear (good peer comps, stable cash flows, standard valuation metrics available)
- 81–100: Highly transparent (excellent peer set, predictable cash flows, multiple valuation methods converge)

**Company Predictability** — Programmatic. Based on historical revenue/earnings volatility (coefficient of variation). Steady growers score high; erratic companies score low. Requires at least 8 quarters of data from yfinance/EDGAR; if fewer are available, defaults to 50 with a note explaining insufficient history.

**Insider Signal** — Programmatic + LLM. Asymmetric scoring: insider buying strongly boosts the score (one clear reason to buy), insider selling only moderately penalizes (many non-informative reasons — 10b5-1 plans, diversification, tax events). Scored against the Financial Analyst's `directional_lean`: insider activity that *confirms* the directional lean boosts the score; activity that *contradicts* it moderately penalizes (since insiders may have non-public information worth noting, but could also be acting for personal reasons). No insider data = neutral (50) with a note.

**Macro Conditions** — LLM-assessed with calibrated rubric. Claude evaluates whether macro indicators are readable and directionally clear for this company's sector, not merely stable. A clearly dovish Fed is volatile but readable.

Rubric anchors:
- 0–20: Highly uncertain (conflicting indicators, policy regime change, unprecedented conditions)
- 21–40: Unclear (mixed signals, elevated uncertainty in key indicators)
- 41–60: Moderate (some clarity but meaningful crosscurrents)
- 61–80: Readable (clear directional trends, manageable uncertainty)
- 81–100: Highly clear (strong consensus on direction, benign environment for this sector)

### Display

Each factor shows its score, a one-sentence explanation, and a directional indicator (helping / hurting the overall score).

### Guardrails

- If Data Completeness < 30, overall score is capped at 40 regardless of other factors
- If yfinance fails entirely, score is 0 and analysis shows an error state instead

---

## 6. Technical Constraints

- **Tech stack:** Python 3.11+, `anthropic` SDK (Claude Sonnet — claude-sonnet-4-20250514), `streamlit`, `yfinance`, `fredapi`, `requests`, `plotly`, `pytest`
- **No frameworks:** Plain Python classes with typed data contracts. No LangChain, CrewAI, or similar.
- **SEC EDGAR compliance:** User-Agent header with contact email, 0.1s minimum between requests
- **Graceful failures:** Every data source function must return gracefully on failure — never crash the pipeline
- **Disclaimer required:** All investment-related output must include: "This is AI-generated analysis for educational purposes only. Not financial advice."
- **Prompt size management:** The Financial Analyst and Thesis Builder receive potentially large payloads (financial data + MD&A + peer data). MD&A text is truncated to ~4,000 tokens at extraction time. Historical data older than 4 years is summarized rather than sent raw. Total prompt payload per Claude call should target <8,000 tokens of data context to leave room for instructions and response.

---

## 7. V2 Considerations (Out of Scope for V1)

- Caching layer (data TTL + cached analyses)
- US public equities + major ADRs
- Earnings call transcript integration
- Sector-specific metric frameworks (bank-specific, SaaS-specific, REIT-specific)
- Multi-pass revision loop (>1 iteration)
- Save/export analysis as PDF
- User accounts and analysis history
- Portfolio-level analysis (multiple tickers)
