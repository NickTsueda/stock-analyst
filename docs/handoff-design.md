# Handoff: Design Phase

**Date:** 2026-03-14
**Status:** Complete
**Next phase:** Build — Phase 1 (Foundation + Data Sources)

---

## What Was Done

Separated the combined PRD/design spec into two standalone documents:
- `docs/prd.md` — product requirements (user journey, success criteria, V2 scope)
- `docs/design.md` — architecture and technical design (agents, data models, confidence algorithm, data sources, UI)

Removed the `docs/superpowers/specs/` directory (brainstorming artifacts moved to canonical locations).

## Key Architecture Decisions

### Agent Pipeline
- **4 agents:** Orchestrator → Data Collector → Financial Analyst → Thesis Builder
- **Data Collector does NOT call Claude** — pure data fetching. Only Financial Analyst and Thesis Builder make LLM calls.
- **Revision loop** between Thesis Builder → Financial Analyst (max 1 iteration, 30s timeout). Thesis Builder self-critiques, sends targeted questions back if it finds substantive gaps.

### Confidence Score — 6-Factor Weighted Model
- **6 factors with percentage weights:** Data Completeness (20%), Earnings Quality (25%), Valuation Clarity (20%), Company Predictability (20%), Insider Signal (10%), Macro Conditions (5%).
- **Mixed computation:** 3 factors are programmatic (Data Completeness, Company Predictability, Insider Signal), 3 are LLM-assessed with calibrated rubric anchors (Earnings Quality, Valuation Clarity, Macro Conditions).
- **Final score** = weighted average, computed in Python post-processing.
- **Claude's role:** generates qualitative `detail` strings and a `summary`, plus the LLM-assessed sub-scores using rubric anchors.
- **Guardrails:** Data Completeness < 30 caps overall at 40.

### Data Sources — Hybrid Approach
- **SEC EDGAR:** XBRL API for reliable structured financial numbers + BeautifulSoup for best-effort qualitative text (MD&A, risk factors). Analysis always works even if text extraction fails.
- **yfinance:** Essential (40pts). If fully down, analysis degrades gracefully — SEC EDGAR data alone is sufficient, but Data Completeness score drops significantly and a LimitationNote warns the user.
- **FRED:** Nice-to-have (25pts). Failure just penalizes macro score.
- **No caching in V1.** Every analysis hits APIs from scratch. Caching is a V2 consideration.

### Data Quality Gate (Orchestrator)
- `score < 20`: abort, show error
- `20 ≤ score < 50`: proceed with limitation warning
- `score ≥ 50`: proceed normally
- **Deterministic Python rule, no Claude call** — faster, cheaper, more predictable for demos.

### Prompt Strategy
- Zero-shot with calibrated 5-tier rubric anchors (not few-shot)
- Chain-of-thought for Financial Analyst (enhanced UChicago methodology)
- Prompt caching (`cache_control`) on system prompts
- Target <8K tokens of data context per Claude call

### UI
- 3-tab Streamlit layout: Investment Thesis | Financial Analysis | Raw Data
- Dark theme, green accent (#4CAF50)
- Disclaimer in 2 locations (V1): persistent footer, warning banner on Thesis tab

## What Build Phase 1 Should Do

Per the implementation plan (Notion: https://www.notion.so/3236b14dd0678122a2abe816656259a9):

1. **Task 1: Project scaffolding** — pyproject.toml, .gitignore, .env.example, config.py, all __init__.py files
2. **Task 2: Data models** — all dataclasses in src/models.py (including RevisionRequest, RevisedAnalysis, LimitationNote), serialization, shared test fixtures
3. **Task 3: Yahoo Finance** — src/data_sources/yahoo_finance.py with integration test
4. **Task 4: SEC EDGAR** — src/data_sources/sec_edgar.py (XBRL + HTML extraction)
5. **Task 5: FRED** — src/data_sources/fred.py

**Exit criteria:** All data source tests pass. `DataPackage` assembles with real AAPL data.
