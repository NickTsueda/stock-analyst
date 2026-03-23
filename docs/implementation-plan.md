# AI Stock Analyst — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

## Context

**Why:** A UChicago research paper (May 2024) showed GPT-4 could predict earnings with 60.4% accuracy vs 52.7% for human analysts using chain-of-thought prompting. This project builds an enhanced version as a real product — a multi-agent system with transparent confidence scoring and free data sources.

---

**Goal:** Build a multi-agent AI stock analysis tool that takes a ticker symbol and produces an investment thesis with buy/sell/hold recommendation.

**Architecture:** Orchestrated 4-agent pipeline (Orchestrator → Data Collector → Financial Analyst → Thesis Builder). Agents are plain Python classes with typed data contracts. No framework dependencies (no LangChain/CrewAI).

**Tech Stack:** Python 3.11+, `anthropic` SDK (Claude Sonnet), Streamlit UI, free data APIs (SEC EDGAR, Yahoo Finance, FRED), Plotly charts.

---

## Session Workflow

This project follows a stage-gated workflow. Each stage runs in a separate session with handoff docs in between.

| Session | Stage | Produces | Exit Criteria |
|---|---|---|---|
| **Session 1** | Setup + Design | Scaffold, CLAUDE.md, PRD, `design.md`, all handoff docs | All docs committed; file structure matches design schema |
| **Session 2** | Build Phase 1 — Foundation + Data Sources | Models, data sources, `conftest.py`, unit + integration tests | All data source tests pass; `DataPackage` assembles with real AAPL data |
| **Session 3** | Build Phase 2 — Agents + UI | All agents, Streamlit app, charts, components, integration tests | End-to-end run produces rendered report for AAPL; all tests pass |
| **Session 4** | QA | Bug fixes, edge case hardening, README, final polish | All edge cases pass; demo script validated |

> **Consolidation note (2026-03-13):** Reduced from 6 sessions to 4. Sessions 1+2 merged (both produce only docs). Sessions 4+5 merged (agents and UI are tightly coupled — UI can't be tested without agents). This cuts handoff overhead while keeping meaningful session boundaries.

**Rule:** No handoff doc, no moving on. Every session starts with the CLAUDE.md ritual.

---

## File Structure

```
~/stock-analyst/
├── CLAUDE.md                       # Session context (auto-read by Claude Code)
├── app.py                          # Streamlit entry point
├── pyproject.toml                  # Dependencies
├── .env.example                    # ANTHROPIC_API_KEY, FRED_API_KEY
├── .gitignore
├── .streamlit/
│   └── config.toml                 # Theme config (dark mode, accent color)
├── README.md
├── docs/
│   ├── prd.md                      # Product Requirements Document (standalone)
│   ├── design.md                   # Architecture and technical decisions (standalone)
│   ├── handoff-requirements.md     # Requirements → Design handoff
│   ├── handoff-design.md           # Design → Build handoff
│   ├── handoff-implementation-plan.md  # Phased build plan
│   └── handoff-build.md            # Running log of what's been built
├── src/
│   ├── __init__.py
│   ├── models.py                   # All dataclasses (data contracts between agents)
│   ├── config.py                   # Settings, API keys, constants
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py                 # Base agent class (Claude calling, JSON parsing, retry)
│   │   ├── orchestrator.py         # Pipeline coordinator
│   │   ├── data_collector.py       # Data fetching (no Claude)
│   │   ├── financial_analyst.py    # Chain-of-thought statement analysis
│   │   └── thesis_builder.py       # Investment thesis synthesis
│   ├── data_sources/
│   │   ├── __init__.py
│   │   ├── sec_edgar.py            # SEC EDGAR API (10-K, 10-Q, Form 4)
│   │   ├── yahoo_finance.py        # yfinance wrapper
│   │   └── fred.py                 # FRED macro data
│   └── ui/
│       ├── __init__.py
│       ├── components.py           # Streamlit rendering functions
│       └── charts.py               # Plotly chart builders
└── tests/
    ├── __init__.py
    ├── conftest.py                 # Shared fixtures, mock Claude client
    ├── test_models.py
    ├── test_yahoo_finance.py
    ├── test_sec_edgar.py
    ├── test_fred.py
    ├── test_data_collector.py
    ├── test_financial_analyst.py
    ├── test_thesis_builder.py
    └── test_orchestrator.py
```

## Agent Data Flow

```
User Input (ticker)
    │
    ▼
┌─────────────┐
│ Orchestrator │──── coordinates pipeline ───────┐
└─────────────┘                                  │
    │                                            ▼
    │                                  ┌──────────────────┐
    │                                  │  Data Collector   │
    │                                  │  (SEC+YF+FRED)    │
    │                                  └────────┬─────────┘
    │                                           │ DataPackage
    │                                           ▼
    │                                  ┌──────────────────┐
    │                                  │ Financial Analyst │
    │                                  │  (CoT analysis)   │
    │                                  └────────┬─────────┘
    │                                           │ FinancialAnalysis
    │                                           ▼
    │                                  ┌──────────────────┐
    │                                  │  Thesis Builder   │
    │                                  │  (synthesis)      │
    │                                  └────────┬─────────┘
    │                                           │ InvestmentThesis
    │◄──────────────────────────────────────────┘
    ▼
  Streamlit UI (3 tabs: Thesis | Analysis | Raw Data)
```

---

## Session 1: Setup + Design

### Task 0: Scaffold Project Structure

**Files:**
- Create: `~/stock-analyst/CLAUDE.md`
- Create: `~/stock-analyst/docs/prd.md`
- Create: `~/stock-analyst/docs/design.md`
- Create: `~/stock-analyst/docs/handoff-requirements.md`
- Create: `~/stock-analyst/docs/handoff-design.md`
- Create: `~/stock-analyst/docs/handoff-implementation-plan.md`
- Create: `~/stock-analyst/docs/handoff-build.md` (placeholder)
- Create: `~/stock-analyst/.streamlit/config.toml`

- [x] **Step 1: Create project folder and doc structure**
- [x] **Step 2: Write CLAUDE.md**
- [x] **Step 3: Write docs/prd.md** (full PRD with product overview, user journey, V2 considerations)
- [x] **Step 4: Write docs/handoff-requirements.md**
- [x] **Step 5: Write .streamlit/config.toml**
- [x] **Step 6: git init and commit**
- [x] **Step 7: Update CLAUDE.md current stage to "Design"**

---

### Task 0.5: Architecture + Design Doc (same session)

- [x] **Step 1: Write docs/design.md** — Standalone architecture doc (system architecture, agent specs, data models, confidence algorithm, data sources, technical constraints, UI architecture). Separated from PRD — previously combined in one spec file.
- [x] **Step 2: Write docs/handoff-design.md** — summarize design decisions and what Build Phase 1 needs
- [x] **Step 3: Update CLAUDE.md stage to "Build — Phase 1"**
- [ ] **Step 4: Commit** *(to be done at start of Session 2 before building)*

---

## Session 2: Build Phase 1 — Foundation + Data Sources

### Task 1: Project Scaffolding (Code)

**Files:**
- Create: `~/stock-analyst/pyproject.toml`
- Create: `~/stock-analyst/.gitignore`
- Create: `~/stock-analyst/.env.example`
- Create: `~/stock-analyst/src/__init__.py`, `src/agents/__init__.py`, `src/data_sources/__init__.py`, `src/ui/__init__.py`, `tests/__init__.py`
- Create: `~/stock-analyst/src/config.py`

- [x] **Step 1: Create pyproject.toml and code structure**
```toml
[project]
name = "stock-analyst"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "anthropic>=0.40.0",
    "streamlit>=1.40.0",
    "yfinance>=0.2.40,<0.3.0",
    "fredapi>=0.5.2",
    "plotly>=5.24.0",
    "requests>=2.32.0",
    "beautifulsoup4>=4.12.0",
    "python-dotenv>=1.0.0",
    "pandas>=2.2.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-mock>=3.14"]

[build-system]
requires = ["setuptools>=75.0"]
build-backend = "setuptools.build_meta"
```

- [x] **Step 2: Create .gitignore, .env.example, all init.py files**

- [x] **Step 3: Create src/config.py**
```python
import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    FRED_API_KEY: str = os.getenv("FRED_API_KEY", "")
    CLAUDE_MODEL: str = "claude-sonnet-4-20250514"
    SEC_USER_AGENT: str = "StockAnalyst/1.0 (stock-analyst-project@example.com)"
    FRED_SERIES = {
        "fed_funds_rate": "FEDFUNDS",
        "gdp": "GDPC1",
        "unemployment": "UNRATE",
        "cpi": "CPIAUCSL",
        "yield_spread": "T10Y2Y",
    }

settings = Settings()
```

- [x] **Step 4: Verify setup**
Run: `cd ~/stock-analyst && pip install -e ".[dev]" && python -c "from src.config import settings; print('OK')"`

- [x] **Step 5: Commit**
```bash
git add -A && git commit -m "Initialize project structure with dependencies and config"
```

### Task 2: Data Models

**Files:**
- Create: `~/stock-analyst/src/models.py`
- Create: `~/stock-analyst/tests/test_models.py`
- Create: `~/stock-analyst/tests/conftest.py` (initial shared fixtures)

- [x] **Step 1: Write test for model serialization**
```python
def test_data_package_round_trip():
    """DataPackage can serialize to dict and back."""
    pkg = make_sample_data_package()
    d = pkg.to_dict()
    restored = DataPackage.from_dict(d)
    assert restored.ticker == pkg.ticker

def test_data_package_to_prompt_text():
    """to_prompt_text() produces structured text with key sections."""
    pkg = make_sample_data_package()
    text = pkg.to_prompt_text()
    assert "Revenue" in text
    assert pkg.ticker in text
```

- [x] **Step 2: Run tests to verify they fail**

- [x] **Step 3: Implement models.py**

Key dataclasses:
- `FinancialStatements` — multi-year income/balance/cash flow
- `MarketData` — current price, ratios, sector
- `InsiderActivity` — transactions + net sentiment
- `InstitutionalData` — top holders
- `MacroContext` — FRED macro indicators
- `FilingText` — extracted MD&A and risk factors text
- `DataPackage` — complete data collector output (aggregates all above)
- `FinancialRatio` — name, values by year, trend, assessment
- `FinancialAnalysis` — financial analyst output (includes LLM-assessed sub-scores: `earnings_quality`, `valuation_clarity`, `macro_conditions` — each 0-100)
- `InvestmentCase` — narrative + drivers + probability
- `ConfidenceScore` — numeric score (0-100) + structured explanation with drivers
- `InvestmentThesis` — thesis builder output (bull/base/bear + recommendation + confidence score)
- `RevisionRequest` — Thesis Builder's request for Financial Analyst re-examination (questions, factors, context)
- `RevisedAnalysis` — Financial Analyst's revision response (revised assessments, sub-scores, rationale)
- `LimitationNote` — warning for partial/degraded results (source, message, severity)
- Enums: `Recommendation`, `ConfidenceLevel`, `CompanyType`

**Confidence Score model (`ConfidenceScore`):**
```python
@dataclass
class ConfidenceDriver:
    factor: str              # One of 6 factors (e.g., "Data Completeness", "Earnings Quality")
    score: int               # 0-100 sub-score for this factor
    weight: float            # Factor weight (e.g., 0.20)
    impact: str              # "positive", "negative", "neutral"
    detail: str              # Plain-English explanation

@dataclass
class ConfidenceScore:
    score: int               # 0-100 overall (weighted average of 6 factor sub-scores)
    level: ConfidenceLevel   # Derived: >=70 High, 40-69 Medium, <40 Low
    summary: str             # 1-2 sentence plain-English explanation (from Claude)
    drivers: list[ConfidenceDriver]  # 6 drivers
```

**6-factor weighted model (see design.md Section 4 for full details):**

| Factor | Weight | Computed By |
|---|---|---|
| Data Completeness | 20% | Python (programmatic — source success weighted by criticality) |
| Earnings Quality | 25% | Claude (LLM-assessed with calibrated rubric) |
| Valuation Clarity | 20% | Claude (LLM-assessed with calibrated rubric) |
| Company Predictability | 20% | Python (programmatic — coefficient of variation) |
| Insider Signal | 10% | Python + Claude (asymmetric heuristic scored against `directional_lean`) |
| Macro Conditions | 5% | Claude (LLM-assessed with calibrated rubric) |

Final score = weighted average computed in Python post-processing. Claude provides qualitative `detail` strings and `summary`, plus the LLM-assessed sub-scores using rubric anchors. Programmatic factors are computed entirely in Python.

**UI display:** Score shown as a colored gauge (green/yellow/red) with expandable driver breakdown. Users see *exactly* why confidence is high or low and can make their own judgment.

Each major model gets `to_dict()`, `from_dict()` classmethods.
`DataPackage` gets `to_prompt_text()` that formats data as structured text for Claude prompts.
`DataPackage` also gets `data_completeness_score: int` (0-100) computed from which data sources returned successfully.

- [x] **Step 4: Run tests to verify they pass**

- [x] **Step 5: Create tests/conftest.py (initial fixtures)**

Create shared test fixtures needed across the test suite:
- `sample_price_data` fixture — minimal `pd.DataFrame` with OHLCV columns
- `sample_financials` fixture — minimal financials dict matching model schema
- `make_sample_data_package()` factory — fully populated `DataPackage` with stub values; accepts optional overrides

This is created here because Task 2 defines the models these fixtures conform to, and Tasks 3-6 depend on them.

- [x] **Step 6: Commit**
```bash
git commit -m "Define data models, serialization, and shared test fixtures"
```

---

### Data Sources

### Task 3: Yahoo Finance Data Source

**Files:**
- Create: `~/stock-analyst/src/data_sources/yahoo_finance.py`
- Create: `~/stock-analyst/tests/test_yahoo_finance.py`

- [x] **Step 1: Write tests** — mock `yfinance.Ticker`, verify output shape matches model expectations
- [x] **Step 2: Run tests to verify they fail**
- [x] **Step 3: Implement yahoo_finance.py**

Functions:
- `get_financial_statements(ticker) -> dict` (income, balance, cash flow — all available years)
- `get_market_data(ticker) -> dict` (price, P/E, market cap, sector, etc.)
- `get_price_history(ticker, period="1y") -> list[dict]`
- `get_insider_transactions(ticker) -> list[dict]`
- `get_institutional_holders(ticker) -> list[dict]`
- `get_peer_data(ticker, industry, market_cap) -> list[dict]` *(added — was missing from plan)*

Each function: try/except, return partial data + warnings on failure.

**Resilience note:** `yfinance` is an unofficial scraper that breaks periodically when Yahoo changes their site. Every function must return gracefully with a warning on failure (never crash). If yfinance is fully down, the Data Collector still produces a DataPackage using SEC EDGAR data — the analysis degrades gracefully with a lower Data Completeness score and a `LimitationNote` warning, consistent with the PRD's graceful degradation philosophy.

- [x] **Step 4: Run tests to verify they pass**
- [x] **Step 5: Write one integration test** (marked `@pytest.mark.integration`) that fetches real AAPL data
- [x] **Step 6: Commit**
```bash
git commit -m "Add Yahoo Finance data source"
```

### Task 4: SEC EDGAR Data Source

**Files:**
- Create: `~/stock-analyst/src/data_sources/sec_edgar.py`
- Create: `~/stock-analyst/tests/test_sec_edgar.py`

- [x] **Step 1: Write tests** — mock HTTP responses with sample SEC JSON, test filing text extraction with real HTML fixture
- [x] **Step 2: Run tests to verify they fail**
- [x] **Step 3: Implement sec_edgar.py**

Functions:
- `get_cik_from_ticker(ticker) -> str` — uses SEC company tickers JSON
- `get_recent_filings(cik, form_type="10-K", count=3) -> list[dict]` — uses SEC submissions endpoint
- `get_financial_facts(cik) -> dict` — **XBRL API.** Fetch structured financial data from `data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json`. Returns clean JSON for revenue, net income, total assets, EPS, etc. This is the **primary source for financial statement numbers** — reliable, structured, no HTML parsing needed.
- `get_filing_text(filing_url) -> str` — **Best-effort qualitative extraction.** Fetch HTML, clean with BeautifulSoup (strip tags, normalize whitespace), then regex to extract MD&A (Item 7) and Risk Factors (Item 1A). Truncate to ~15K chars per section.
  - **Extraction strategy:** BeautifulSoup `get_text()` first, then regex patterns for section headers (case-insensitive: "Item 7", "ITEM 7", "Item 7.", "Item 7 —"). Extract text between matched header and next "Item" header.
  - **Fallback:** If section extraction fails (no regex match), grab the first 15K characters of cleaned text and let Claude handle it. Log a warning.
  - **Scope limit:** Only attempt filings from 2000+. Older filings use inconsistent formats.
  - **Key design principle:** This is a *nice-to-have enhancement*, not a critical dependency. The Financial Analyst agent can produce a solid analysis from XBRL numbers alone. When text extraction succeeds, the analysis is richer (MD&A context, risk factors). When it fails, the pipeline still works.
- `get_insider_transactions(cik) -> list[dict]` — Form 4 data

**Critical:** Must set `User-Agent` header to `"StockAnalyst/1.0 (contact@example.com)"` per SEC policy. Rate limit: `time.sleep(0.1)` between requests.

> **Hybrid approach (2026-03-13):** Uses XBRL API for reliable structured financial numbers + BeautifulSoup-cleaned HTML for qualitative text. Even if text extraction is flaky, the analysis always works because XBRL data is rock-solid. Added `beautifulsoup4` to dependencies.

- [x] **Step 4: Run tests to verify they pass**
- [x] **Step 5: Commit**
```bash
git commit -m "Add SEC EDGAR data source with filing text extraction"
```

### Task 5: FRED Data Source

**Files:**
- Create: `~/stock-analyst/src/data_sources/fred.py`
- Create: `~/stock-analyst/tests/test_fred.py`

- [x] **Step 1: Write tests** — mock `fredapi.Fred`
- [x] **Step 2: Run tests to verify they fail**
- [x] **Step 3: Implement fred.py**

Function: `get_macro_context() -> dict` — fetches latest values for FEDFUNDS, GDPC1, UNRATE, CPIAUCSL, T10Y2Y. Calculates YoY changes where appropriate.

- [x] **Step 4: Run tests to verify they pass**
- [x] **Step 5: Commit**
```bash
git commit -m "Add FRED macro data source"
```

---

### Session 2 Handoff

- [x] **Append to docs/handoff-build.md:** What was built, decisions made, deviations from plan
- [x] **Update CLAUDE.md stage to "Build — Phase 2"**
- [x] **Commit handoff docs**

---

## Session 3: Build Phase 2 — Agents + UI

### Task 6: Base Agent

**Files:**
- Create: `~/stock-analyst/src/agents/base.py`

- [x] **Step 1: Write tests** — JSON extraction from various response formats (raw JSON, markdown-fenced JSON), retry behavior
- [x] **Step 2: Run tests to verify they fail**
- [x] **Step 3: Add Claude fixtures to existing tests/conftest.py**

Append to the existing `conftest.py` (created in Task 2):
- `mock_claude_client` fixture — `MagicMock` simulating `anthropic.Anthropic()` with configurable response
- `sample_agent_response` fixture — minimal structured agent output dict

- [x] **Step 4: Implement base.py**
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

- [x] **Step 5: Run tests to verify they pass**
- [x] **Step 6: Commit**
```bash
git commit -m "Add base agent class with Claude calling infrastructure"
```

### Task 7: Data Collector Agent

**Files:**
- Create: `~/stock-analyst/src/agents/data_collector.py`
- Create: `~/stock-analyst/tests/test_data_collector.py`

- [x] **Step 1: Write tests** — mock all data sources, verify DataPackage assembly, verify warnings for missing data
- [x] **Step 2: Run tests to verify they fail**
- [x] **Step 3: Implement data_collector.py**

`DataCollectorAgent.run(ticker: str) -> DataPackage` — calls all data sources sequentially, assembles results, populates warnings, computes `data_completeness_score`. Does NOT call Claude.

**Note:** `DataCollectorAgent` is a standalone class — it does NOT extend `BaseAgent` since it never calls Claude.

- [x] **Step 4: Run tests to verify they pass**
- [x] **Step 5: Commit**
```bash
git commit -m "Add Data Collector agent"
```

### Task 8: Financial Analyst Agent

**Files:**
- Create: `~/stock-analyst/src/agents/financial_analyst.py`
- Create: `~/stock-analyst/tests/test_financial_analyst.py`

- [x] **Step 1: Write tests** — mock Claude response with realistic JSON, verify parsing into FinancialAnalysis. Test with incomplete data.
- [x] **Step 2: Run tests to verify they fail**
- [x] **Step 3: Implement financial_analyst.py**

`FinancialAnalystAgent.run(data: DataPackage) -> FinancialAnalysis`

System prompt implements the enhanced UChicago methodology:
1. Classify company type (Growth/Value/Dividend/Turnaround/Cyclical)
2. Profitability analysis (margins, ROE, ROA — with trends across years)
3. Growth analysis (revenue/earnings growth, acceleration/deceleration)
4. Balance sheet health (D/E, current ratio, cash position)
5. Cash flow quality (OCF vs net income, FCF trend)
6. Overall assessment with strengths and concerns

Requests structured JSON response matching FinancialAnalysis schema.

- [x] **Step 4: Run tests to verify they pass**
- [x] **Step 5: Commit**
```bash
git commit -m "Add Financial Analyst agent with chain-of-thought prompting"
```

### Task 9: Thesis Builder Agent

**Files:**
- Create: `~/stock-analyst/src/agents/thesis_builder.py`
- Create: `~/stock-analyst/tests/test_thesis_builder.py`

- [x] **Step 1: Write tests** — mock Claude response, verify all thesis sections populated
- [x] **Step 2: Run tests to verify they fail**
- [x] **Step 3: Implement thesis_builder.py**

`ThesisBuilderAgent.run(data: DataPackage, analysis: FinancialAnalysis) -> InvestmentThesis`

Synthesizes: financial analysis + MD&A excerpts + insider activity + institutional data + macro context into:
- Executive summary (2-3 paragraphs, forward-looking)
- Bull/Base/Bear cases with probabilities (must sum to 100%)
- Buy/Hold/Sell recommendation
- **Confidence score (0-100) with structured explanation** — 6 weighted factors: Data Completeness, Earnings Quality, Valuation Clarity, Company Predictability, Insider Signal, Macro Conditions. Each factor gets a driver entry explaining its impact on the score.
- Adaptive investment horizon (by company type)
- Key risks and catalysts
- Insider signal interpretation
- Macro alignment assessment

**Confidence score implementation:**

After Claude returns the thesis JSON (with qualitative driver details and summary), Python post-processing:
After Claude returns the thesis JSON (with qualitative driver details and summary), the **Orchestrator** performs post-processing:
1. Collects sub-scores: Data Completeness (from Orchestrator), Earnings Quality + Valuation Clarity + Macro Conditions (from `FinancialAnalysis`), Company Predictability (from `DataPackage`), Insider Signal (Python heuristic using `directional_lean` + recommendation)
2. Computes weighted average of 6 factor sub-scores → final score (0-100)
3. Derives `level` from score: ≥70 High, 40-69 Medium, <40 Low
4. Applies guardrails (Data Completeness < 30 caps overall at 40)
5. Assembles the final `ConfidenceScore` dataclass with sub-scores + Claude's qualitative text

- [x] **Step 4: Run tests to verify they pass**
- [ ] **Step 5: Commit**
```bash
git commit -m "Add Thesis Builder agent with multi-source synthesis"
```

### Task 10: Orchestrator Agent

**Files:**
- Create: `~/stock-analyst/src/agents/orchestrator.py`
- Create: `~/stock-analyst/tests/test_orchestrator.py`

- [x] **Step 1: Write tests** — mock all sub-agents, verify pipeline flow, test error-in-middle returns partial results
- [x] **Step 2: Run tests to verify they fail**
- [x] **Step 3: Implement orchestrator.py**

`OrchestratorAgent.run(ticker: str, progress_callback=None) -> tuple[DataPackage, FinancialAnalysis | None, InvestmentThesis | None]`

Pipeline:
1. Run Data Collector → report progress
2. **Data quality gate (deterministic Python rule, no Claude call):**
   - If `data_completeness_score < 20`: abort analysis, return `(DataPackage, None, None)` with error. UI shows which data sources failed.
   - If `20 ≤ score < 50`: proceed, but append a `LimitationNote` warning: "Data completeness score is {score}/100. Analysis may be incomplete."
   - If `score ≥ 50`: proceed normally.
3. Run Financial Analyst → report progress
4. Run Thesis Builder (initial thesis) → report progress
5. **Revision loop:** If Thesis Builder's self-critique identifies substantive gaps, it produces a `RevisionRequest`. Send to Financial Analyst for `RevisedAnalysis`, then re-run Thesis Builder with revised input. Max 1 iteration, 30s timeout — if exceeded, use pre-revision thesis.
6. **Confidence Score computation** (Python post-processing — weighted average of 6 factor sub-scores)
7. Return: `tuple[DataPackage, FinancialAnalysis | None, InvestmentThesis | None]`
8. **On agent error:** Return partial results, never crash.

> **Simplification (2026-03-13):** Replaced the Claude API "proceed/abort" decision call with a deterministic Python rule. Faster, cheaper ($0 vs ~$0.003), and more predictable for demos.

`progress_callback` is `(stage: str, status: str) -> None` for Streamlit updates.

- [x] **Step 4: Run tests to verify they pass**
- [x] **Step 5: Commit**
```bash
git commit -m "Add Orchestrator agent with pipeline coordination"
```

---

## Session 3 (cont.): Streamlit UI

### UI Visual Specification

This section defines the intended appearance and layout of the final Streamlit app. Tasks 11–13 should conform to this spec.

**Investment Thesis Tab:**
- **Hero section:** Company name (large, bold) + ticker (muted, monospace) side by side. Current stock price prominently sized. Recommendation badge: pill-shaped, color-coded (green = BUY, yellow = HOLD, red = SELL).
- **Confidence Score gauge:** Semicircular gauge, range 0–100. Color zones: red (0-39), yellow (40-69), green (70-100). Numeric score at center. 1–2 sentence summary below. Expandable "Score Driver Breakdown" section (collapsed by default) with table: Factor | Impact | Weight | Detail.
- **Executive Summary:** 2–3 paragraph narrative, rendered as prose.
- **Bull / Base / Bear Cases:** 3-column card layout. Each card: scenario label, probability %, short narrative (3–5 sentences), key drivers as bulleted list.
- **Risks & Catalysts:** 2-column layout (left = Risks, right = Catalysts).
- **Insider & Institutional Signals:** Recent insider transactions summary, institutional ownership changes. Graceful "Data unavailable" if empty.
- **Macro Context Summary:** Short paragraph on relevant macro factors.
- **Footer:** Disclaimer, cost of analysis ("Analysis cost: ~$X.XX"), timestamp ("Generated at YYYY-MM-DD HH:MM UTC").

**Financial Analysis Tab:**
- Price chart: 1Y daily close with 50-day and 200-day moving averages.
- Revenue & profit bar chart: grouped bars for revenue, gross profit, net income.
- Margin trends line chart: gross margin %, operating margin %, net margin % over time.
- Ratio table: key ratios (P/E, P/S, EV/EBITDA, D/E, Current Ratio, ROE), sortable, current value + 3-year average.
- Chain-of-thought reasoning: expandable section (collapsed by default) titled "Agent Reasoning."

**Raw Data Tab:**
- One expandable section per data source (Price Data, Financials, Insider Transactions, Macro Indicators, Filing Text).
- Data Completeness Indicator at top: horizontal bar or table showing each source, status (OK / Partial / Failed), and score contribution.
- Warnings / Limitations Log: collapsible section listing all `LimitationNote` entries from the run.

---

### Task 11: Chart Builders

**Files:**
- Create: `~/stock-analyst/src/ui/charts.py`

- [x] **Step 1: Implement chart functions**
  - `price_chart(price_history) -> go.Figure` — line chart with 50/200 day MA
  - `revenue_profit_chart(financials) -> go.Figure` — grouped bar chart
  - `margin_trends_chart(ratios) -> go.Figure` — multi-line chart
  - `ratio_table(ratios) -> pd.DataFrame` — formatted for st.dataframe()

Dark-theme friendly colors. Consistent styling.

- [x] **Step 2: Smoke test** — verify functions return valid Plotly figures
- [x] **Step 3: Commit**
```bash
git commit -m "Add Plotly chart builders for financial visualization"
```

### Task 12: UI Components

**Files:**
- Create: `~/stock-analyst/src/ui/components.py`

- [x] **Step 1: Implement rendering functions**
  - `render_recommendation_badge(rec, confidence_score)` — colored badge (green=Buy, red=Sell, yellow=Hold) with confidence score gauge
  - `render_confidence_score(confidence: ConfidenceScore)` — colored gauge (0-100), summary text, expandable driver breakdown table showing each factor, its impact (+/-), and explanation. This is the key user-empowerment feature.
  - `render_executive_summary(thesis)` — hero section
  - `render_thesis_cases(thesis)` — 3-column bull/base/bear layout
  - `render_risks_catalysts(thesis)` — 2-column risks and catalysts
  - `render_financial_analysis(analysis, data)` — charts + ratios + expandable chain-of-thought
  - `render_raw_data(data)` — expandable sections per data category
  - `render_pipeline_status(stages)` — progress indicator via st.status()

- [x] **Step 2: Commit**
```bash
git commit -m "Add Streamlit UI components for analysis display"
```

### Task 13: Main App

**Files:**
- Create: `~/stock-analyst/app.py`

- [x] **Step 1: Implement app.py**

Layout:
- Page config (wide, title, icon)
- Header with title + description
- Input: ticker text input + Analyze button
- Pipeline progress indicator (st.status)
- Results in 3 tabs: Investment Thesis | Financial Analysis | Raw Data
- Executive summary with recommendation badge above tabs
- Footer with disclaimer

Session state for persisting results across Streamlit reruns.

**Disclaimer placement (2 locations in V1, both required):**
1. **Persistent footer bar (all pages):** Always visible, subtle styling (small font, muted color, thin top border). Use `st.markdown` with fixed-position CSS or a consistent footer component.
2. **Yellow info banner (Investment Thesis tab only):** Rendered at top of tab, above hero section. Use `st.warning()`. Text: "AI-generated analysis for educational purposes only. Not financial advice. Always consult a qualified financial advisor before making investment decisions."

- [ ] **Step 2: Manual test** — `streamlit run app.py`, analyze AAPL *(deferred to next session)*
- [x] **Step 3: Commit**
```bash
git commit -m "Add Streamlit app with full analysis pipeline UI"
```

---

### Polish

### Task 14: Error Handling + Edge Cases

- [x] **Step 1:** Ensure every data source returns gracefully on failure (no uncaught exceptions)
- [x] **Step 2:** Add `st.error()` for common failures (invalid ticker, missing API key, rate limited)
- [ ] **Step 3:** Test edge cases: penny stock, foreign ADR, recent IPO, invalid ticker *(deferred to next session)*
- [x] **Step 4:** Commit

### Task 14.5: Code Review + Bug Discovery (added)

- [x] **Step 1:** 3-agent parallel review of full codebase (UI, agent pipeline, data sources)
- [x] **Step 2:** 5 bugs found, 13 new entries added to `docs/future-enhancements.md` (25 total)
- [x] **Step 3:** Commit

### Task 15: README

- [x] **Step 1:** Write README with: setup instructions, architecture diagram, example output description, cost breakdown, link to UChicago paper
- [x] **Step 2:** Commit
```bash
git commit -m "Add README with setup instructions and architecture overview"
```

### Task 15.5: Pre-Launch Bug Fixes + Enhancements (added)

- [x] **Step 1:** Fix bug #23 — remove "Operating Expense" from margin chart candidates
- [x] **Step 2:** Fix bug #24 — incorporate revised_subscores into confidence computation
- [x] **Step 3:** Fix bug #13 — enforce valuation_clarity cap at 60 when no peers
- [x] **Step 4:** Fix bug #14 — safe format for ratio table values
- [x] **Step 5:** Enhancement #3 — deseasonalized predictability score (YoY same-quarter CV)
- [x] **Step 6:** Enhancement #15 — ETF/ADR/mutual fund detection warning
- [x] **Step 7:** Update tests for all fixes
- [x] **Step 8:** Commit

### Session 3 Handoff

- [x] **Append to docs/handoff-build.md:** What was built, decisions made, deviations from plan
- [x] **Update CLAUDE.md stage to "QA"**
- [x] **Commit handoff docs**

---

## Session 4: QA Review (Fresh Session)

- [ ] **Step 1: Open fresh Claude Code session** — `cd ~/stock-analyst && claude`
- [ ] **Step 2: Follow CLAUDE.md session start ritual** — read all handoff docs
- [ ] **Step 3: Run QA review prompt:**
```
Review the code in /src as a senior QA engineer. Identify anything that is
broken, incomplete, insecure, or inconsistent with /docs/design.md.

Do not suggest improvements beyond scope — focus only on what is wrong or
missing relative to the spec.
```
- [ ] **Step 4: Fix identified issues**
- [ ] **Step 5: Run full verification suite** (see table below)
- [ ] **Step 6: Update CLAUDE.md stage to "Complete"**
- [ ] **Step 7: Final commit**

---

## Verification

| Phase | Command | Expected |
|---|---|---|
| Foundation | `pip install -e ".[dev]" && python -c "from src.config import settings"` | No errors |
| Data Sources | `pytest tests/test_yahoo_finance.py tests/test_sec_edgar.py tests/test_fred.py` | All pass |
| Integration | `pytest -m integration` | Real data fetched for AAPL |
| Agents | `pytest tests/` | All pass |
| End-to-end | `streamlit run app.py` → enter AAPL | Full thesis in <90 seconds, cost <$0.40 |
| Edge cases | Test: TSLA (volatile), JNJ (mature), ARM (recent IPO, ~2.5 years), XXXXX (invalid) | Graceful handling |

## Cost Per Analysis (Sonnet)

| Component | Est. Cost |
|---|---|
| Financial Analyst (~25K input, ~3K output) | ~$0.08 |
| Thesis Builder (~35K input, ~4K output) | ~$0.12 |
| Orchestrator decision (deterministic Python) | $0.00 |
| **Total per company** | **~$0.15-0.20** |
