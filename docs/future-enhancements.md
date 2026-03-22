# Future Enhancements

Improvements identified during development that are out of scope for current bug fix sessions but worth incorporating later.

## Stack Rank (by impact on analysis quality and user experience)

| Rank | # | Enhancement | Priority | Rationale |
|------|---|-------------|----------|-----------|
| 1 | 23 | Operating Expense in margin chart candidates | **Bug** | Wrong operating margin — cost used as income |
| 2 | 24 | Revised confidence sub-scores ignored after revision | **Bug** | Confidence score uses original scores, not revised ones |
| 3 | 13 | Valuation clarity cap enforcement in Python | **Bug** | Claude may ignore prompt instruction, inflating confidence score |
| 4 | 14 | Ratio table crash on string values | **Bug** | Claude returns "28.5x" instead of 28.5 → format crash in UI |
| 5 | 25 | MarketData.from_dict() uses Field objects as defaults | **Bug (latent)** | Partial dicts produce Field objects instead of values |
| 6 | 1 | yfinance column name resilience | High | Silent data loss — next yfinance update could break any field |
| 7 | 2 | Reduce redundant Ticker instantiation | High | 5-6 Ticker objects per analysis = unnecessary API calls + latency |
| 8 | 12 | Data Collector parallelization | High | 25s → 10-15s collection time — critical for Streamlit UX |
| 9 | 15 | ETF/ADR/mutual fund handling | High | These pass ticker validation but have different data structures |
| 10 | 6 | EDGAR Form 4 parse failure visibility | Medium | Silent failures hide data quality issues from the pipeline |
| 11 | 11 | Financial statement token optimization | Medium | 2-3K wasted tokens per statement — adds up across 3 statements |
| 12 | 3 | Deseasonalized predictability score | Medium | Confidence Score accuracy for seasonal/growth companies |
| 13 | 16 | Caching layer for repeated analyses | Medium | V2 item from PRD — same ticker re-analyzed wastes time + money |
| 14 | 17 | PDF/image export of analysis | Medium | V2 item — users want to save/share results |
| 15 | 8 | Peer discovery fallback | Medium | Undocumented API dependency, but working reliably now |
| 16 | 18 | Sector-specific analysis frameworks | Medium | V2 item — banks, REITs, SaaS need different metrics |
| 17 | 19 | Earnings call transcript integration | Medium | V2 item — adds forward-looking qualitative signal |
| 18 | 4 | Test stub mutation safety | Medium | Latent risk, not actively causing failures |
| 19 | 20 | Streamlit UI tests | Medium | No automated UI testing — all verification is manual |
| 20 | 9 | Parallel peer data fetching | Low | ~10s savings, subset of #12 |
| 21 | 5 | yfinance revenue row robustness | Low | Mitigated by XBRL primary source |
| 22 | 7 | XSLT prefix handling for all filings | Low | Defensive — only Form 4 affected today |
| 23 | 21 | Cost tracking per analysis | Low | BaseAgent logs costs but they're not aggregated or surfaced to UI |
| 24 | 22 | Analysis comparison (A vs B ticker) | Low | V2 item — users want side-by-side comparison |

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

## 10. ~~Balance Sheet Stale NaN Year~~ — RESOLVED

**Status:** Fixed in Bug 6 session (2026-03-22). NaN values are now filtered in `_df_to_dict()`.

---

## 11. Financial Statement Token Optimization

**Source:** Bug 6 fix session (2026-03-22)
**File:** `src/data_sources/yahoo_finance.py` — `_df_to_dict()`, `get_financial_statements()`
**Priority:** Medium — reduces Claude prompt token usage

**Problem:** yfinance returns 39-69 line items per financial statement, many of which are redundant (e.g., "Net Income", "Net Income Common Stockholders", "Net Income Including Noncontrolling Interests", "Diluted NI Availto Com Stockholders" all have identical values for most companies). Sending all of them to the Financial Analyst wastes ~2-3K tokens per statement and adds noise.

**Proposed fix:** Curate a list of ~15-20 essential line items per statement type (revenue, COGS, gross profit, operating income, net income, EPS for income; total assets, total liabilities, equity, cash, debt for balance sheet; operating/investing/financing cash flow). Filter `_df_to_dict()` output to only include these, or add a `slim=True` mode that the Data Collector can use.

**Trade-off:** May miss unusual but meaningful items (e.g., large impairments, restructuring charges). Could keep a "notable items" pass that includes anything > 10% of revenue that isn't in the curated list.

---

## 12. Data Collector Parallelization

**Source:** Bug 6 fix session (2026-03-22) — observed sequential data source fetching
**File:** `src/agents/data_collector.py` — `run()`
**Priority:** Medium — performance improvement for Phase 2 UX

**Problem:** `DataCollectorAgent.run()` fetches data sources sequentially: yfinance market data → yfinance financials → yfinance price history → yfinance insiders → yfinance institutional → SEC EDGAR → FRED → peers. The total wall time is 20-30 seconds. Since yfinance, EDGAR, and FRED are independent, they could run in parallel.

**Proposed fix:** Use `concurrent.futures.ThreadPoolExecutor` to run the three independent source groups in parallel:
- Group 1: All yfinance calls (market_data, financials, price_history, insider, institutional)
- Group 2: All SEC EDGAR calls (CIK → XBRL + filings + insider)
- Group 3: FRED macro data

Peer data must wait for market_data (needs market cap), and insider resolution must wait for both EDGAR and yfinance insiders.

**Expected impact:** Could reduce total collection time from ~25s to ~10-15s. Important for Streamlit UX — users will be watching a loading spinner.

**Trade-off:** More complex error handling. Thread safety of yfinance Ticker objects should be verified (each group uses its own Ticker instance, so likely safe).

---

## 13. Valuation Clarity Cap Not Enforced in Python (BUG)

**Source:** Phase 2 code review (2026-03-22)
**File:** `src/agents/financial_analyst.py` — `_parse_analysis()` (line 327)
**Priority:** Bug — affects confidence score accuracy

**Problem:** The design doc and system prompt say "If no peer data is provided, cap valuation_clarity at 60." The prompt tells Claude this at line 153, but `_parse_analysis()` only clamps to [0, 100] — it does NOT enforce the peer-data cap in Python. Claude may ignore the prompt instruction and return valuation_clarity=75 even with no peers.

Since valuation_clarity has 20% weight in the confidence score, an uncapped value inflates the overall score by up to ~3 points. This is a systematic bias that always pushes confidence higher for companies without peers (foreign filers, niche industries, recent IPOs).

**Fix:** In `_parse_analysis()`, accept the `DataPackage` as a parameter (or add a post-parse step). If `data.peers is None or len(data.peers) == 0`, cap `valuation_clarity` at 60. Alternatively, enforce this in `OrchestratorAgent._compute_confidence()` since it already has access to the DataPackage.

**Recommended location:** `OrchestratorAgent._compute_confidence()` — add after line 203:
```python
# Cap valuation_clarity at 60 when no peer data (per design doc)
if data.peers is None or len(data.peers) == 0:
    valuation_clarity = min(valuation_clarity, 60)
```

---

## 14. Ratio Table Crashes on Non-Numeric Values (BUG)

**Source:** Phase 2 code review (2026-03-22)
**File:** `src/ui/components.py` — `render_financial_analysis()` (line 265)
**Priority:** Bug — crashes the UI for certain Claude responses

**Problem:** The ratio table formats values with `f"{r.values[sorted_years[0]]:.2f}"`. But `FinancialRatio.values` comes from Claude's JSON response. Claude may return string values like `"28.5x"`, `"N/A"`, or `"N/M"` instead of numeric floats. The `.2f` format specifier will raise `ValueError` on non-float values.

**Fix:** Wrap in a try/except:
```python
if r.values:
    sorted_years = sorted(r.values.keys(), reverse=True)
    val = r.values[sorted_years[0]]
    try:
        row["Current"] = f"{float(val):.2f}"
    except (ValueError, TypeError):
        row["Current"] = str(val)
else:
    row["Current"] = "—"
```

---

## 15. ETF/ADR/Mutual Fund Ticker Handling

**Source:** Phase 2 code review (2026-03-22)
**Files:** `app.py` (validation), `src/agents/data_collector.py` (data assembly)
**Priority:** High — these tickers pass validation but produce misleading results

**Problem:** The ticker validator accepts any 1-5 letter symbol. ETFs (SPY, QQQ), ADRs (BABA, TSM), and mutual funds (VTSAX) all pass validation and enter the pipeline, but:
- ETFs have no SEC filings (no CIK) — EDGAR returns nothing
- ADRs may have limited SEC data (Form 20-F instead of 10-K)
- Mutual funds have no price history or insider data
- The Financial Analyst prompt is designed for single companies, not funds

The analysis proceeds but produces misleading results — e.g., an ETF thesis that says "BUY SPY" based only on price momentum with no fundamental analysis.

**Proposed fix (choose one):**
1. **Warning-based:** Detect instrument type from yfinance's `info.quoteType` field (returns "ETF", "MUTUALFUND", "EQUITY", etc.). Show a warning: "This appears to be an ETF. Analysis is designed for individual equities and may not be applicable."
2. **Block-based:** Refuse non-equity tickers with an error message. Simpler but less flexible.
3. **Adapt-based (V2):** Different analysis frameworks for ETFs vs equities. Most complex but best UX.

**Recommendation:** Option 1 (warning) — graceful and informative. The `quoteType` field is already available from the yfinance `info` dict fetched in `get_market_data()`.

---

## 16. Caching Layer for Repeated Analyses

**Source:** PRD V2 considerations
**Priority:** Medium — saves time and API costs

**Problem:** Every analysis hits all APIs from scratch and makes 2-3 Claude calls (~$0.15-0.20). If a user re-analyzes the same ticker within an hour, all data and analysis is re-fetched/re-generated.

**Proposed fix:** Two-tier cache:
1. **Data cache:** Cache `DataPackage` for 1 hour (keyed by ticker). Data doesn't change minute-to-minute. Use `shelve` or a simple JSON file in a `.cache/` directory.
2. **Analysis cache:** Cache the full `(DataPackage, FinancialAnalysis, InvestmentThesis)` tuple for 4-6 hours. Claude's analysis of the same data is deterministic enough.

Show "Cached result from HH:MM" with a "Re-analyze" button to bypass cache.

**Trade-off:** Stale data risk. TTLs should be short enough that price movements don't make cached analysis misleading. Consider showing staleness warnings when price has moved >2% since cache time.

---

## 17. PDF/Image Export of Analysis

**Source:** PRD V2 considerations
**Priority:** Medium — users want to save/share results

**Problem:** Analysis results exist only in the Streamlit session. Users can't save or share them.

**Proposed fix:** Add an "Export" button with two options:
1. **PDF export:** Use `fpdf2` or `reportlab` to generate a formatted PDF with charts (as images), thesis text, and confidence breakdown. Include the disclaimer.
2. **Screenshot:** Use `streamlit-extras` or browser-native screenshot functionality.

**Trade-off:** PDF generation adds a dependency and complexity. The simpler V1 approach could be a "Copy as Markdown" button that copies the thesis text to clipboard.

---

## 18. Sector-Specific Analysis Frameworks

**Source:** PRD V2 considerations
**Priority:** Medium — current one-size-fits-all misses sector nuances

**Problem:** The Financial Analyst uses the same prompt for all companies. Banks need NIM, efficiency ratio, loan loss provisions. REITs need FFO, NOI, cap rate. SaaS companies need ARR, NRR, Rule of 40. The current prompt handles this via "flexible dict structure" in profitability/growth, relying on Claude to pick relevant metrics. This works okay but doesn't enforce sector-specific analysis depth.

**Proposed fix:** Add sector-specific prompt extensions that append to the base system prompt when `CompanyType` or `sector` matches. E.g., for banks, append a "Banking-Specific Analysis" section requiring NIM trend, credit quality, capital ratios. The `DataCollectorAgent` could also fetch sector-specific data fields.

**Trade-off:** Maintenance burden of N sector-specific prompts. Start with 3-4 most common (Tech, Financials, Healthcare, REITs) and fall back to the generic prompt.

---

## 19. Earnings Call Transcript Integration

**Source:** PRD V2 considerations
**Priority:** Medium — adds forward-looking qualitative signal

**Problem:** SEC filings are backward-looking. The most valuable forward-looking signal for public companies is the quarterly earnings call, where management discusses guidance, strategy, and competitive dynamics. This is currently not captured.

**Proposed fix:** Integrate a transcript source (e.g., Financial Modeling Prep API, or scrape from public filings). Extract the Q&A section (most information-dense) and truncate to ~4K tokens. Feed to the Financial Analyst as an additional input section.

**Trade-off:** Adds a dependency and API cost. Transcripts can be 30K+ words — need aggressive summarization to fit token budgets. Could use a dedicated "Transcript Summarizer" sub-agent.

---

## 20. Streamlit UI Automated Testing

**Source:** Phase 2 code review (2026-03-22)
**Files:** `src/ui/components.py`, `app.py`
**Priority:** Medium — all UI verification is currently manual

**Problem:** There are 0 tests for the UI layer (components.py, app.py). All verification is manual (`streamlit run app.py` → enter AAPL → visually check). This means:
- UI regressions from model changes aren't caught
- Edge cases (None data, empty strings, partial pipeline results) aren't systematically verified
- Refactoring components is risky without test coverage

**Proposed fix:** Use `streamlit.testing` (AppTest) framework to test components in isolation:
```python
from streamlit.testing.v1 import AppTest

def test_app_renders_with_no_data():
    at = AppTest.from_file("app.py")
    at.run()
    assert at.error == []  # No crashes
```

Also add unit tests for pure logic in components (e.g., `_validate_ticker`, color mapping).

**Trade-off:** Streamlit testing is relatively new and has limitations (can't test all widget interactions). Focus on smoke tests and data-edge-case tests rather than full interaction testing.

---

## 21. Cost Tracking Surfaced to UI

**Source:** Phase 2 code review (2026-03-22)
**Files:** `src/agents/base.py` (logging), `app.py` (display)
**Priority:** Low — cost logging exists but isn't aggregated or shown

**Problem:** `BaseAgent._call_claude()` logs token counts and cost estimates per call (line 54-58), but these are only in Python logs. The user never sees them. The design spec mentions "Analysis cost: ~$X.XX" in the footer, but this isn't implemented.

**Proposed fix:** Add a `total_cost` accumulator to `BaseAgent` (or the Orchestrator) that sums across all Claude calls in a pipeline run. Surface it in the Thesis tab footer: "Analysis cost: ~$0.18 (2 Claude calls, 45K tokens)".

**Implementation:** Add `self._total_cost = 0.0` and `self._total_tokens = 0` to `BaseAgent.__init__()`, increment in `_call_claude()`, and expose via properties. The Orchestrator can read from each sub-agent after the run.

---

## 22. Analysis Comparison (A vs B Ticker)

**Source:** PRD V2 considerations
**Priority:** Low — single-ticker is the V1 scope

**Problem:** Retail investors often compare two stocks ("Should I buy AAPL or MSFT?"). The current tool only analyzes one ticker at a time. Users must run two analyses and mentally compare.

**Proposed fix:** Add a "Compare" mode with a second ticker input. Run both analyses in parallel (using two Orchestrator instances), then render a side-by-side comparison view: recommendation badges, confidence scores, key metrics, and a synthesis paragraph highlighting the key differences.

**Trade-off:** Doubles API costs (~$0.30-0.40 per comparison). The synthesis paragraph would need a separate Claude call. This is a significant feature addition, not a quick enhancement.

---

## 23. Operating Expense in Margin Chart Candidates (BUG)

**Source:** Phase 2 code review (2026-03-22)
**File:** `src/ui/charts.py` — `margin_trends_chart()` (line 179-180)
**Priority:** Bug — produces wrong operating margins

**Problem:** The `operating_income` candidate list includes `"Operating Expense"`:
```python
operating_income = _find_line_item(income, [
    "Operating Income", "EBIT", "Operating Expense",
])
```

`Operating Expense` is a cost, not income. If a financial statement has a key exactly named "Operating Expense" and not "Operating Income" or "EBIT", the chart would use the expense value to compute operating margin. Since expenses are typically positive large numbers (and roughly equal to revenue), this would show ~100% operating margin — completely wrong.

**Fix:** Remove `"Operating Expense"` from the candidate list. Replace with `"Operating Income Loss"` (common XBRL label) if needed:
```python
operating_income = _find_line_item(income, [
    "Operating Income", "EBIT", "Operating Income Loss",
])
```

**Risk assessment:** In practice, yfinance labels this "Operating Income" and XBRL-derived data maps to "Operating Income" in `_financials_from_xbrl()`. So this hasn't caused issues yet, but it's a landmine waiting for an edge case.

---

## 24. Revised Confidence Sub-Scores Ignored After Revision Loop (BUG)

**Source:** Phase 2 code review (2026-03-22)
**File:** `src/agents/orchestrator.py` — `run()` (line 153) and `_compute_confidence()` (line 202-206)
**Priority:** Bug — wrong confidence score when revision occurs

**Problem:** When the revision loop triggers (lines 144-149), the Financial Analyst may return updated sub-scores in `RevisedAnalysis.revised_subscores` (e.g., changing `earnings_quality` from 60 to 75). However, `_compute_confidence()` on line 153 receives only the **original** `analysis` object:

```python
# Line 153:
confidence = self._compute_confidence(data, analysis)  # ← original analysis

# Lines 202-206 in _compute_confidence:
earnings_quality = analysis.earnings_quality      # ← ORIGINAL, not revised
valuation_clarity = analysis.valuation_clarity    # ← ORIGINAL, not revised
macro_conditions = analysis.macro_conditions      # ← ORIGINAL, not revised
```

The `RevisedAnalysis.revised_subscores` dict is consumed by the Thesis Builder for narrative adjustments but never fed back into the confidence computation.

**Impact:** The confidence score becomes inconsistent with the revised thesis narrative. If revision changes `earnings_quality` from 60 to 75 (weight 25%), the confidence score is ~3.75 points too low. This matters because it can cross the LOW/MEDIUM/HIGH threshold boundaries (40 and 70).

**Fix:** In `_compute_confidence()`, accept an optional `revised_subscores` parameter and merge before computing:
```python
def _compute_confidence(self, data, analysis, revised_subscores=None):
    earnings_quality = analysis.earnings_quality
    valuation_clarity = analysis.valuation_clarity
    macro_conditions = analysis.macro_conditions

    if revised_subscores:
        earnings_quality = revised_subscores.get("earnings_quality", earnings_quality)
        valuation_clarity = revised_subscores.get("valuation_clarity", valuation_clarity)
        macro_conditions = revised_subscores.get("macro_conditions", macro_conditions)
```

Then pass the revised scores from `_run_revision()` through to `_compute_confidence()`.

---

## 25. MarketData.from_dict() Uses Field Objects as Defaults (BUG — latent)

**Source:** Phase 2 code review (2026-03-22)
**File:** `src/models.py` — `MarketData.from_dict()` (line 116-118)
**Priority:** Bug (latent) — only triggers on partial dicts, which don't occur in normal use

**Problem:** The `from_dict()` implementation iterates `cls.__dataclass_fields__`:
```python
return cls(**{k: d.get(k, v) for k, v in cls.__dataclass_fields__.items()
              if k in d or hasattr(cls, k)})
```

Here `v` is a `dataclasses.Field` object, not the default value. When a key is missing from `d`, `d.get(k, v)` returns the Field object itself, not the field's default. Since `hasattr(cls, k)` is always True for dataclass fields, every field is included regardless of whether it's in the dict.

In normal operation, `to_dict()` always includes all 13 fields, so `d.get(k, v)` always finds the key and returns the correct value. But if `from_dict()` is called on a partial dict (e.g., from external input or a test), it would construct a `MarketData` with Field objects as attribute values, causing subtle downstream failures.

**Compare to correct implementations in the same file:**
- `MacroContext.from_dict()`: `cls(**{k: d.get(k) for k in cls.__dataclass_fields__})` — returns None for missing keys
- `FilingText.from_dict()`: `cls(**{k: d.get(k, "") for k in cls.__dataclass_fields__})` — returns "" for missing keys

**Fix:** Align with the pattern used by other models:
```python
@classmethod
def from_dict(cls, d: dict) -> MarketData:
    return cls(**{k: d.get(k) for k in cls.__dataclass_fields__})
```

Or use explicit defaults matching the dataclass field defaults.
