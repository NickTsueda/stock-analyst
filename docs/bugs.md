# Known Bugs — Data Collector Output

## Bug 1: Peer discovery is a stub (never finds peers)
**File:** `src/data_sources/yahoo_finance.py` lines 235-298
**Issue:** `_find_peers_from_screener()` never populates `peer_tickers`, so the loop at line 273 never executes. The function always returns an empty list.
**Impact:** No peer comparison data is ever included in the DataPackage. The Financial Analyst agent will have no competitive context.
**Fix:** Either use yfinance's `Ticker.recommendations` to extract peer tickers, or maintain a hardcoded sector-to-tickers mapping for common industries.

## Bug 2: Insider activity counts all transactions as "buys"
**File:** `src/agents/data_collector.py` (insider data assembly)
**Issue:** AAPL shows "Net buys: 75, Transactions: 75" and MSFT shows "Net buys: 99, Transactions: 99". It's impossible that 100% of insider transactions are buys — the `net_buys` field is just the total transaction count, not the buy/sell delta.
**Impact:** Claude will be told insiders are massively buying when they're likely selling — completely misleading for investment analysis.

## Bug 3: SEC filing text extraction returns stubs
**File:** `src/data_sources/sec_edgar.py` (filing text extraction)
**Issue:** MD&A sections are returning ~64 characters (e.g., "and Analysis of Financial Condition and Results of Operations 35"). This is a table-of-contents entry, not the actual MD&A text. Risk Factors returns just "5" or "16" (a page number).
**Impact:** The Financial Analyst agent gets no actual qualitative filing content to reason over. This is a critical data gap — the UChicago paper's approach relies on financial statement analysis, and MD&A provides key management context.

## Bug 4: Institutional ownership always shows 0.0%
**File:** `src/data_sources/yahoo_finance.py` (institutional data fetching)
**Issue:** Both AAPL and MSFT show "Ownership: 0.0%" which is clearly wrong — both are ~60%+ institutionally held. The `institutional_ownership_pct` field isn't being populated correctly from yfinance.
**Impact:** Confidence Score's insider/institutional signal will be inaccurate.

## Bug 5: Company Predictability Score is always 50
**File:** `src/agents/data_collector.py` (predictability computation)
**Issue:** Both AAPL and MSFT return a predictability score of exactly 50, despite having very stable, predictable quarterly revenue. The score should differ based on revenue volatility (coefficient of variation).
**Impact:** The Confidence Score's "Company Predictability" factor (20% weight) is always the same default value instead of reflecting actual revenue stability.

## Bug 6: Balance sheet includes a stale 5th year of all NaN values
**Issue:** Every balance sheet line item includes `'2021-06-30 00:00:00': nan` (MSFT) or `'2021-09-30 00:00:00': nan` (AAPL) — a year with no data. This wastes prompt tokens and could confuse Claude.
**Impact:** Minor — token waste and potential noise in Claude's analysis.
