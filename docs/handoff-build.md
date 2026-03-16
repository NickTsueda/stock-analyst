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

Continue from Task 8:
1. Task 8: Financial Analyst Agent (chain-of-thought analysis with UChicago methodology)
2. Task 9: Thesis Builder Agent (narrative synthesis + self-critique → RevisionRequest)
3. Task 10: Orchestrator Agent (pipeline coordination + revision loop + confidence score post-processing)
4. Tasks 11-13: Streamlit UI (charts, components, main app)
5. Tasks 14-15: Error handling + README

### How to Resume

```bash
cd ~/stock-analyst/.worktrees/build-phase-1
source .venv/bin/activate
pytest tests/ -v  # Should show 88 passing, 1 skipped
```
