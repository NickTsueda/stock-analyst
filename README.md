# AI Stock Analyst

A multi-agent AI system that takes a ticker symbol and produces a complete investment thesis with buy/sell/hold recommendation and transparent confidence scoring — powered by Claude and built with plain Python.

Inspired by the [UChicago paper (May 2024)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4835311) where GPT-4 predicted earnings direction with 60.4% accuracy vs 52.7% for human analysts using chain-of-thought prompting on financial statements.

> **Status:** V1 complete. All agents, UI, and data sources implemented. 203 tests passing.

## Why This Exists

Retail investors managing $25K–$500K portfolios want institutional-quality analysis but can't justify $20K+/yr for Bloomberg or FactSet. Free sources (Seeking Alpha, Reddit, finviz) are fragmented — no single tool synthesizes SEC filings, financials, and macro signals into an explainable investment thesis comparable to a sell-side research report.

AI Stock Analyst fills that gap. Enter a ticker, get a structured analysis in under 2 minutes.

## How It Works

Four agents run in sequence, each with a clear responsibility:

```
Orchestrator → Data Collector → Financial Analyst → Thesis Builder
                                       ↑                    │
                                       └── Revision Loop ───┘
```

| Agent | Role | Uses Claude? |
|---|---|---|
| **Orchestrator** | Validates ticker, dispatches agents, computes final confidence score | No |
| **Data Collector** | Fetches data from SEC EDGAR, Yahoo Finance, FRED | No |
| **Financial Analyst** | Chain-of-thought analysis of financials, trends, and risks | Yes |
| **Thesis Builder** | Synthesizes into investment thesis, self-critiques, triggers revision if needed | Yes |

**No LangChain. No CrewAI.** Plain Python classes with typed data contracts. The `anthropic` SDK is the only AI dependency.

### Revision Loop

After generating an initial thesis, the Thesis Builder self-critiques: *"What are my weakest assumptions? What contradictions did I gloss over?"* If it finds substantive gaps, it sends targeted questions back to the Financial Analyst for re-examination — mimicking how a senior analyst reviews a junior's first draft.

## Confidence Score

Every analysis includes a 0–100 Confidence Score with a transparent breakdown of 6 weighted factors:

| Factor | Weight | How It's Computed |
|---|---|---|
| Data Completeness | 20% | Programmatic — which data sources returned successfully |
| Earnings Quality | 25% | LLM-assessed — coherence and explainability of financial picture |
| Valuation Clarity | 20% | LLM-assessed — how clearly over/undervaluation can be assessed |
| Company Predictability | 20% | Programmatic — historical revenue volatility (coefficient of variation) |
| Insider Signal | 10% | Hybrid — insider buying/selling vs analyst directional lean |
| Macro Conditions | 5% | LLM-assessed — clarity of macro environment for this sector |

Users see exactly *why* the system is confident or uncertain.

## Data Sources (All Free)

- **SEC EDGAR** — 10-K/10-Q filings (XBRL financial data + MD&A text), Form 4 insider transactions
- **Yahoo Finance** (`yfinance`) — prices, ratios, institutional holdings, peer comparisons
- **FRED** — Fed funds rate, GDP, unemployment, CPI, yield curve

Every data source fails gracefully. If one goes down, the pipeline continues with what's available and the Confidence Score reflects the gap.

## Tech Stack

- Python 3.11+
- `anthropic` SDK (Claude Sonnet)
- `streamlit` for UI
- `yfinance`, `fredapi`, `requests`, `beautifulsoup4`
- `plotly` for charts
- `pandas` for data manipulation
- `pytest` for testing

## Getting Started

### Prerequisites

- Python 3.11+
- [Anthropic API key](https://console.anthropic.com/)
- [FRED API key](https://fred.stlouisfed.org/docs/api/api_key.html) (free)

### Setup

```bash
git clone https://github.com/NickTsueda/stock-analyst.git
cd stock-analyst
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Create a `.env` file:

```
ANTHROPIC_API_KEY=your-key-here
FRED_API_KEY=your-key-here
```

### Run

```bash
streamlit run app.py
```

### Test the Data Pipeline

You can run the Data Collector agent standalone to see the raw financial data it assembles:

```bash
python run_collector.py AAPL
```

This fetches data from all three sources (Yahoo Finance, SEC EDGAR, FRED) and outputs the structured markdown that gets passed to Claude for analysis. No Anthropic API key needed — the Data Collector doesn't use Claude.

## What You Get

Enter a ticker (e.g., AAPL) and the app produces:

- **Investment Thesis tab** — Recommendation badge (BUY/HOLD/SELL), confidence gauge (0–100) with expandable breakdown, executive summary, bull/base/bear cases with probabilities, risks & catalysts, insider/institutional signals, macro context
- **Financial Analysis tab** — 1Y price chart with 50/200-day moving averages, revenue & margin trend charts, ratio table (P/E, P/S, D/E, ROE, etc.), chain-of-thought agent reasoning
- **Raw Data tab** — Data completeness indicator, per-source status, expandable raw data sections, warnings log

Analysis completes in 45–90 seconds. ETFs and mutual funds are detected with a warning that the tool is designed for individual stocks.

## Cost Per Analysis

| Component | Est. Cost |
|---|---|
| Financial Analyst (~25K input, ~3K output) | ~$0.08 |
| Thesis Builder (~35K input, ~4K output) | ~$0.12 |
| Revision loop (if triggered) | ~$0.03 |
| Data Collector + Orchestrator (no Claude) | $0.00 |
| **Total per analysis** | **~$0.15–0.20** |

## Project Structure

```
stock-analyst/
├── app.py                          # Streamlit entry point
├── pyproject.toml                  # Dependencies and project config
├── .env.example                    # API key placeholders
├── src/
│   ├── models.py                   # 17 dataclasses + 3 enums (typed data contracts)
│   ├── config.py                   # Settings, API keys, constants
│   ├── agents/
│   │   ├── base.py                 # Base agent (Claude calling, JSON parsing, retry)
│   │   ├── orchestrator.py         # Pipeline coordinator + confidence scoring
│   │   ├── data_collector.py       # Data fetching from all sources (no Claude)
│   │   ├── financial_analyst.py    # Chain-of-thought financial analysis
│   │   └── thesis_builder.py       # Investment thesis synthesis + self-critique
│   ├── data_sources/
│   │   ├── sec_edgar.py            # SEC EDGAR API (XBRL, filings, Form 4)
│   │   ├── yahoo_finance.py        # yfinance wrapper
│   │   └── fred.py                 # FRED macro indicators
│   └── ui/
│       ├── components.py           # Streamlit rendering functions
│       └── charts.py               # Plotly chart builders
├── tests/                          # 203 tests (unit + integration)
└── docs/                           # PRD, architecture docs
```

## Design Documentation

The `/docs` directory contains the full product and technical design:

- **[PRD](docs/prd.md)** — Product requirements, user journey, success criteria
- **[Design](docs/design.md)** — Architecture, data contracts, confidence algorithm, UI spec

## Scope

**V1 covers:**
- US public equities (NYSE, NASDAQ, AMEX)
- Single-ticker analysis
- Real-time data fetching (no caching)
- ~$0.15–0.20 per analysis with Claude Sonnet

**Not in V1:** portfolio management, historical comparisons, caching, user accounts, non-US equities.

## Disclaimer

This is AI-generated analysis for educational purposes only. Not financial advice.

## License

MIT
