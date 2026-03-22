# AI Stock Analyst — CLAUDE.md

## What We're Building

A multi-agent AI stock analysis tool that takes a ticker symbol and produces a complete investment thesis with buy/sell/hold recommendation. Inspired by the UChicago paper (May 2024) where GPT-4 predicted earnings with 60.4% accuracy vs 52.7% for human analysts using chain-of-thought prompting on financial statements.

**Target user:** Self-directed retail investors managing $25K-$500K portfolios who want institutional-quality analysis without Bloomberg/FactSet costs.

**Key differentiator:** Every analysis includes a Confidence Score (0-100) with a transparent breakdown of 6 weighted factors (data completeness, earnings quality, valuation clarity, company predictability, insider signal, macro conditions). Users see exactly why the system is confident or uncertain, enabling better judgment.

**Architecture:** 4-agent pipeline (Orchestrator → Data Collector → Financial Analyst → Thesis Builder) using Python, Claude Sonnet, and Streamlit. No LangChain/CrewAI — plain Python classes with typed data contracts.

**Purpose:** Portfolio piece demonstrating PM product thinking + multi-agent AI system design.

## Current Stage

Options:
- Session 1: Setup + Design (PRD, architecture, handoff docs)
- Session 2: Build — Phase 1 (Foundation + Data Sources)
- Session 3: Build — Phase 2 (Agents + UI)
- Session 4: QA (reviewing and fixing)
- Complete

Current: **Build — Phase 2 (Agents + UI)**

## Session Start Ritual

Before doing anything in this session, read the following documents in order:

1. /docs/prd.md
2. /docs/design.md
3. /docs/bugs.md
4. /docs/handoff-requirements.md
5. /docs/handoff-design.md
6. /docs/handoff-implementation-plan.md
7. /docs/handoff-build.md

After reading, summarize:
- What has been built so far
- What decisions were made and why
- What this session needs to accomplish

Do not begin any work until I confirm your summary is accurate.

Note: Skip any file that is empty or does not yet exist.

## Bug Fix Sessions

**Before starting Phase 2 (Agents + UI), all Data Collector bugs must be fixed.** The data quality is critical — the Financial Analyst and Thesis Builder agents reason over this data, so wrong inputs produce wrong investment theses.

**Bug tracker:** `docs/bugs.md` (canonical list with file locations and impact)

**Test script:** `python run_collector.py AAPL` — run after each fix to verify output against real-world values.

### Debugging Approach

Use the `superpowers:systematic-debugging` skill for each bug. Do NOT guess-and-fix. The process is:
1. Investigate root cause (trace data flow, read error messages, check how yfinance/EDGAR actually return data)
2. Find working examples or reference implementations
3. Form a hypothesis, test minimally
4. Write a failing test, then fix, then verify output against known real-world values

### Priority Order

Fix in this order (most dangerous first — bugs that feed Claude actively wrong data):

1. **Bug 3: SEC filing text returns stubs** — MD&A is ~64 chars (a TOC entry, not content). Risk Factors returns a page number. The whole thesis depends on qualitative filing data.
2. **Bug 2: Insider activity miscounts** — All transactions counted as "buys" (AAPL: 75/75, MSFT: 99/99). The `net_buys` field equals total transaction count instead of buy/sell delta.
3. **Bug 4: Institutional ownership always 0.0%** — AAPL and MSFT are ~60%+ institutionally held. The yfinance field isn't being read correctly.
4. **Bug 5: Predictability score always 50** — Default value returned regardless of actual revenue volatility. The coefficient of variation computation isn't working.
5. **Bug 1: Peer discovery is a stub** — `_find_peers_from_screener()` never populates `peer_tickers`. Always returns empty list.
6. **Bug 6: Balance sheet includes stale NaN year** — Minor cleanup, wastes tokens.

### Verification

After fixing a bug, verify the output makes sense against reality:
- AAPL institutional ownership should be ~60%
- MSFT institutional ownership should be ~70%
- Insider transactions should have both buys AND sells
- MD&A should be thousands of characters of actual prose
- Predictability scores should differ between volatile and stable companies

### Session Structure

One bug per session. Each session should:
1. Read `docs/bugs.md` for the bug description
2. Investigate root cause using systematic debugging
3. Fix and write/update tests
4. Run `python run_collector.py <TICKER>` to verify
5. Update `docs/bugs.md` to mark the bug as fixed
6. Update this priority list if needed

## Implementation Plan

**Canonical source:** `docs/handoff-implementation-plan.md` (full plan with all tasks and checkboxes)

**Notion copy** (for sharing/reference): https://www.notion.so/3236b14dd0678122a2abe816656259a9

The local file is the source of truth. Notion is a sharing copy.

## Folder Conventions

- All documentation lives in /docs
- All code lives in /src
- All tests live in /tests
- Streamlit entry point is /app.py
- Never let documentation live only in chat — always write it to /docs

## Tech Stack

- Python 3.11+
- `anthropic` SDK (Claude Sonnet — claude-sonnet-4-20250514)
- `streamlit` for UI
- `yfinance` for market data (unofficial scraper — handle failures gracefully)
- `fredapi` for macro data (requires free FRED API key)
- `requests` for SEC EDGAR API
- `beautifulsoup4` for SEC filing HTML parsing
- `plotly` for charts
- `pandas` for data manipulation
- `python-dotenv` for environment variables
- `pytest` for testing

## Hard Rules

1. Never install a new dependency without asking me first
2. All documentation lives in /docs — never keep notes only in chat
3. Never mock in integration tests — integration tests hit real APIs
4. Always update CLAUDE.md "Current Stage" before ending a session
5. Include a disclaimer in any investment-related output: "This is AI-generated analysis for educational purposes only. Not financial advice."
6. SEC EDGAR requests must include a User-Agent header and respect rate limits (0.1s between requests)
7. Every data source function must return gracefully on failure — never crash the pipeline

## Data Sources (all free)

- **SEC EDGAR** — 10-K, 10-Q filings, insider transactions (Form 4)
- **Yahoo Finance** (`yfinance`) — prices, ratios, institutional holdings
- **FRED** — Fed funds rate, GDP, unemployment, CPI, yield curve
