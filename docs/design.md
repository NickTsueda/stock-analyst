# AI Stock Analyst — Architecture & Design

This document describes the technical architecture, data contracts, scoring algorithms, and engineering constraints for the AI Stock Analyst. For product requirements (target user, user journey, success criteria), see `docs/prd.md`.

---

## 1. System Architecture

### Pipeline Overview

Four agents in a sequential pipeline with a revision loop between the Thesis Builder and Financial Analyst. Each agent is a plain Python class with typed inputs/outputs — no framework dependencies (no LangChain, CrewAI, or similar).

```
Orchestrator → Data Collector → Financial Analyst → Thesis Builder
                                       ↑                    │
                                       └── Revision Loop ───┘
                                          (max 1 iteration)
```

### Why This Architecture

**Two separate LLM agents (Analyst + Thesis Builder):** Separation of concerns — the Analyst focuses on quantitative reasoning (what do the numbers say?), the Thesis Builder focuses on narrative synthesis (what does it mean for an investor?). This mirrors how research teams work and makes each prompt more focused and debuggable.

**Revision loop:** Single-pass analysis is the #1 difference between mediocre and good analyst work. A junior analyst's first draft always has blind spots — the value comes from a senior analyst asking "but what about X?" The revision loop simulates this dynamic. Concretely: if the Thesis Builder says "BUY" but notices that insider selling is heavy and margins are compressing, the revision sends targeted questions back to the Financial Analyst to stress-test those specific signals before finalizing.

**No framework:** Plain Python classes keep the system debuggable, testable, and free of opaque abstractions. The `anthropic` SDK is the only AI dependency.

---

## 2. Agent Specifications

### Agent 1: Orchestrator

- **Responsibility:** Validates ticker, dispatches agents in sequence, manages the revision loop, handles failures, assembles final output, computes the final Confidence Score
- **Input:** Ticker string (e.g., `"AAPL"`)
- **Output:** `tuple[DataPackage, FinancialAnalysis | None, InvestmentThesis | None]`
- **Reads:** `DataPackage.data_completeness_score` (computed by Data Collector) for the quality gate and the Data Completeness confidence sub-score
- **Data quality gate (deterministic, no Claude call):**
  - If `data_completeness_score < 20`: abort analysis, return `(DataPackage, None, None)` with error. UI shows which data sources failed.
  - If `20 ≤ score < 50`: proceed, but append a `LimitationNote` warning to the DataPackage.
  - If `score ≥ 50`: proceed normally.
- **Error handling:** If Data Collector returns partial data, continues with what's available. If Financial Analyst or Thesis Builder fails entirely, returns an error state to the UI. If the revision loop times out (30s), uses the pre-revision thesis.
- **Progress callback:** `(stage: str, status: str) -> None` for Streamlit streaming updates.

### Agent 2: Data Collector

- **Responsibility:** Fetches raw data from all sources, normalizes into a unified structure
- **Input:** Validated ticker
- **Output:** `DataPackage` object (see Section 3 for full schema)
- **Does NOT call Claude** — this is pure data fetching and assembly.
- **Key behaviors:**
  - Each data source fetch is independent — one failure doesn't block others. Returns a `data_completeness` flag per source.
  - **Peer selection:** Uses yfinance's `industry` field. Constrains peers to a market cap band of 0.25x–4x the target's market cap, then selects 3–5 largest within that band. If fewer than 3 peers fit, widens the band and flags the mismatch in metadata. If `industry` is missing or overly generic (e.g., "Conglomerates"), falls back to `sector` field and flags reduced peer relevance. If neither yields usable peers, skips peer comparison and penalizes Valuation Clarity score.
  - **Computes:** `company_predictability_score` — programmatic calculation based on historical revenue/earnings volatility (coefficient of variation). Requires at least 8 quarters of data; if fewer are available, defaults to 50 with a note.

### Agent 3: Financial Analyst

- **Responsibility:** Takes raw data, computes derived metrics, identifies trends, produces structured financial analysis with forward-looking assessments. Calls Claude.
- **Input:** `DataPackage` object. On revision: receives `DataPackage` + `RevisionRequest`.
- **Output:** `FinancialAnalysis` object containing:
  - Computed metrics (revenue growth rates, margin trends, debt ratios over time)
  - Peer-relative metrics (how each metric compares to sector peers)
  - Trend assessments (improving/stable/declining for each metric category)
  - Forward-looking directional views (revenue trajectory, margin outlook, catalysts/headwinds — grounded in historical trends, MD&A, and macro context)
  - Risk factors identified
  - Macro impact assessment
  - Insider signal interpretation
  - `directional_lean` (BULLISH / NEUTRAL / BEARISH) with one-sentence rationale
  - Confidence sub-scores: `earnings_quality` (0-100), `valuation_clarity` (0-100), `macro_conditions` (0-100) — LLM-assessed using rubric anchors defined in Section 4
- **On revision:** `run_revision(data: DataPackage, request: RevisionRequest) -> RevisedAnalysis` — a separate method that focuses specifically on the questions raised, with deeper examination and any corrected assessments.
- **Prompt strategy:** Enhanced UChicago methodology with chain-of-thought:
  1. Classify company type (Growth/Value/Dividend/Turnaround/Cyclical)
  2. Profitability analysis (margins, ROE, ROA — with trends across years)
  3. Growth analysis (revenue/earnings growth, acceleration/deceleration)
  4. Balance sheet health (D/E, current ratio, cash position)
  5. Cash flow quality (OCF vs net income, FCF trend)
  6. Overall assessment with strengths and concerns

### Agent 4: Thesis Builder

- **Responsibility:** Synthesizes the financial analysis into a human-readable investment thesis with a 12-month forward outlook recommendation. Calls Claude. After initial synthesis, performs a self-critique to identify weak points.
- **Input:** `FinancialAnalysis` object + `DataPackage` (for raw context)
- **Output:** `InvestmentThesis` object containing:
  - Recommendation (BUY / HOLD / SELL) with explicit 12-month forward outlook
  - Executive summary (2–3 paragraphs, forward-looking)
  - Bull case / Base case / Bear case with probabilities (must sum to 100%)
  - Peer comparison narrative
  - Forward outlook section
  - Confidence Score (0–100) with structured breakdown
  - Section narratives (financial analysis, risk factors, macro context, insider activity)
  - Key risks and catalysts
- **Revision behavior:** After generating the initial thesis, the Thesis Builder self-critiques by asking: *"What are the weakest assumptions in this thesis? What contradictions did I gloss over? What would a skeptical analyst challenge?"* If it identifies substantive gaps (not cosmetic), it produces a `RevisionRequest` with 1–3 specific questions and sends it back to the Financial Analyst. Revision is skipped if self-critique finds no substantive gaps.
- **Revised run:** `run_with_revision(data: DataPackage, analysis: FinancialAnalysis, revised: RevisedAnalysis) -> InvestmentThesis` — a separate method that incorporates the revised analysis. The Orchestrator calls `run()` first, then if a `RevisionRequest` is produced, calls the Financial Analyst's `run_revision()`, then calls `run_with_revision()` on the Thesis Builder.

### Revision Loop

- Max 1 revision iteration (keeps latency bounded)
- The Orchestrator enforces a 30-second timeout — if exceeded, uses the pre-revision thesis
- If revision occurs, the UI streams: `"Validating thesis — re-examining [topic]..."`

**`RevisionRequest`:**
- `questions: list[str]` — 1–3 specific questions the Thesis Builder wants re-examined
- `factors_to_reexamine: list[str]` — which confidence factors or analysis areas need deeper scrutiny
- `context: str` — brief explanation of what triggered the revision

**`RevisedAnalysis`:**
- `revised_assessments: dict[str, str]` — updated assessments keyed by factor/area
- `revised_subscores: dict[str, int]` — any confidence sub-scores that changed
- `revision_rationale: str` — summary of what changed and why

---

## 3. Data Models

All data contracts are Python dataclasses with `to_dict()` and `from_dict()` classmethods for serialization.

### Core Models

- **`FinancialStatements`** — multi-year income/balance/cash flow
- **`MarketData`** — current price, ratios, sector
- **`InsiderActivity`** — transactions + net sentiment. **Primary source: SEC EDGAR Form 4** (authoritative). yfinance insider data is a fallback if EDGAR fails. Do not merge — use one source.
- **`InstitutionalData`** — top holders
- **`MacroContext`** — FRED macro indicators
- **`FilingText`** — extracted MD&A and risk factors text
- **`PeerData`** — comparison data for 3-5 sector peers (ticker, name, market cap, key ratios). Fetched by yfinance based on industry/sector classification.
- **`DataPackage`** — complete Data Collector output (aggregates all above + `PeerData` + `list[LimitationNote]`)
  - Also provides `to_prompt_text()` for formatting data as structured text for Claude prompts
  - Also provides `data_completeness_score: int` (0–100) computed by Data Collector using weighted formula (yfinance=40, EDGAR=35, FRED=25)
  - Also provides `warnings: list[LimitationNote]` for tracking degraded sources

### Analysis Models

- **`FinancialRatio`** — name, values by year, trend, assessment
- **`FinancialAnalysis`** — Financial Analyst output (includes LLM-assessed sub-scores: `earnings_quality: int` 0–100, `valuation_clarity: int` 0–100, `macro_conditions: int` 0–100)
- **`InvestmentCase`** — narrative + drivers + probability
- **`InvestmentThesis`** — Thesis Builder output (bull/base/bear + recommendation + confidence score)

### Confidence Models

- **`ConfidenceDriver`** — single scoring factor with its contribution
  - `factor: str` — one of the 6 factors (e.g., "Data Completeness", "Earnings Quality")
  - `score: int` — 0-100 sub-score for this factor
  - `weight: float` — factor weight (e.g., 0.20 for Data Completeness)
  - `impact: str` — "positive", "negative", "neutral" (helping/hurting overall score)
  - `detail: str` — plain-English explanation
- **`ConfidenceScore`** — overall confidence with breakdown
  - `score: int` — 0-100 (weighted average of 6 factor sub-scores)
  - `level: ConfidenceLevel` — derived: ≥70 High, 40-69 Medium, <40 Low
  - `summary: str` — 1-2 sentence explanation (from Claude)
  - `drivers: list[ConfidenceDriver]` — 6 drivers

### Revision Models

- **`RevisionRequest`** — Thesis Builder's request for re-examination
  - `questions: list[str]` — 1-3 specific questions
  - `factors_to_reexamine: list[str]` — which areas need deeper scrutiny
  - `context: str` — what triggered the revision
- **`RevisedAnalysis`** — Financial Analyst's response to revision
  - `revised_assessments: dict[str, str]` — updated assessments by area
  - `revised_subscores: dict[str, int]` — any confidence sub-scores that changed
  - `revision_rationale: str` — summary of what changed and why

### Utility Models

- **`LimitationNote`** — warning attached to partial or degraded results
  - `source: str` — which component generated the warning
  - `message: str` — human-readable explanation
  - `severity: str` — "warning" or "error"

### Enums

- **`Recommendation`** — BUY, HOLD, SELL
- **`ConfidenceLevel`** — HIGH, MEDIUM, LOW
- **`CompanyType`** — GROWTH, VALUE, DIVIDEND, TURNAROUND, CYCLICAL

---

## 4. Confidence Score Algorithm

The headline differentiator — a 0–100 score with full transparency into what drives it.

### 6-Factor Weighted Model

Weighted average of 6 sub-scores, each 0–100:

| Factor | Weight | Computed By | Method |
|---|---|---|---|
| Data Completeness | 20% | Python (programmatic) | Source success weighted by criticality |
| Earnings Quality | 25% | Claude (LLM-assessed) | Whether the financial picture is explainable and coherent within context |
| Valuation Clarity | 20% | Claude (LLM-assessed) | How clearly we can assess over/undervaluation. Capped at 60 if no peer data |
| Company Predictability | 20% | Python (programmatic) | Historical revenue volatility (coefficient of variation). See formula below. Default 50 if <8 quarters |
| Insider Signal | 10% | Python + Claude | Asymmetric: buying boosts strongly, selling penalizes moderately. Scored against `directional_lean`. No data = 50 |
| Macro Conditions | 5% | Claude (LLM-assessed) | How readable/clear the macro environment is for this sector |

**Overall score** = weighted sum of 6 sub-scores. Example: if Data Completeness = 75, Earnings Quality = 80, Valuation Clarity = 60, Company Predictability = 70, Insider Signal = 50, Macro Conditions = 65 → score = (75×0.20) + (80×0.25) + (60×0.20) + (70×0.20) + (50×0.10) + (65×0.05) = 69.25 → 69.

**Who computes what:**
- **Data Completeness** sub-score: the Data Collector computes `data_completeness_score` (0-100) on the `DataPackage` using the weighted formula (yfinance=40, EDGAR=35, FRED=25). The Orchestrator reads this value directly as the sub-score.
- **Earnings Quality, Valuation Clarity, Macro Conditions**: the Financial Analyst returns these as LLM-assessed sub-scores in its `FinancialAnalysis` output, using the rubric anchors below.
- **Company Predictability**: computed by the Data Collector from historical volatility data, stored on `DataPackage`.
- **Insider Signal**: Python heuristic computed in Orchestrator post-processing. Algorithm:
  1. If no insider data available → score = 50 (neutral)
  2. Determine net insider direction: net_buys > 0 → BUYING, net_buys < 0 → SELLING, net_buys == 0 → NEUTRAL
  3. Compare to Financial Analyst's `directional_lean`:
     - BUYING + BULLISH lean → 80 (strong confirmation)
     - BUYING + NEUTRAL lean → 70 (positive signal)
     - BUYING + BEARISH lean → 60 (notable divergence, insiders may know something)
     - SELLING + BEARISH lean → 60 (weak confirmation — selling is noisy)
     - SELLING + NEUTRAL lean → 45 (mild negative)
     - SELLING + BULLISH lean → 35 (concerning divergence)
     - NEUTRAL insider activity → 50
- **Final weighted score**: computed in Python post-processing after the Thesis Builder returns. Claude provides qualitative `detail` strings and a `summary` for each factor, but does NOT generate the numeric sub-scores for programmatic factors.

### Company Predictability Sub-Score (0-100)

Computed by the Data Collector from quarterly revenue data (at least 8 quarters required, else default 50):
1. Calculate coefficient of variation (CV) of quarterly revenue: `CV = std(revenue) / mean(revenue)`
2. Map CV to score:
   - CV < 0.05 → 90-100 (very stable, e.g., utilities, consumer staples)
   - CV 0.05-0.15 → 70-89 (stable growth, e.g., large-cap tech)
   - CV 0.15-0.30 → 50-69 (moderate volatility, e.g., cyclicals)
   - CV 0.30-0.50 → 30-49 (high volatility, e.g., growth/biotech)
   - CV > 0.50 → 10-29 (very unpredictable, e.g., turnaround/speculative)
3. Linear interpolation within each band.

### Data Completeness Sub-Score (0-100)

Weighted by source criticality:
- yfinance: 40 points (essential)
- SEC EDGAR: 35 points (important)
- FRED: 25 points (nice-to-have)
- Score = sum of points for successful sources.

### Rubric Anchors (for LLM-assessed factors)

**Earnings Quality:**
- 0–20: Major red flags (restatements, inconsistencies with no explanation)
- 21–40: Significant concerns (declining quality, unexplained divergences)
- 41–60: Mixed signals (some concerns but partially explainable)
- 61–80: Solid (coherent story, minor concerns only)
- 81–100: Exceptional (highly consistent, transparent, predictable)

**Valuation Clarity:**
- 0–20: Essentially unvaluable (pre-revenue, no comps)
- 21–40: Difficult (limited comps, volatile cash flows)
- 41–60: Moderate (some comps, imperfect, or missing peer data)
- 61–80: Clear (good peer comps, stable cash flows)
- 81–100: Highly transparent (excellent peers, multiple methods converge)

**Macro Conditions:**
- 0–20: Highly uncertain (conflicting indicators, regime change)
- 21–40: Unclear (mixed signals, elevated uncertainty)
- 41–60: Moderate (some clarity but meaningful crosscurrents)
- 61–80: Readable (clear directional trends)
- 81–100: Highly clear (strong consensus, benign environment)

### Guardrails

- If Data Completeness < 30, overall score is capped at 40 regardless of other factors
- If ALL data sources fail, score is 0 and analysis shows an error state

### Post-Processing Flow

After the Thesis Builder returns its JSON (with qualitative driver details and summary):
1. Collect sub-scores: Data Completeness (from Orchestrator), Earnings Quality + Valuation Clarity + Macro Conditions (from Financial Analyst), Company Predictability (from Data Collector), Insider Signal (computed now from heuristic)
2. Compute weighted average → final score (0-100)
3. Derive `level`: ≥70 High, 40-69 Medium, <40 Low
4. Apply guardrails (Data Completeness cap)
5. Assemble `ConfidenceScore` dataclass with sub-scores + Claude's qualitative text

---

## 5. Data Sources

Each data source is a standalone module that returns a typed result or a graceful failure. No source failure should crash the pipeline.

### Criticality Ranking

yfinance (essential, 40pts) > SEC EDGAR (important, 35pts) > FRED (nice-to-have, 25pts)

### SEC EDGAR

- **Endpoints:**
  - XBRL API (`data.sec.gov/api/xbrl/companyfacts/`) — **primary source for financial statement numbers.** Reliable, structured, no HTML parsing needed.
  - Submissions API — recent filings list (10-K, 10-Q, Form 4)
  - Filing HTML — best-effort qualitative extraction (MD&A, Risk Factors)
- **What we fetch:** Most recent 10-K and 10-Q filings (financial statements via XBRL + MD&A text via HTML), Form 4 insider transactions (last 12 months)
- **MD&A extraction strategy:** BeautifulSoup `get_text()` first, then regex for section headers (case-insensitive: "Item 7", "ITEM 7", etc.). Extract text between matched header and next "Item" header. Truncate to ~15K chars per section. Fallback: first 15K chars of cleaned text. Only attempt filings from 2000+.
- **API constraints:** Must include `User-Agent` header with contact email. Rate limit: 0.1s between requests.
- **Failure modes:** Company not found (foreign filer, too new), EDGAR down/slow, filing format changed. All return empty data + flag.
- **Impact of failure:** Confidence penalizes Data Completeness. Analysis proceeds using yfinance fundamentals as fallback.

### Yahoo Finance (yfinance)

- **What we fetch:** Current price, historical prices (1yr), key ratios (P/E, P/B, EPS, market cap), institutional holdings, industry classification, and key ratios for 3–5 sector peers
- **API constraints:** Unofficial scraper — no guaranteed uptime. Can break without notice.
- **Failure modes:** Ticker not found, data structure changes, temporary blocking. Peer fetch failure is independent.
- **Impact of failure:** Most critical source. If yfinance fails entirely, analysis still proceeds with SEC EDGAR data (graceful degradation), but Data Completeness score drops significantly (max 60/100 without yfinance) and a `LimitationNote` warns the user.

### FRED (Federal Reserve Economic Data)

- **What we fetch:** Fed funds rate (FEDFUNDS), GDP growth (GDPC1), unemployment (UNRATE), CPI (CPIAUCSL), yield spread (T10Y2Y)
- **API constraints:** Requires free API key. Rate limit: 120 requests/minute.
- **Failure modes:** Invalid API key, FRED down.
- **Impact of failure:** Least critical. Macro section shows "unavailable" and Confidence penalizes Macro Conditions.

### Caching

No caching in V1. Every analysis hits all APIs from scratch. Caching is a V2 consideration.

---

## 6. Technical Constraints

- **Tech stack:** Python 3.11+, `anthropic` SDK (Claude Sonnet — claude-sonnet-4-20250514), `streamlit`, `yfinance`, `fredapi`, `requests`, `beautifulsoup4`, `plotly`, `pandas`, `python-dotenv`, `pytest`
- **No frameworks:** Plain Python classes with typed data contracts
- **SEC EDGAR compliance:** User-Agent header with contact email, 0.1s minimum between requests
- **Graceful failures:** Every data source function must return gracefully on failure — never crash the pipeline
- **Disclaimer required:** All investment-related output must include: "This is AI-generated analysis for educational purposes only. Not financial advice." (2 placements in V1: persistent footer, warning banner on Thesis tab)
- **Prompt size management:** MD&A truncated to ~4,000 tokens at extraction time. Historical data older than 4 years summarized. Target <8,000 tokens of data context per Claude call.
- **Cost target:** ~$0.15-0.20 per analysis with Sonnet

### Base Agent Class

```python
class BaseAgent:
    def __init__(self, client: anthropic.Anthropic, model: str = None):
        self.client = client
        self.model = model or settings.CLAUDE_MODEL

    def _call_claude(self, system: str, user: str) -> dict:
        """Send message to Claude, parse JSON response. Retry up to 2x on rate limit or parse failure."""

    def _parse_json_response(self, text: str) -> dict:
        """Extract JSON from response (handles markdown code fences)."""
```

Uses prompt caching (`cache_control`) on system prompts. Logs token counts and cost estimates.

---

## 7. UI Architecture

### Layout: 3-Tab Structure

**Investment Thesis Tab:**
- Hero section: company name + ticker + price + recommendation badge (pill-shaped, color-coded)
- Confidence Score gauge: semicircular, 0-100, color zones (red 0-39, yellow 40-69, green 70-100). Expandable driver breakdown.
- Executive Summary: 2-3 paragraph prose
- Bull / Base / Bear Cases: 3-column card layout with probabilities
- Risks & Catalysts: 2-column layout
- Insider & Institutional Signals
- Macro Context Summary
- Footer: disclaimer, cost, timestamp

**Financial Analysis Tab:**
- Price chart: 1Y daily close with 50-day and 200-day moving averages
- Revenue & profit bar chart: grouped bars
- Margin trends line chart: gross/operating/net margin %
- Ratio table: P/E, P/S, EV/EBITDA, D/E, Current Ratio, ROE
- Chain-of-thought reasoning: expandable "Agent Reasoning" section

**Raw Data Tab:**
- Expandable section per data source
- Data Completeness Indicator at top
- Warnings / Limitations Log

### Streamlit Specifics

- Dark theme with green accent (`#4CAF50`)
- Session state for persisting results across reruns
- `st.status()` for pipeline progress streaming
- Plotly for all charts (dark-theme friendly colors)
