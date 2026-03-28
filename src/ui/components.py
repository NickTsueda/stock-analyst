"""Streamlit UI components for rendering analysis results.

Each function takes typed model objects and renders them using Streamlit.
All components handle None/empty data gracefully (partial pipeline results).
"""
from __future__ import annotations

import streamlit as st

from src.models import (
    ConfidenceScore,
    DataPackage,
    FinancialAnalysis,
    InvestmentThesis,
    Recommendation,
)
from src.ui.charts import (
    confidence_gauge,
    margin_trends_chart,
    price_chart,
    revenue_profit_chart,
)

# --- Helpers ---


def _escape_dollars(text: str) -> str:
    """Escape bare ``$`` so Streamlit doesn't treat them as LaTeX delimiters.

    ``st.markdown`` renders ``$…$`` as inline math.  Financial text is full of
    dollar signs (``$2.6B``), which triggers false LaTeX blocks that strip
    whitespace and garble the output.  Replacing ``$`` → ``\\$`` keeps them
    literal.
    """
    return text.replace("$", r"\$")


# --- Color constants ---

_GREEN = "#4CAF50"
_RED = "#EF5350"
_YELLOW = "#FFC107"
_MUTED = "#9E9E9E"
_CARD_BG = "#262730"


# --- Recommendation badge ---

_REC_COLORS = {
    Recommendation.BUY: (_GREEN, "#1B5E20"),
    Recommendation.HOLD: (_YELLOW, "#F57F17"),
    Recommendation.SELL: (_RED, "#B71C1C"),
}


def render_hero(data: DataPackage, thesis: InvestmentThesis) -> None:
    """Hero section: company name, ticker, price, and recommendation badge."""
    rec_fg, rec_bg = _REC_COLORS.get(thesis.recommendation, (_YELLOW, "#F57F17"))

    price_str = ""
    if data.market_data and data.market_data.current_price:
        price_str = f"${data.market_data.current_price:,.2f}"

    badge_html = (
        f'<span style="background:{rec_bg}; color:{rec_fg}; '
        f'padding:6px 18px; border-radius:20px; font-weight:700; '
        f'font-size:1.1rem; letter-spacing:1px;">'
        f'{thesis.recommendation.value}</span>'
    )

    st.markdown(
        f'<div style="display:flex; align-items:center; gap:16px; flex-wrap:wrap;">'
        f'<span style="font-size:2rem; font-weight:700;">{data.company_name}</span>'
        f'<span style="font-size:1.2rem; color:{_MUTED}; font-family:monospace;">'
        f'{data.ticker}</span>'
        f'<span style="font-size:1.8rem; font-weight:600;">{price_str}</span>'
        f'{badge_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


# --- Confidence score ---


def render_confidence_score(confidence: ConfidenceScore) -> None:
    """Confidence gauge with summary and expandable driver breakdown."""
    col1, col2 = st.columns([1, 2])

    with col1:
        fig = confidence_gauge(confidence.score, confidence.level.value)
        st.plotly_chart(fig, use_container_width=True, key="confidence_gauge")

    with col2:
        level_colors = {"HIGH": _GREEN, "MEDIUM": _YELLOW, "LOW": _RED}
        color = level_colors.get(confidence.level.value, _MUTED)
        st.markdown(
            f'<p style="font-size:1.1rem; margin-top:1rem;">'
            f'<span style="color:{color}; font-weight:700;">'
            f'{confidence.level.value} CONFIDENCE</span></p>',
            unsafe_allow_html=True,
        )
        if confidence.summary:
            st.markdown(_escape_dollars(confidence.summary))

    # Expandable driver breakdown
    with st.expander("Score Driver Breakdown", expanded=False):
        for driver in confidence.drivers:
            impact_icon = {"positive": "+", "negative": "-", "neutral": "~"}
            icon = impact_icon.get(driver.impact, "~")
            impact_color = {"positive": _GREEN, "negative": _RED, "neutral": _MUTED}
            color = impact_color.get(driver.impact, _MUTED)

            st.markdown(
                f'<div style="display:flex; justify-content:space-between; '
                f'padding:6px 0; border-bottom:1px solid rgba(255,255,255,0.05);">'
                f'<span>{driver.factor}</span>'
                f'<span style="color:{color}; font-weight:600;">'
                f'[{icon}] {driver.score}/100 '
                f'<span style="color:{_MUTED}; font-weight:400;">'
                f'(w={driver.weight:.0%})</span></span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            if driver.detail:
                st.caption(driver.detail)


# --- Thesis tab sections ---


def render_executive_summary(thesis: InvestmentThesis) -> None:
    """Executive summary prose."""
    if thesis.executive_summary:
        st.markdown(_escape_dollars(thesis.executive_summary))


def render_thesis_cases(thesis: InvestmentThesis) -> None:
    """3-column bull/base/bear card layout with probabilities."""
    cases = [
        ("Bull Case", thesis.bull_case, _GREEN),
        ("Base Case", thesis.base_case, _YELLOW),
        ("Bear Case", thesis.bear_case, _RED),
    ]

    cols = st.columns(3)
    for col, (label, case, color) in zip(cols, cases):
        with col:
            if case is None:
                st.markdown(f"**{label}**")
                st.caption("Not available")
                continue

            prob_pct = f"{case.probability * 100:.0f}%" if case.probability else "—"
            st.markdown(
                f'<div style="border-left:3px solid {color}; padding:0 12px;">'
                f'<p style="font-weight:700; margin-bottom:4px;">{label} '
                f'<span style="color:{color};">({prob_pct})</span></p>'
                f'</div>',
                unsafe_allow_html=True,
            )
            st.markdown(_escape_dollars(case.narrative))
            if case.drivers:
                for driver in case.drivers:
                    st.markdown(f"- {_escape_dollars(driver)}")


def render_risks_catalysts(thesis: InvestmentThesis) -> None:
    """2-column risks and catalysts layout."""
    col_r, col_c = st.columns(2)
    with col_r:
        st.markdown(f"**:red[Risks]**")
        if thesis.risks:
            for risk in thesis.risks:
                st.markdown(f"- {_escape_dollars(risk)}")
        else:
            st.caption("No risks identified")
    with col_c:
        st.markdown(f"**:green[Catalysts]**")
        if thesis.catalysts:
            for cat in thesis.catalysts:
                st.markdown(f"- {_escape_dollars(cat)}")
        else:
            st.caption("No catalysts identified")


def render_insider_institutional(
    thesis: InvestmentThesis, data: DataPackage
) -> None:
    """Insider and institutional signals section."""
    st.subheader("Insider & Institutional Signals")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Insider Activity**")
        if thesis.insider_summary:
            st.markdown(_escape_dollars(thesis.insider_summary))
        elif data.insider_activity and data.insider_activity.transactions:
            net = data.insider_activity.net_buys
            total = len(data.insider_activity.transactions)
            direction = "net buying" if net > 0 else ("net selling" if net < 0 else "neutral")
            st.markdown(f"{total} transactions, {direction} (net: {net:+d})")
        else:
            st.caption("Insider data unavailable")

    with col2:
        st.markdown("**Institutional Ownership**")
        if data.institutional and data.institutional.institutional_ownership_pct is not None:
            pct = data.institutional.institutional_ownership_pct
            st.metric("Institutional Ownership", f"{pct:.1f}%")
            if data.institutional.holders:
                with st.expander(f"Top Holders ({len(data.institutional.holders)})"):
                    for h in data.institutional.holders[:5]:
                        name = h.get("name", h.get("holder", "Unknown"))
                        shares = h.get("shares", h.get("position", 0))
                        st.markdown(f"- {name}: {shares:,.0f} shares")
        else:
            st.caption("Institutional data unavailable")


def render_macro_context(thesis: InvestmentThesis, data: DataPackage) -> None:
    """Macro context summary."""
    st.subheader("Macro Context")
    if thesis.macro_context:
        st.markdown(_escape_dollars(thesis.macro_context))
    elif data.macro:
        m = data.macro
        parts = []
        if m.fed_funds_rate is not None:
            parts.append(f"Fed Funds: {m.fed_funds_rate:.2f}%")
        if m.unemployment_rate is not None:
            parts.append(f"Unemployment: {m.unemployment_rate:.1f}%")
        if m.cpi_yoy is not None:
            parts.append(f"CPI YoY: {m.cpi_yoy:.1f}%")
        if m.yield_spread is not None:
            parts.append(f"Yield Spread: {m.yield_spread:.2f}%")
        st.markdown(" | ".join(parts) if parts else "Macro data partially available")
    else:
        st.caption("Macro data unavailable")


# --- Financial Analysis tab ---


def render_financial_analysis(
    analysis: FinancialAnalysis, data: DataPackage
) -> None:
    """Charts, ratio table, and chain-of-thought reasoning."""
    # Price chart
    fig = price_chart(data.price_history)
    if fig:
        st.plotly_chart(fig, use_container_width=True, key="price_chart")

    # Revenue & margin charts side by side
    financials_dict = data.financials.to_dict() if data.financials else None
    col1, col2 = st.columns(2)
    with col1:
        fig = revenue_profit_chart(financials_dict)
        if fig:
            st.plotly_chart(fig, use_container_width=True, key="rev_profit_chart")
        else:
            st.caption("Revenue data unavailable for charting")
    with col2:
        fig = margin_trends_chart(financials_dict)
        if fig:
            st.plotly_chart(fig, use_container_width=True, key="margin_chart")
        else:
            st.caption("Margin data unavailable for charting")

    # Ratio table
    st.subheader("Key Ratios")
    if analysis.ratios:
        rows = []
        for r in analysis.ratios:
            row = {"Ratio": r.name, "Trend": r.trend}
            # Show most recent value and assessment
            if r.values:
                sorted_years = sorted(r.values.keys(), reverse=True)
                if sorted_years:
                    val = r.values[sorted_years[0]]
                    try:
                        row["Current"] = f"{float(val):.2f}"
                    except (ValueError, TypeError):
                        row["Current"] = str(val)
                else:
                    row["Current"] = "—"
            else:
                row["Current"] = "—"
            row["Assessment"] = r.assessment
            rows.append(row)
        st.dataframe(rows, use_container_width=True, hide_index=True)
    else:
        # Fallback: show ratios from market data
        if data.market_data:
            md = data.market_data
            ratio_data = {}
            if md.pe_ratio is not None:
                ratio_data["P/E"] = f"{md.pe_ratio:.1f}"
            if md.ps_ratio is not None:
                ratio_data["P/S"] = f"{md.ps_ratio:.1f}"
            if md.ev_ebitda is not None:
                ratio_data["EV/EBITDA"] = f"{md.ev_ebitda:.1f}"
            if md.pb_ratio is not None:
                ratio_data["P/B"] = f"{md.pb_ratio:.1f}"
            if ratio_data:
                st.dataframe(
                    [{"Ratio": k, "Value": v} for k, v in ratio_data.items()],
                    use_container_width=True,
                    hide_index=True,
                )

    # Strengths & Concerns
    if analysis.strengths or analysis.concerns:
        col_s, col_c = st.columns(2)
        with col_s:
            st.markdown("**Strengths**")
            for s in analysis.strengths:
                st.markdown(f"- :green[{_escape_dollars(s)}]")
        with col_c:
            st.markdown("**Concerns**")
            for c in analysis.concerns:
                st.markdown(f"- :red[{_escape_dollars(c)}]")

    # Chain-of-thought reasoning
    if analysis.chain_of_thought:
        with st.expander("Agent Reasoning (Chain-of-Thought)", expanded=False):
            st.markdown(_escape_dollars(analysis.chain_of_thought))


# --- Raw Data tab ---


def render_raw_data(data: DataPackage) -> None:
    """Expandable sections per data source with completeness indicator."""
    # Data Completeness Indicator
    score = data.data_completeness_score
    score_color = _GREEN if score >= 70 else (_YELLOW if score >= 40 else _RED)
    st.markdown(
        f'<div style="padding:12px; border-radius:8px; background:{_CARD_BG}; '
        f'margin-bottom:1rem;">'
        f'<span style="font-weight:700;">Data Completeness: </span>'
        f'<span style="color:{score_color}; font-weight:700; font-size:1.2rem;">'
        f'{score}/100</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # Source status table
    sources = [
        ("Yahoo Finance", data.market_data is not None, 40),
        ("SEC EDGAR", data.financials is not None or data.filing_text is not None, 35),
        ("FRED", data.macro is not None, 25),
    ]
    for name, ok, pts in sources:
        status = f":green[OK] (+{pts}pts)" if ok else ":red[Failed] (0pts)"
        st.markdown(f"- **{name}:** {status}")

    st.divider()

    # Price Data
    with st.expander("Price Data"):
        if data.price_history:
            st.markdown(f"{len(data.price_history)} daily data points")
            # Show last 5 entries
            recent = data.price_history[-5:]
            st.dataframe(recent, use_container_width=True, hide_index=True)
        else:
            st.caption("No price data")

    # Financials
    with st.expander("Financial Statements"):
        if data.financials:
            if data.financials.income_statement:
                st.markdown("**Income Statement**")
                st.json(data.financials.income_statement)
            if data.financials.balance_sheet:
                st.markdown("**Balance Sheet**")
                st.json(data.financials.balance_sheet)
            if data.financials.cash_flow:
                st.markdown("**Cash Flow**")
                st.json(data.financials.cash_flow)
        else:
            st.caption("No financial statement data")

    # Insider Transactions
    with st.expander("Insider Transactions"):
        if data.insider_activity and data.insider_activity.transactions:
            ia = data.insider_activity
            st.markdown(
                f"Source: **{ia.source}** | Net buys: **{ia.net_buys:+d}** | "
                f"Total: **{len(ia.transactions)}**"
            )
            st.dataframe(
                ia.transactions[:20],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.caption("No insider transaction data")

    # Macro Indicators
    with st.expander("Macro Indicators"):
        if data.macro:
            m = data.macro
            indicators = {
                "Fed Funds Rate": f"{m.fed_funds_rate:.2f}%" if m.fed_funds_rate is not None else "—",
                "GDP Growth": f"{m.gdp_growth:.2f}%" if m.gdp_growth is not None else "—",
                "Unemployment": f"{m.unemployment_rate:.1f}%" if m.unemployment_rate is not None else "—",
                "CPI YoY": f"{m.cpi_yoy:.1f}%" if m.cpi_yoy is not None else "—",
                "Yield Spread (10Y-2Y)": f"{m.yield_spread:.2f}%" if m.yield_spread is not None else "—",
            }
            for k, v in indicators.items():
                st.markdown(f"- **{k}:** {v}")
            if m.as_of_date:
                st.caption(f"As of {m.as_of_date}")
        else:
            st.caption("No macro data (FRED API key may be missing)")

    # Filing Text
    with st.expander("SEC Filing Text"):
        if data.filing_text:
            ft = data.filing_text
            if ft.filing_date or ft.filing_type:
                st.markdown(f"**{ft.filing_type}** filed {ft.filing_date}")
            if ft.mda_text:
                st.markdown("**MD&A** (truncated)")
                st.text(ft.mda_text[:3000])
            if ft.risk_factors_text:
                st.markdown("**Risk Factors** (truncated)")
                st.text(ft.risk_factors_text[:3000])
        else:
            st.caption("No SEC filing text")

    # Warnings / Limitations
    if data.warnings:
        with st.expander("Warnings & Limitations", expanded=True):
            for w in data.warnings:
                if w.severity == "error":
                    st.error(f"**{w.source}:** {w.message}")
                else:
                    st.warning(f"**{w.source}:** {w.message}")


# --- Pipeline status ---


def render_disclaimer_footer() -> None:
    """Persistent footer disclaimer shown on all pages."""
    st.markdown(
        '<div style="position:fixed; bottom:0; left:0; right:0; '
        'background:#0E1117; border-top:1px solid rgba(255,255,255,0.1); '
        'padding:8px 16px; text-align:center; z-index:999; '
        'font-size:0.75rem; color:#9E9E9E;">'
        'This is AI-generated analysis for educational purposes only. '
        'Not financial advice.'
        '</div>',
        unsafe_allow_html=True,
    )
