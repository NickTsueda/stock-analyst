"""AI Stock Analyst — Streamlit entry point.

3-tab layout: Investment Thesis | Financial Analysis | Raw Data
Pipeline: Orchestrator → Data Collector → Financial Analyst → Thesis Builder
"""
from __future__ import annotations

from datetime import datetime, timezone

import anthropic
import streamlit as st

from src.agents.orchestrator import OrchestratorAgent
from src.config import settings
from src.ui.components import (
    render_confidence_score,
    render_disclaimer_footer,
    render_executive_summary,
    render_financial_analysis,
    render_hero,
    render_insider_institutional,
    render_macro_context,
    render_raw_data,
    render_risks_catalysts,
    render_thesis_cases,
)

# --- Page config ---

st.set_page_config(
    page_title="AI Stock Analyst",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --- Persistent disclaimer footer ---

render_disclaimer_footer()

# --- Header ---

st.markdown(
    '<h1 style="margin-bottom:0;">AI Stock Analyst</h1>',
    unsafe_allow_html=True,
)
st.caption(
    "Multi-agent investment analysis powered by Claude · "
    "Enter a ticker to generate a complete investment thesis"
)

# --- Input ---

col_input, col_btn = st.columns([3, 1])
with col_input:
    ticker = st.text_input(
        "Ticker Symbol",
        placeholder="e.g. AAPL, MSFT, TSLA",
        label_visibility="collapsed",
    )
with col_btn:
    analyze = st.button("Analyze", type="primary", use_container_width=True)


# --- Pipeline execution ---


def _run_pipeline(ticker: str) -> None:
    """Run the Orchestrator pipeline with streaming progress."""
    # Validate API key
    if not settings.ANTHROPIC_API_KEY:
        st.error(
            "**Missing API key.** Set `ANTHROPIC_API_KEY` in your `.env` file. "
            "See `.env.example` for details."
        )
        return

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    orchestrator = OrchestratorAgent(client)

    # Progress container
    status_container = st.status(f"Analyzing {ticker.upper()}...", expanded=True)
    stages_log: list[str] = []

    def progress_callback(stage: str, status: str) -> None:
        icon = {"in_progress": "⏳", "complete": "✅", "failed": "❌"}.get(status, "")
        stages_log.append(f"{icon} {stage}")
        status_container.markdown("\n\n".join(stages_log))

    start_time = datetime.now(timezone.utc)

    try:
        data, analysis, thesis = orchestrator.run(
            ticker, progress_callback=progress_callback
        )
    except Exception as e:
        status_container.update(label="Analysis failed", state="error", expanded=True)
        st.error(f"Pipeline error: {e}")
        return

    elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()

    # Update status container
    if thesis is not None:
        status_container.update(
            label=f"Analysis complete ({elapsed:.0f}s)", state="complete", expanded=False
        )
    elif analysis is not None:
        status_container.update(
            label="Partial results (thesis generation failed)", state="error", expanded=False
        )
    else:
        status_container.update(
            label="Insufficient data for analysis", state="error", expanded=True
        )

    # Persist in session state
    st.session_state["data"] = data
    st.session_state["analysis"] = analysis
    st.session_state["thesis"] = thesis
    st.session_state["timestamp"] = start_time.strftime("%Y-%m-%d %H:%M UTC")
    st.session_state["elapsed"] = elapsed


# Trigger pipeline
if analyze and ticker.strip():
    _run_pipeline(ticker.strip())
elif analyze:
    st.warning("Please enter a ticker symbol.")


# --- Results display ---

data = st.session_state.get("data")
analysis = st.session_state.get("analysis")
thesis = st.session_state.get("thesis")

if data is not None:
    # Hero section (above tabs)
    if thesis is not None:
        st.divider()
        render_hero(data, thesis)

        if thesis.confidence:
            render_confidence_score(thesis.confidence)

    # 3-tab layout
    tab_thesis, tab_analysis, tab_raw = st.tabs(
        ["Investment Thesis", "Financial Analysis", "Raw Data"]
    )

    with tab_thesis:
        if thesis is not None:
            # Disclaimer banner — Thesis tab only
            st.warning(
                "AI-generated analysis for educational purposes only. Not financial "
                "advice. Always consult a qualified financial advisor before making "
                "investment decisions."
            )

            render_executive_summary(thesis)

            st.subheader("Investment Cases")
            render_thesis_cases(thesis)

            st.subheader("Risks & Catalysts")
            render_risks_catalysts(thesis)

            render_insider_institutional(thesis, data)
            render_macro_context(thesis, data)

            # Footer metadata
            st.divider()
            timestamp = st.session_state.get("timestamp", "")
            elapsed = st.session_state.get("elapsed", 0)
            st.caption(
                f"Generated at {timestamp} · Analysis took {elapsed:.0f}s · "
                f"This is AI-generated analysis for educational purposes only. "
                f"Not financial advice."
            )
        else:
            st.info(
                "Analysis could not be completed. Check the Raw Data tab for details "
                "on which data sources succeeded or failed."
            )

    with tab_analysis:
        if analysis is not None:
            render_financial_analysis(analysis, data)
        else:
            st.info("Financial analysis not available. Insufficient data to proceed.")

    with tab_raw:
        render_raw_data(data)
