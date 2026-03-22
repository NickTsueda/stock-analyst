# Known Bugs — Data Collector Output

## Bug 1: Peer discovery is a stub (never finds peers)
**File:** `src/data_sources/yahoo_finance.py` lines 235-298
**Issue:** `_find_peers_from_screener()` never populates `peer_tickers`, so the loop at line 273 never executes. The function always returns an empty list.
**Impact:** No peer comparison data is ever included in the DataPackage. The Financial Analyst agent will have no competitive context.
**Fix:** Either use yfinance's `Ticker.recommendations` to extract peer tickers, or maintain a hardcoded sector-to-tickers mapping for common industries.

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

## Bug 5: Company Predictability Score is always 50
**File:** `src/agents/data_collector.py` (predictability computation)
**Issue:** Both AAPL and MSFT return a predictability score of exactly 50, despite having very stable, predictable quarterly revenue. The score should differ based on revenue volatility (coefficient of variation).
**Impact:** The Confidence Score's "Company Predictability" factor (20% weight) is always the same default value instead of reflecting actual revenue stability.

## Bug 6: Balance sheet includes a stale 5th year of all NaN values
**Issue:** Every balance sheet line item includes `'2021-06-30 00:00:00': nan` (MSFT) or `'2021-09-30 00:00:00': nan` (AAPL) — a year with no data. This wastes prompt tokens and could confuse Claude.
**Impact:** Minor — token waste and potential noise in Claude's analysis.
