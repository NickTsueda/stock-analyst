# Known Bugs — Data Collector Output

## Bug 1: Peer discovery is a stub (never finds peers) — FIXED
**File:** `src/data_sources/yahoo_finance.py` (peer discovery functions)
**Issue:** `_find_peers_from_screener()` never populated `peer_tickers` — the variable was initialized as `[]` and never assigned to. The loop that fetches peer fundamentals iterated over nothing.
**Root cause:** The original implementation was a placeholder. yfinance doesn't have a built-in screener API, and the code tried several approaches (recommendations, recommendations_summary) but none of them produce peer ticker symbols.
**Fix:** Replaced the stub with `_fetch_recommended_symbols()` which calls Yahoo Finance's `recommendationsbysymbol` API — the same "People Also Watch" data shown on Yahoo Finance ticker pages. This returns 5 relevant comparison tickers (e.g., AAPL → AMZN, TSLA, GOOG, META, MSFT). The existing market cap band filter (0.25x-4x) and fundamentals fetching logic were already correct and now execute properly.
**Verified:** AAPL: 5 peers (AMZN, TSLA, GOOG, META, MSFT) with real P/E, margin, and growth data. JPM returns financial sector peers (C, BAC, WFC, GS). XOM returns energy/defensive peers (CVX, JNJ, WMT, PG). 3 new unit tests + 1 integration test added, 102 tests pass.

## Bug 2: Insider activity counts all transactions as "buys" — FIXED
**File:** `src/data_sources/sec_edgar.py` (Form 4 URL construction) + `src/agents/data_collector.py` (yfinance fallback)
**Issue:** AAPL shows "Net buys: 75, Transactions: 75" and MSFT shows "Net buys: 99, Transactions: 99". It's impossible that 100% of insider transactions are buys — the `net_buys` field is just the total transaction count, not the buy/sell delta.
**Root cause (two compounding bugs):**
1. **EDGAR Form 4 parsing returned 0 transactions.** `primaryDocument` in SEC submissions points to an XSLT-rendered HTML view (`xslF345X05/wk-form4_*.xml`), not raw XML. `ElementTree.ParseError` was silently caught, returning `[]`. So EDGAR always fell through to the yfinance fallback.
2. **yfinance fallback misclassified all transactions as buys.** The `type` field is empty (`""`) for most yfinance insider transactions. The logic `"sale" in type` never triggered on empty strings, so every transaction scored `+1`.
**Fix:**
1. In `sec_edgar.get_insider_transactions()`: strip XSLT prefix from `primaryDocument` (e.g., `"xslF345X05/form4.xml"` → `"form4.xml"`) to fetch raw XML that `ElementTree` can parse.
2. In `data_collector._resolve_insider_data()`: yfinance fallback now only counts transactions with explicit "sale"/"sell" or "purchase"/"buy" in the type field. Empty/unknown types are neutral (0), not assumed to be buys.
**Verified:** AAPL: -4 net buys / 26 transactions (net selling). MSFT: -9 net buys / 11 transactions (net selling). Both realistic for large-cap tech executives. 3 new tests added, all 94 tests pass.

## Bug 3: SEC filing text extraction returns stubs — FIXED
**File:** `src/data_sources/sec_edgar.py` (filing text extraction)
**Issue:** MD&A sections were returning ~64 characters (a TOC entry). Risk Factors returned just a page number.
**Root cause:** `_extract_section()` used `pattern.search()` which found the first match — always the Table of Contents entry. The TOC contains short lines like "Item 7. Management's Discussion... 21" followed immediately by "Item 7A.", yielding ~64 chars.
**Fix:** Changed `_extract_section()` to use `finditer()` and skip any extraction shorter than 500 chars (TOC entries and cross-references). The actual section content is always thousands of characters. Added `_MIN_SECTION_CHARS = 500` constant.
**Verified:** AAPL and MSFT both return 15,000 chars of real prose for MD&A and Risk Factors. 2 new tests added, all 91 tests pass.

## Bug 4: Institutional ownership always shows 0.0% — FIXED
**File:** `src/data_sources/yahoo_finance.py` (institutional data fetching) + `src/agents/data_collector.py` (total ownership)
**Issue:** Both AAPL and MSFT show "Ownership: 0.0%" which is clearly wrong — both are ~60%+ institutionally held. The `institutional_ownership_pct` field isn't being populated correctly from yfinance.
**Root cause:** yfinance renamed the column from `"% Out"` to `"pctHeld"`. Our code read `"% Out"` which always returned the default `0`. Additionally, summing only top-10 holders underreports total institutional ownership (~33% vs ~65% for AAPL).
**Fix:**
1. In `yahoo_finance.get_institutional_holders()`: read `"pctHeld"` instead of `"% Out"`, multiply by 100 to convert decimal to percentage.
2. In `yahoo_finance.get_market_data()`: also return `heldPercentInstitutions` from `t.info` (the authoritative total across all institutional holders).
3. In `data_collector._fetch_institutional()`: use `heldPercentInstitutions` for the total, fall back to summing top holders if unavailable.
4. Fixed test mutable dict bug: `STUB_MARKET_DATA` was shared across tests and mutated by `data.pop()`. Changed to return fresh copy per test.
**Verified:** AAPL: 65.26%, MSFT: 76.0%. Both match real-world values. 3 new tests added, all 97 tests pass.

## Bug 5: Company Predictability Score is always 50 — FIXED
**File:** `src/agents/data_collector.py` (predictability computation) + `src/data_sources/yahoo_finance.py` (revenue row match)
**Issue:** Both AAPL and MSFT return a predictability score of exactly 50, despite having very stable, predictable quarterly revenue. The score should differ based on revenue volatility (coefficient of variation).
**Root cause (two compounding issues):**
1. **Insufficient data from yfinance.** `t.quarterly_financials` only returns ~5 quarters, but `_compute_predictability_score` requires >= 8. The function always hit the `len < 8` guard and returned the default 50.
2. **Wrong yfinance row matched.** The `"revenue" in label.lower()` search matched "Reconciled Cost Of Revenue" (cost data) before "Total Revenue" — reading the wrong metric entirely.
**Fix:**
1. In `data_collector.py`: Added `_extract_quarterly_revenue_from_xbrl()` to extract quarterly revenue from SEC EDGAR XBRL data (28+ quarters available via `frame` field filtering for 'Q' entries). XBRL is primary source, yfinance fallback.
2. In `yahoo_finance.py`: Changed revenue row search to prefer exact "Total Revenue" match, then "Operating Revenue"/"Revenue", instead of substring matching on "revenue".
3. Added 3 new tests: XBRL quarterly revenue used for scoring, XBRL-to-yfinance fallback, no-revenue-anywhere defaults to 50. Updated 3 existing tests to account for XBRL priority.
**Verified:** AAPL: 53/100 (CV=0.28, seasonal revenue swings). MSFT: 41/100 (CV=0.38, strong growth trend creates high dispersion). Scores now differ and reflect actual revenue characteristics. 99 tests pass.

## Bug 6: Balance sheet includes a stale 5th year of all NaN values — FIXED
**File:** `src/data_sources/yahoo_finance.py` (`_df_to_dict()`)
**Issue:** Every balance sheet line item includes `'2021-06-30 00:00:00': nan` (MSFT) or `'2021-09-30 00:00:00': nan` (AAPL) — a year with no data. This wastes prompt tokens and could confuse Claude. Affected all three financial statements (income, balance sheet, cash flow), not just balance sheet.
**Root cause:** `_df_to_dict()` converted every DataFrame cell to a dict entry, including NaN values. yfinance returns 5 columns for financial statements, but the 5th/oldest year is overwhelmingly NaN (e.g., 63/69 for balance sheet, 33/39 for income, 45/53 for cash flow).
**Fix:** Added NaN filtering to `_df_to_dict()` — skip any value where `val != val` (IEEE 754 NaN check). Also skip rows that end up entirely empty after NaN removal. Line items that have real data in the older year (e.g., Capital Lease Obligations) are preserved.
**Verified:** AAPL output has zero `nan` values. Line items now show only years with actual data. 1 new test added, 103 tests pass.
