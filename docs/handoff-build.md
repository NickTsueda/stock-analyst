# Handoff: Build Log

This file tracks what was built in each build session, decisions made during implementation, and any deviations from the plan.

---

## Session 2: Build Phase 1 — Foundation + Data Sources

**Date:** 2026-03-15
**Status:** Complete
**Branch:** `build/phase-1-foundation` (worktree at `.worktrees/build-phase-1/`)
**Python:** 3.13.12 via Homebrew, venv at `.worktrees/build-phase-1/.venv`
**Next phase:** Build — Phase 2 (Agents + UI)

### What Was Built

#### Task 1: Project Scaffolding (DONE)
- `pyproject.toml` with all dependencies
- `.env.example` with API key placeholders
- `src/config.py` with Settings class
- All `__init__.py` files for package structure
- Verified: `pip install -e ".[dev]"` succeeds, config imports clean

#### Task 2: Data Models (DONE)
- `src/models.py` — 17 dataclasses + 3 enums, all with `to_dict()`/`from_dict()` serialization
- `tests/conftest.py` — shared fixtures: `make_sample_data_package()`, `sample_price_data`, `sample_financial_analysis`, `sample_investment_thesis`
- `tests/test_models.py` — 15 tests covering round-trip serialization, computed properties, enum values
- All 15 tests passing

#### Task 3: Yahoo Finance Data Source (DONE)
- `src/data_sources/yahoo_finance.py` — 6 functions, all return `(data, warnings)` tuples
  - `get_financial_statements`, `get_market_data`, `get_price_history`
  - `get_insider_transactions`, `get_institutional_holders`, `get_peer_data`
- `tests/test_yahoo_finance.py` — 11 unit tests + 3 integration tests
- All 14 unit + integration tests passing
- Registered `integration` pytest marker in `pyproject.toml`

#### Task 4: SEC EDGAR Data Source (DONE)
- `src/data_sources/sec_edgar.py` — 5 functions, all return `(data, warnings)` tuples
  - `get_cik_from_ticker(ticker)` — CIK lookup via `company_tickers.json`
  - `get_recent_filings(cik, form_type, count)` — SEC submissions API
  - `get_financial_facts(cik)` — XBRL API, extracts 25+ US-GAAP concepts
  - `get_filing_text(filing_url)` — BeautifulSoup + regex for MD&A/Risk Factors
  - `get_insider_transactions(cik)` — Form 4 XML parsing
- SEC compliance: User-Agent header, 0.1s rate limiting
- `tests/test_sec_edgar.py` — 17 unit tests + 3 integration tests
- All passing (unit + integration with real AAPL data)

#### Task 5: FRED Data Source (DONE)
- `src/data_sources/fred.py` — `get_macro_context()` function
  - Fetches: Fed Funds Rate, GDP growth, unemployment, CPI YoY, yield spread
  - Computes derived values: GDP quarter-over-quarter growth, CPI year-over-year change
  - Handles partial failures (individual series can fail independently)
- `tests/test_fred.py` — 7 unit tests + 1 integration test (skips if no API key)
- All passing

### Test Results (Final)

- **50 unit tests pass** (15 models + 14 Yahoo Finance + 17 SEC EDGAR + 7 FRED)
- **6 integration tests pass** (3 Yahoo Finance + 3 SEC EDGAR), 1 skipped (FRED — no API key)
- **Total: 56 pass, 1 skip, 0 fail**

### Decisions Made During Implementation

1. **Python 3.13 via Homebrew** — system Python was 3.9.6 (too old). Installed 3.13 via `brew install python@3.13`.
2. **Git worktree** — working in `.worktrees/build-phase-1/` on branch `build/phase-1-foundation` to keep main clean.
3. **PeerData model added** — was listed in design.md but missing from Task 2's model list. Added as a proper dataclass.
4. **`get_peer_data` function added** — was missing from yahoo_finance.py's planned function list. Added per design spec.
5. **MarketData.from_dict uses dataclass introspection** — avoids manually listing all 13 fields.
6. **`data_completeness_score` is a `@property`** — computed on access from which data sources are non-None.
7. **SEC EDGAR CIK lookup** uses `company_tickers.json` endpoint (reliable, always up to date) rather than EFTS search index.
8. **XBRL concept extraction** targets 25+ US-GAAP concepts covering income statement, balance sheet, and cash flow. Sorted by date descending so most recent data comes first.
9. **Filing text extraction** uses a two-pass regex approach: specific patterns first (e.g., "Item 7. Management's Discussion..."), then generic ("Item 7."). Falls back to first 15K chars if no section found.
10. **Form 4 parsing** uses Python's built-in `xml.etree.ElementTree` — Form 4s are well-structured XML, not messy HTML.
11. **FRED GDP growth** is computed as quarter-over-quarter (not annualized) from raw GDPC1 series. CPI YoY uses the latest value vs ~12 months prior.
12. **All functions follow the `(data, warnings)` contract** — consistency across all three data sources.

### Deviations from Plan

- **SEC EDGAR `get_filing_text()` returns a dict** (`{mda_text, risk_factors_text}`) instead of a raw string — better structure for downstream consumers.
- **FRED integration test uses `pytest.skip()`** instead of `@pytest.mark.skipif` — cleaner when the skip condition depends on runtime API key availability.

### Inconsistency Resolutions Applied

| # | Issue | Resolution |
|---|---|---|
| 1 | Insider Signal scored against `directional_lean` vs `recommendation` | Using `directional_lean` only (per design.md) to avoid circular dependency |
| 2 | Duplicate paragraph in Task 9 | Will follow corrected version (Orchestrator computes confidence) |
| 3 | `PeerData` model undefined | Added as dataclass in models.py |
| 4 | Data Completeness ownership | Data Collector populates fields, `DataPackage.data_completeness_score` is a computed property |
| 6 | MD&A token budget (15K chars per section vs total) | Will truncate to ~15K chars total across both sections (~4K tokens) |
| 7 | Peer data function missing | Added `get_peer_data()` to yahoo_finance.py |

### What the Next Session Should Do

Continue Session 3: Build Phase 2. Tasks 6-7 are done; Tasks 8-15 remain.

---

## Session 3: Build Phase 2 — Agents + UI (Partial)

**Date:** 2026-03-15
**Status:** In progress (paused after Task 7)
**Branch:** `build/phase-1-foundation` (worktree at `.worktrees/build-phase-1/`)

### What Was Built

#### Task 6: Base Agent (DONE)
- `src/agents/base.py` — `BaseAgent` class with:
  - `_call_claude(system, user, max_tokens)` — sends messages with prompt caching (`cache_control: ephemeral`), retries up to 2x on rate limit or JSON parse failure
  - `_parse_json_response(text)` — extracts JSON from raw, markdown-fenced (```json), bare-fenced (```), or embedded-in-prose responses
  - Token usage and cost logging per call
- `tests/test_base_agent.py` — 13 tests covering JSON parsing (6 cases) and Claude calling (7 cases: success, retry on parse failure, retry exhaustion, rate limit retry, prompt caching, model config, token logging)
- `tests/conftest.py` — added `mock_claude_client` fixture

#### Task 7: Data Collector Agent (DONE)
- `src/agents/data_collector.py` — `DataCollectorAgent` class (standalone, does NOT extend `BaseAgent`):
  - `run(ticker) -> DataPackage` — orchestrates all three data sources
  - EDGAR primary for insider data, yfinance fallback (per design doc: "Do not merge — use one source")
  - Falls back to XBRL-derived financials when yfinance financials unavailable
  - Computes `company_predictability_score` from quarterly revenue coefficient of variation (CV)
  - Predictability: 5 CV bands with linear interpolation (CV < 0.05 → 90-100, ... , CV > 0.50 → 10-29)
  - Defaults to 50 when < 8 quarters available
  - Collects warnings from all sources into `DataPackage.warnings`
- `tests/test_data_collector.py` — 19 tests covering:
  - Happy path (8 tests: package assembly, market data, financials, macro, insider priority, completeness score, peers, filing text)
  - Graceful degradation (5 tests: yfinance failure, EDGAR failure, FRED failure, total failure, warning propagation)
  - Predictability scoring (4 tests: stable, volatile, insufficient data, no data)
  - Insider data priority (2 tests: EDGAR-to-yfinance fallback, no data at all)

### Test Results (Current)

- **88 tests pass, 1 skip, 0 fail**
- Breakdown: 15 models + 14 Yahoo Finance + 17 SEC EDGAR + 7 FRED + 13 Base Agent + 19 Data Collector + 3 integration

### Decisions Made

1. **`_company_name` stored as instance attribute** during `_fetch_market_data` — extracted from yfinance's `company_name` field before building `MarketData` (which doesn't have that field).
2. **Data Completeness score note** — when EDGAR fails but yfinance financials succeed, score still gets the EDGAR 35pts because `DataPackage.data_completeness_score` checks `self.financials is not None`. This is by design: the score measures data availability, not source provenance.
3. **Predictability score uses `statistics.stdev`** (sample standard deviation) — appropriate for revenue samples since we're estimating population volatility from a sample of quarters.

### What the Next Session Should Do

~~Continue from Task 8~~ — see Session 4 below.

---

## Session 4: Build Phase 2 — Financial Analyst Agent

**Date:** 2026-03-22
**Status:** Complete
**Branch:** `main` (no worktree — working directly on main)

### What Was Built

#### Task 8: Financial Analyst Agent (DONE)
- `src/agents/financial_analyst.py` — `FinancialAnalystAgent` class extending `BaseAgent`:
  - `run(data: DataPackage) -> FinancialAnalysis` — sends data via `to_prompt_text()`, parses Claude JSON into dataclass
  - `run_revision(data: DataPackage, request: RevisionRequest) -> RevisedAnalysis` — targeted re-examination for revision loop
  - `_parse_analysis(raw: dict) -> FinancialAnalysis` — robust parsing with fallbacks for company type, ratios, clamped sub-scores
  - `_build_revision_prompt(data, request) -> str` — builds focused revision prompt with questions + original data
- System prompt implements enhanced UChicago methodology with 8-step chain-of-thought:
  1. Company Type Classification
  2. Profitability Analysis (with bps quantification)
  3. Growth Analysis (quarterly momentum emphasis)
  4. Balance Sheet Health (net debt/cash position)
  5. Cash Flow Quality (OCF/NI ratio, FCF margin — "most important step for earnings quality")
  6. Peer Comparison (peer median multiple math)
  7. Forward Outlook 12-Month (base-rate anchored projections)
  8. Overall Assessment (evidence-weighted directional lean)
- **Accuracy-focused analytical discipline** (5 rules in preamble):
  1. Numbers first, narrative second — every claim must cite a figure
  2. Distinguish secular trends from one-time items — require 2-3 data points for trend
  3. Base rate thinking — historical trend is the default projection
  4. Weight recent data more, but don't ignore history
  5. Acknowledge uncertainty honestly — confident wrong > uncertain correct
- Calibrated rubric anchors for LLM-assessed sub-scores (earnings_quality, valuation_clarity, macro_conditions)
- Valuation clarity capped at 60 when no peer data available
- Separate, shorter system prompt for revision requests (cost: ~$0.03 vs ~$0.08 for full analysis)
- `tests/test_financial_analyst.py` — 15 tests:
  - Run tests (8): returns FinancialAnalysis, parses sub-scores, ratios, strengths/concerns, chain-of-thought, verifies prompt content (methodology + rubric anchors)
  - Degraded data tests (4): no macro, no filing text, no peers, empty Claude response
  - Revision tests (3): returns RevisedAnalysis, sends revision context, handles empty response

### Test Results

- **118 tests pass, 0 fail**
- Breakdown: 15 models + 14 Yahoo Finance + 17 SEC EDGAR + 7 FRED + 13 Base Agent + 19 Data Collector + 15 Financial Analyst + 3 integration + remaining

### Decisions Made

1. **Flexible dict structure for profitability/growth/balance_sheet/cash_flow** — Claude returns whatever metrics are relevant to the company type (e.g., FFO for REITs, NIM for banks) rather than forcing fixed keys that would cause hallucination when data is missing.
2. **"Sell-side equity research analyst" persona** — stronger framing than generic "financial analyst" to elicit institutional-quality reasoning.
3. **8-step methodology (added Forward Outlook as explicit step)** — the 12-month outlook was previously buried in "Overall Assessment"; making it a dedicated step forces deeper grounding in the data.
4. **5-rule analytical discipline preamble** — addresses the most common LLM failure modes in financial analysis (narrative bias, trend extrapolation from single data points, over-confident scoring).

### What the Next Session Should Do

Continue from Task 9:
1. **Task 9: Thesis Builder Agent** — narrative synthesis + self-critique → RevisionRequest. Two methods: `run()` and `run_with_revision()`.
2. **Task 10: Orchestrator Agent** — pipeline coordination, data quality gate, revision loop (max 1 iteration, 30s timeout), confidence score post-processing (6-factor weighted average in Python).
3. **Tasks 11-13: Streamlit UI** — charts.py (Plotly), components.py (rendering), app.py (3-tab layout).
4. **Task 14: Error handling** — invalid ticker, missing API key, rate limits.
5. **Task 15: README** — setup, architecture, cost breakdown.

### How to Resume

```bash
cd ~/stock-analyst
source .venv/bin/activate
pytest tests/ -v  # Should show 118 passing
```

---

## Session 5: Build Phase 2 — Thesis Builder Agent

**Date:** 2026-03-22
**Status:** Complete
**Branch:** `main`

### What Was Built

#### Task 9: Thesis Builder Agent (DONE)
- `src/agents/thesis_builder.py` — `ThesisBuilderAgent` class extending `BaseAgent`:
  - `run(data: DataPackage, analysis: FinancialAnalysis) -> InvestmentThesis` — synthesizes data + analysis into narrative thesis with self-critique
  - `run_with_revision(data, analysis, revised: RevisedAnalysis) -> InvestmentThesis` — produces updated thesis incorporating revised analysis (no self-critique — revision is one-and-done)
  - `_parse_thesis(raw, allow_revision)` — robust parsing with recommendation fallback, investment case parsing, self-critique → RevisionRequest extraction
  - `_build_user_prompt(data, analysis)` — sends both raw DataPackage and structured FinancialAnalysis sections
  - `_build_revision_user_prompt(data, analysis, revised)` — prominently places revised assessments for integration
  - Stores `last_confidence_summary` and `last_confidence_driver_details` as instance attributes for Orchestrator post-processing
- System prompt implements narrative synthesis methodology:
  - Evidence-weighted recommendation (BUY/HOLD/SELL with 12-month horizon)
  - Probability-calibrated bull/base/bear scenarios (must sum to 100%)
  - Self-critique step: "What are the weakest assumptions? What contradictions? What would a skeptic challenge?"
  - Requires specific metrics in executive summary (no vague qualitative assertions)
  - Guards against confirmation bias and defaulting to HOLD
  - Includes disclaimer requirement ("not financial advice")
- Separate, shorter system prompt for revision (no self-critique, integrates revised assessments)
- `tests/test_thesis_builder.py` — 18 tests:
  - Run tests (6): returns InvestmentThesis, parses executive summary, bull/base/bear cases with probabilities summing to 1.0, risks/catalysts, all narrative sections, confidence details for Orchestrator
  - Self-critique tests (3): no revision when no gaps, produces RevisionRequest when gaps found, revision has factors to reexamine
  - Revision tests (3): run_with_revision returns thesis, sends revised data in prompt, no new RevisionRequest
  - Degraded data tests (3): no peers, no macro, empty Claude response
  - Prompt tests (3): system prompt has synthesis instructions + self-critique + disclaimer, user prompt includes data + analysis

### Test Results

- **136 tests pass, 0 fail**
- Breakdown: 15 models + 14 Yahoo Finance + 17 SEC EDGAR + 7 FRED + 13 Base Agent + 19 Data Collector + 15 Financial Analyst + 18 Thesis Builder + 3 integration + remaining

### Decisions Made

1. **Self-critique within same Claude call** — cheaper ($0.12 for one call vs $0.24 for two) and faster. Claude generates thesis + self-critique in one pass. The JSON includes a `self_critique` section that may or may not trigger a revision.
2. **Confidence details stored as agent instance attributes** (`last_confidence_summary`, `last_confidence_driver_details`) — the Orchestrator reads these after calling run(). Avoids changing the InvestmentThesis model (which sets confidence=None until the Orchestrator fills it in).
3. **Separate system prompts for initial vs revision** — the revision prompt is shorter (no self-critique needed, no scenario construction — just integrate revised assessments and adjust probabilities/recommendation if warranted).
4. **"Senior investment strategist" persona** — distinct from the Financial Analyst's "sell-side equity research analyst" persona. The strategist synthesizes rather than calculates.
5. **Anti-confirmation-bias guardrails** — prompt explicitly warns against forcing narratives, defaulting to HOLD, and assigning >60% to any single scenario without justification.

### What the Next Session Should Do

~~Continue from Task 10~~ — see Session 6 below.

---

## Session 6: Build Phase 2 — Orchestrator Agent

**Date:** 2026-03-22
**Status:** Complete
**Branch:** `main`

### What Was Built

#### Task 10: Orchestrator Agent (DONE)
- `src/agents/orchestrator.py` — `OrchestratorAgent` class:
  - `run(ticker, progress_callback) -> tuple[DataPackage, FinancialAnalysis | None, InvestmentThesis | None]`
  - Pipeline: Data Collector → data quality gate → Financial Analyst → Thesis Builder → revision loop → confidence post-processing
  - Data quality gate (deterministic, no Claude call): <20 abort, 20-49 warn with LimitationNote, ≥50 proceed
  - Revision loop: max 1 iteration, graceful timeout/error fallback to pre-revision thesis
  - `_compute_confidence(data, analysis) -> ConfidenceScore` — 6-factor weighted average
  - `_compute_insider_signal(data, analysis) -> int` — asymmetric heuristic using lookup table
  - Guardrail: Data Completeness < 30 caps overall score at 40
  - Progress callback `(stage: str, status: str) -> None` for Streamlit streaming
  - Partial failure handling: never crashes, returns what it has
- `tests/test_orchestrator.py` — 32 tests:
  - Pipeline tests (5): returns 3-tuple, calls agents in order, thesis has confidence, ticker uppercased, progress callback
  - Data quality gate (3): abort <20, warn 20-49, proceed ≥50
  - Revision loop (3): no revision when no request, revision triggered, timeout uses pre-revision
  - Confidence score (9): weighted average, 6 drivers, weights sum to 1.0, HIGH/MEDIUM/LOW levels, guardrail cap, summary from TB, driver details from TB
  - Insider signal heuristic (8): all 6 direction×lean combinations + no data + neutral activity
  - Error handling (4): FA failure, TB failure, DC failure, revision failure

### Test Results

- **168 tests pass, 0 fail**

### Decisions Made

1. **Lookup table for insider signal** — `_INSIDER_SIGNAL_MAP` keyed by `(direction, lean)` tuples instead of nested if/elif. Self-documenting, trivially testable, matches design doc table.
2. **OrchestratorAgent does not extend BaseAgent** — it never calls Claude directly. Has its own `__init__` that takes `client` and `model` to pass through to sub-agents.
3. **Revision timeout is best-effort** — checks elapsed time after each sub-call rather than using threading/signals. Falls back to pre-revision thesis on any exception (timeout, API error, etc.).
4. **Impact thresholds for driver labels** — score ≥60 → "positive", <40 → "negative", 40-59 → "neutral". Simple but effective.

### What the Next Session Should Do

Continue from Task 11:
1. **Task 11: Chart Builders** — Plotly charts (price with MAs, revenue/profit bars, margin trends)
2. **Task 12: UI Components** — Streamlit rendering (recommendation badge, confidence gauge, thesis sections, pipeline status)
3. **Task 13: Main App** — `app.py` with 3-tab layout, session state, streaming progress, disclaimer in 2 locations
4. **Task 14: Error handling** — invalid ticker, missing API key, rate limits
5. **Task 15: README**

### How to Resume

```bash
cd ~/stock-analyst
source .venv/bin/activate
pytest tests/ -v  # Should show 168 passing
```

---

## Session 7: Build Phase 2 — UI + Error Handling + Code Review

**Date:** 2026-03-22
**Status:** Complete
**Branch:** `main`

### What Was Built

#### Task 11: Chart Builders (DONE — previous session)
- Already committed at `a2c6b22`

#### Task 12: UI Components (DONE)
- `src/ui/components.py` — 10 Streamlit rendering functions:
  - `render_hero(data, thesis)` — company name + ticker + price + pill-shaped recommendation badge (color-coded BUY/HOLD/SELL)
  - `render_confidence_score(confidence)` — gauge chart + level label + summary + expandable driver breakdown table with impact indicators
  - `render_executive_summary(thesis)` — prose rendering
  - `render_thesis_cases(thesis)` — 3-column bull/base/bear cards with color-coded left borders and probabilities
  - `render_risks_catalysts(thesis)` — 2-column red risks / green catalysts
  - `render_insider_institutional(thesis, data)` — 2-column insider activity + institutional ownership with top holders expander
  - `render_macro_context(thesis, data)` — macro summary with fallback to raw FRED indicators
  - `render_financial_analysis(analysis, data)` — price chart, side-by-side revenue/margin charts, ratio table (from analysis.ratios or market_data fallback), strengths/concerns, expandable Agent Reasoning
  - `render_raw_data(data)` — completeness indicator with score color, source status list, expandable sections per data source, warnings/limitations log
  - `render_disclaimer_footer()` — fixed-position persistent footer with disclaimer text

#### Task 13: Main App (DONE)
- `app.py` — Streamlit entry point with:
  - Wide layout, page title "AI Stock Analyst", 📊 icon
  - Ticker text input + Analyze button
  - `st.status()` pipeline progress with live stage updates via Orchestrator progress_callback closure
  - Session state persistence (data, analysis, thesis, timestamp, elapsed)
  - Hero section + confidence gauge rendered above tabs
  - 3-tab layout: Investment Thesis | Financial Analysis | Raw Data
  - Disclaimers in 2 locations: persistent footer (all pages) + `st.warning()` banner (Thesis tab only)
  - Footer metadata: timestamp + elapsed time

#### Task 14: Error Handling (DONE)
- Ticker format validation via regex (`^[A-Z]{1,5}([.\-][A-Z]{1,2})?$`)
- Missing ANTHROPIC_API_KEY: `st.error`, blocks pipeline
- Invalid ANTHROPIC_API_KEY: catches `anthropic.AuthenticationError`
- Rate limited: catches `anthropic.RateLimitError` with retry guidance
- Missing FRED_API_KEY: `st.info` non-blocking warning
- Unknown ticker (all data sources return empty): `st.error` with suggestion
- Pipeline exception: `st.error` with exception details

#### Code Review (DONE)
- 3-agent parallel review of full codebase (UI, agent pipeline, data sources)
- 5 bugs found, 13 new entries added to `docs/future-enhancements.md` (now 25 total)
- Bugs ranked by impact, fixes specified with code snippets

### Test Results

- **181 tests pass, 0 fail** (unchanged — no test-affecting changes)

### Decisions Made

1. **Components as pure rendering functions** — each takes typed models and calls `st.*` methods. Charts built in `charts.py` are rendered here via `st.plotly_chart()`, keeping Streamlit as the only import boundary.
2. **Graceful degradation cascade** — components try thesis narrative first, fall back to raw data stats, then show "unavailable". Handles Orchestrator's partial-failure returns.
3. **Progress callback closure** — captures `st.status()` container and appends stage updates as a growing checklist.
4. **Ticker validation in app layer** — regex at the presentation layer, not in the Orchestrator. Data sources handle invalid tickers gracefully already; the regex prevents obviously wrong input from wasting API calls.
5. **Error handling in layers** — data sources catch all exceptions, Orchestrator returns partial results, app surfaces actionable messages. Each layer handles what it knows about.

### Bugs Found in Code Review (to fix in next session)

| # | Bug | File | Impact |
|---|-----|------|--------|
| 23 | Operating Expense used as Operating Income in margin chart | `charts.py:179` | Wrong margins |
| 24 | Revised confidence sub-scores ignored after revision | `orchestrator.py:153` | Wrong confidence |
| 13 | Valuation clarity cap not enforced in Python | `orchestrator.py` | Inflated confidence |
| 14 | Ratio table crashes on string values | `components.py:265` | UI crash |
| 25 | MarketData.from_dict() uses Field objects | `models.py:117` | Latent |

### What the Next Session Should Do

1. Fix bugs #23, #24, #13, #14 (quick — 1-5 lines each)
2. Enhancement #3: Deseasonalized predictability score (YoY same-quarter comparison)
3. Enhancement #15: ETF/ADR detection warning
4. Task 15: README
5. Update handoff docs, check off implementation plan, set CLAUDE.md stage to "QA"
6. Manual test: `streamlit run app.py` → AAPL, MSFT, TSLA, XXXXX, SPY

### How to Resume

```bash
cd ~/stock-analyst
source .venv/bin/activate
pytest tests/ -v  # Should show 181 passing
```
