# AI Stock Analyst — CLAUDE.md

## What We're Building

A multi-agent AI stock analysis tool that takes a ticker symbol and produces a complete investment thesis with buy/sell/hold recommendation. Inspired by the UChicago paper (May 2024) where GPT-4 predicted earnings with 60.4% accuracy vs 52.7% for human analysts using chain-of-thought prompting on financial statements.

**Target user:** Self-directed retail investors managing $25K-$500K portfolios who want institutional-quality analysis without Bloomberg/FactSet costs.

**Key differentiator:** Every analysis includes a Confidence Score (0-100) with a transparent breakdown of what drives the score up or down (data completeness, financial consistency, insider alignment, macro conditions, company predictability). Users see exactly why the system is confident or uncertain, enabling better judgment.

**Architecture:** 4-agent pipeline (Orchestrator → Data Collector → Financial Analyst → Thesis Builder) using Python, Claude Sonnet, and Streamlit. No LangChain/CrewAI — plain Python classes with typed data contracts.

**Purpose:** Portfolio piece demonstrating PM product thinking + multi-agent AI system design.

## Current Stage

Options:
- Requirements (working on PRD)
- Design (working on architecture)
- Implementation Planning (writing the build plan)
- Build — Phase 1 (Foundation + Data Sources)
- Build — Phase 2 (Agent Layer)
- Build — Phase 3 (Streamlit UI + Polish)
- QA (reviewing and fixing)
- Complete

Current: **Design (working on architecture)**

## Session Start Ritual

Before doing anything in this session, read the following documents in order:

1. /docs/prd.md
2. /docs/handoff-requirements.md
3. /docs/handoff-design.md
4. /docs/handoff-implementation-plan.md
5. /docs/handoff-build.md

After reading, summarize:
- What has been built so far
- What decisions were made and why
- What this session needs to accomplish

Do not begin any work until I confirm your summary is accurate.

Note: Skip any file that is empty or does not yet exist.

## Implementation Plan

**Canonical source:** `docs/handoff-implementation-plan.md` (copied from the plan file during Session 2)

**Notion copy** (for sharing/reference): https://www.notion.so/3236b14dd0678122a2abe816656259a9

If there's a conflict, the local `/docs/` file is the source of truth.

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
- `plotly` for charts
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
