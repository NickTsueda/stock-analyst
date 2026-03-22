# Future Enhancements

Improvements identified during development that are out of scope for current bug fix sessions but worth incorporating later.

---

## 1. yfinance Column Name Resilience

**Source:** Bug 4 fix session (2026-03-22)
**Files:** `src/data_sources/yahoo_finance.py` (all functions)
**Priority:** High — yfinance breaks silently when column names change

**Problem:** yfinance is an unofficial scraper that renames DataFrame columns without warning. Bug 4 was caused by `"% Out"` → `"pctHeld"`. Bug 5 revealed `quarterly_financials` row labels can match wrong rows. These are silent failures — no exceptions, just wrong data.

**Proposed fix:** Add a defensive column-matching layer:
1. Log a warning when an expected column is missing (e.g., `"% Out" not found in columns: ['pctHeld', 'Shares', ...]`).
2. Try multiple known column names in priority order (e.g., `["pctHeld", "% Out", "Pct Held"]`).
3. Consider a `_get_column(df, candidates, default)` utility that tries a list of column name candidates.

**Impact:** Prevents future silent data loss from yfinance schema changes. Would have caught Bug 4 immediately instead of producing 0.0%.

---

## 2. Reduce Redundant yfinance Ticker Instantiation

**Source:** Bug 4 fix session (2026-03-22)
**Files:** `src/data_sources/yahoo_finance.py` — each function creates `yf.Ticker(ticker)` independently
**Priority:** High — reduces API calls and latency

**Problem:** Each `get_*` function creates its own `yf.Ticker(ticker)` object. For a single analysis, we create 5-6 Ticker objects for the same ticker. Each one may trigger separate HTTP requests to Yahoo Finance.

**Proposed fix:** Create a `YahooFinanceClient` class that instantiates `yf.Ticker` once and shares it across all data fetches. This would:
- Reduce HTTP calls (yfinance caches some data on the Ticker object)
- Allow `heldPercentInstitutions` from `t.info` to be read alongside market data without a separate Ticker instantiation
- Eliminate the current workaround of passing `_held_pct_institutions` through `_fetch_market_data` as an instance attribute

**Trade-off:** Changes the stateless function API to a stateful class. But `DataCollectorAgent` already manages the lifecycle.

---

## 3. Deseasonalized Predictability Score

**Source:** Bug 5 fix session (2026-03-22)
**File:** `src/agents/data_collector.py` — `_compute_predictability_score()`
**Priority:** Medium — affects Confidence Score accuracy for seasonal companies

**Problem:** The current CV (coefficient of variation) method measures raw quarterly revenue dispersion. Companies with strong seasonal patterns (e.g., AAPL holiday quarter ~$140B vs summer ~$85B) score as "moderately volatile" (CV=0.28, score=53) even though their revenue is highly *predictable* — the seasonal pattern is known and consistent.

Similarly, high-growth companies (e.g., MSFT revenue grew from ~$26B to ~$70B/quarter over 7 years) have high CV (0.38, score=41) despite very consistent growth.

**Proposed fix:** Compare same-quarter year-over-year instead of quarter-to-quarter. For each quarter Q, compute `abs(revenue_Q_thisYear - revenue_Q_lastYear) / revenue_Q_lastYear`. The CV of these YoY deltas would capture whether the company deviates from its own seasonal/growth pattern — which is what "predictability" actually means.

**Expected impact:**
- AAPL: Score would increase significantly (seasonal pattern is very consistent)
- MSFT: Score would increase (growth is steady quarter-over-quarter)
- Truly erratic companies (biotech, crypto) would still score low

**Trade-off:** Requires >= 8 quarters of same-quarter pairs (i.e., 2+ years of data minimum, ideally 3+). EDGAR XBRL provides this easily.

---

## 4. Test Stub Mutation Safety

**Source:** Bug 4 fix session (2026-03-22)
**File:** `tests/test_data_collector.py`
**Priority:** Medium — prevents flaky test ordering bugs

**Problem:** Module-level stub dicts (e.g., `STUB_MARKET_DATA`) are shared mutable objects. When production code calls `data.pop()`, it mutates the original dict. Tests that run later see a dict without the popped keys, causing order-dependent failures. Fixed for `STUB_MARKET_DATA` with `side_effect=lambda: (dict(STUB_MARKET_DATA), [])`, but other stubs (`STUB_FINANCIALS`, etc.) have the same latent risk.

**Proposed fix:** Either:
1. Apply the `side_effect=lambda` copy pattern to all mutable stub patches, or
2. Use `pytest` fixtures (`@pytest.fixture`) that return fresh copies, or
3. Freeze stubs with `types.MappingProxyType` to catch mutations as errors

**Impact:** Prevents future intermittent test failures from shared mutable state.

---

## 5. yfinance Revenue Row Robustness

**Source:** Bug 5 investigation (2026-03-22)
**File:** `src/data_sources/yahoo_finance.py` — `get_financial_statements()`
**Priority:** Low — already mitigated by XBRL primary source

**Problem:** The original code used `"revenue" in label.lower()` to find revenue in `quarterly_financials`, which matched "Reconciled Cost Of Revenue" (cost data) before "Total Revenue". Fixed to prefer exact "Total Revenue" match, but yfinance row labels can change across versions.

**Proposed improvement:** Add a warning when the matched label isn't "Total Revenue" so we catch future yfinance schema changes early. Also consider logging the matched label for debugging. Lower priority since XBRL is now the primary revenue source for predictability scoring.

---

## 6. EDGAR Form 4 Parse Failure Visibility

**Source:** Bug 2 fix session (2026-03-22)
**File:** `src/data_sources/sec_edgar.py` — `_parse_form4()`
**Priority:** Medium — silent failures hide data quality issues

**Problem:** `_parse_form4()` catches `ElementTree.ParseError` and returns `[]` with no logging. Before Bug 2 was fixed, this silently discarded all insider data from EDGAR, falling through to the yfinance fallback which produced wrong results. More broadly, several EDGAR functions catch exceptions and return empty data without emitting warnings — the caller has no way to distinguish "no data exists" from "fetch failed."

**Proposed fix:**
1. Add warnings to the return value when `ParseError` or other exceptions occur in `_parse_form4()`, so `DataCollectorAgent` can surface them.
2. Audit all EDGAR functions for similar silent-failure patterns. Functions like `get_financial_facts()` and `get_filing_text()` log warnings but don't return them consistently.
3. Consider returning `(data, warnings)` tuples from `_parse_form4()` for consistency with the rest of the codebase.

**Impact:** Would have made Bug 2 visible immediately — `run_collector.py` output would have shown "Form 4 XML parsing failed" warnings instead of silently falling back to yfinance.

---

## 7. XSLT Prefix Handling for All EDGAR Filing Types

**Source:** Bug 2 fix session (2026-03-22)
**File:** `src/data_sources/sec_edgar.py` — `get_insider_transactions()`
**Priority:** Low — only Form 4 is affected currently

**Problem:** SEC EDGAR's `primaryDocument` field includes XSLT rendering prefixes (e.g., `xslF345X05/`) for Form 4 filings. The fix strips this prefix for Form 4 URLs, but the same pattern could affect other filing types if we ever fetch additional form types directly. The `get_recent_filings()` function used for 10-K/10-Q isn't affected because those filing URLs point to HTML documents that we process with BeautifulSoup (not XML parsing).

**Proposed fix:** Factor the XSLT prefix stripping into a shared utility (e.g., `_strip_xslt_prefix(doc_name)`) and apply it in `get_recent_filings()` as well. This is defensive — currently only matters for Form 4, but prevents future bugs if we add Form 3, Form 5, or other XML filing types.

---

## 8. Peer Discovery Resilience — Fallback When Yahoo API Changes

**Source:** Bug 1 fix session (2026-03-22)
**File:** `src/data_sources/yahoo_finance.py` — `_fetch_recommended_symbols()`
**Priority:** Medium — undocumented API dependency
**Status:** New (identified during Bug 1 fix)

**Problem:** The peer discovery fix uses Yahoo Finance's `recommendationsbysymbol` API endpoint, which is undocumented and could change or disappear without notice. Currently if it fails, `get_peer_data()` returns empty with a warning — graceful, but the Financial Analyst gets no competitive context.

**Proposed fix:** Add a secondary fallback: a curated sector-to-tickers mapping for the most common sectors (Technology, Healthcare, Financials, Energy, Consumer Staples, etc.) with 8-10 large-cap tickers each. When the Yahoo API fails, select 5 from the matching sector within the market cap band. This is static and requires maintenance but provides guaranteed baseline coverage.

**Trade-off:** A hardcoded mapping is maintenance burden and becomes stale. Could mitigate by generating/refreshing it periodically from a reliable source. The current Yahoo API has worked reliably across AAPL, MSFT, JPM, and XOM in testing.

---

## 9. Parallel Peer Data Fetching

**Source:** Bug 1 fix session (2026-03-22)
**File:** `src/data_sources/yahoo_finance.py` — `get_peer_data()`
**Priority:** Low — performance optimization, not correctness
**Status:** New

**Problem:** `get_peer_data()` fetches each peer's fundamentals sequentially via `yf.Ticker(pt).info`. For 5 peers, this is 5 serial HTTP calls (~2-3 seconds each = ~10-15 seconds total). The Data Collector already takes 15-20 seconds; this adds significant latency.

**Proposed fix:** Use `concurrent.futures.ThreadPoolExecutor` to fetch all 5 peers in parallel. Since each `yf.Ticker().info` call is I/O-bound, threads work well here. Could reduce peer fetch time from ~12s to ~3s.

**Trade-off:** Slightly more complex code. Also need to respect Yahoo Finance rate limits — 5 parallel requests should be fine, but worth monitoring.

---

## 10. Balance Sheet Stale NaN Year (Bug 6 — Still Open)

**File:** Data sources returning a 5th year of all-NaN values
**Priority:** Low — minor token waste, cosmetic

**Status:** Lowest priority bug. Filter out years where all values are NaN before including in DataPackage.
