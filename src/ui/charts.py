"""Plotly chart builders for financial visualization.

Each function is a pure data → Figure transform with no Streamlit dependency.
All charts use dark-theme-friendly colors consistent with the app's #4CAF50 accent.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

# --- Theme constants ---

_BG_COLOR = "rgba(0,0,0,0)"  # transparent — inherits Streamlit dark bg
_GRID_COLOR = "rgba(255,255,255,0.1)"
_TEXT_COLOR = "#FAFAFA"
_GREEN = "#4CAF50"
_RED = "#EF5350"
_YELLOW = "#FFC107"
_BLUE = "#42A5F5"
_PURPLE = "#AB47BC"
_ORANGE = "#FF7043"

_LAYOUT_DEFAULTS = dict(
    paper_bgcolor=_BG_COLOR,
    plot_bgcolor=_BG_COLOR,
    font=dict(color=_TEXT_COLOR, size=12),
    margin=dict(l=50, r=20, t=40, b=40),
    legend=dict(bgcolor=_BG_COLOR, borderwidth=0),
    xaxis=dict(gridcolor=_GRID_COLOR, showgrid=True),
    yaxis=dict(gridcolor=_GRID_COLOR, showgrid=True),
)


def _apply_layout(fig: go.Figure, **overrides) -> go.Figure:
    """Apply consistent dark-theme layout to a figure."""
    layout = {**_LAYOUT_DEFAULTS, **overrides}
    fig.update_layout(**layout)
    return fig


# --- Chart functions ---


def price_chart(price_history: list[dict] | None) -> go.Figure | None:
    """1Y daily close with 50-day and 200-day moving averages.

    Args:
        price_history: list of dicts with 'date' and 'close' keys.

    Returns:
        Plotly Figure or None if insufficient data.
    """
    if not price_history or len(price_history) < 2:
        return None

    df = pd.DataFrame(price_history)
    if "date" not in df.columns or "close" not in df.columns:
        return None

    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")

    fig = go.Figure()

    # Price line
    fig.add_trace(go.Scatter(
        x=df["date"], y=df["close"],
        name="Price",
        line=dict(color=_GREEN, width=2),
    ))

    # 50-day MA (only if enough data)
    if len(df) >= 50:
        df["ma50"] = df["close"].rolling(window=50).mean()
        fig.add_trace(go.Scatter(
            x=df["date"], y=df["ma50"],
            name="50-Day MA",
            line=dict(color=_BLUE, width=1.5, dash="dash"),
        ))

    # 200-day MA (only if enough data)
    if len(df) >= 200:
        df["ma200"] = df["close"].rolling(window=200).mean()
        fig.add_trace(go.Scatter(
            x=df["date"], y=df["ma200"],
            name="200-Day MA",
            line=dict(color=_ORANGE, width=1.5, dash="dot"),
        ))

    return _apply_layout(
        fig,
        title="Price History (1Y)",
        yaxis_title="Price ($)",
        hovermode="x unified",
    )


def revenue_profit_chart(financials: dict | None) -> go.Figure | None:
    """Grouped bar chart: revenue, gross profit, net income by year.

    Args:
        financials: FinancialStatements as dict (income_statement with line items).

    Returns:
        Plotly Figure or None if no data.
    """
    if not financials:
        return None

    income = financials.get("income_statement", {})
    if not income:
        return None

    # Extract metrics — try common yfinance/XBRL labels
    revenue = _find_line_item(income, ["Total Revenue", "Revenue", "Revenues"])
    gross_profit = _find_line_item(income, ["Gross Profit"])
    net_income = _find_line_item(income, ["Net Income", "Net Income Common Stockholders"])

    if not revenue:
        return None

    # Sort years chronologically
    years = sorted(revenue.keys())

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=years,
        y=[revenue.get(y, 0) / 1e9 for y in years],
        name="Revenue",
        marker_color=_GREEN,
    ))

    if gross_profit:
        fig.add_trace(go.Bar(
            x=years,
            y=[gross_profit.get(y, 0) / 1e9 for y in years],
            name="Gross Profit",
            marker_color=_BLUE,
        ))

    if net_income:
        fig.add_trace(go.Bar(
            x=years,
            y=[net_income.get(y, 0) / 1e9 for y in years],
            name="Net Income",
            marker_color=_PURPLE,
        ))

    return _apply_layout(
        fig,
        title="Revenue & Profitability",
        yaxis_title="$ Billions",
        barmode="group",
        hovermode="x unified",
    )


def margin_trends_chart(financials: dict | None) -> go.Figure | None:
    """Multi-line chart: gross, operating, and net margin % over time.

    Computes margins from income statement line items if available.

    Args:
        financials: FinancialStatements as dict.

    Returns:
        Plotly Figure or None if insufficient data.
    """
    if not financials:
        return None

    income = financials.get("income_statement", {})
    if not income:
        return None

    revenue = _find_line_item(income, ["Total Revenue", "Revenue", "Revenues"])
    gross_profit = _find_line_item(income, ["Gross Profit"])
    operating_income = _find_line_item(income, [
        "Operating Income", "EBIT", "Operating Income Loss",
    ])
    net_income = _find_line_item(income, ["Net Income", "Net Income Common Stockholders"])

    if not revenue:
        return None

    years = sorted(revenue.keys())
    fig = go.Figure()
    has_data = False

    # Gross margin
    if gross_profit:
        margins = [_safe_pct(gross_profit.get(y), revenue.get(y)) for y in years]
        if any(m is not None for m in margins):
            fig.add_trace(go.Scatter(
                x=years, y=margins,
                name="Gross Margin",
                line=dict(color=_GREEN, width=2),
                mode="lines+markers",
            ))
            has_data = True

    # Operating margin
    if operating_income:
        margins = [_safe_pct(operating_income.get(y), revenue.get(y)) for y in years]
        if any(m is not None for m in margins):
            fig.add_trace(go.Scatter(
                x=years, y=margins,
                name="Operating Margin",
                line=dict(color=_BLUE, width=2),
                mode="lines+markers",
            ))
            has_data = True

    # Net margin
    if net_income:
        margins = [_safe_pct(net_income.get(y), revenue.get(y)) for y in years]
        if any(m is not None for m in margins):
            fig.add_trace(go.Scatter(
                x=years, y=margins,
                name="Net Margin",
                line=dict(color=_PURPLE, width=2),
                mode="lines+markers",
            ))
            has_data = True

    if not has_data:
        return None

    return _apply_layout(
        fig,
        title="Margin Trends",
        yaxis_title="Margin (%)",
        hovermode="x unified",
    )


def confidence_gauge(score: int, level: str) -> go.Figure:
    """Semicircular confidence gauge with color zones.

    Args:
        score: 0-100 confidence score.
        level: "HIGH", "MEDIUM", or "LOW".

    Returns:
        Plotly Figure with gauge indicator.
    """
    if level == "HIGH":
        bar_color = _GREEN
    elif level == "MEDIUM":
        bar_color = _YELLOW
    else:
        bar_color = _RED

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        number=dict(font=dict(size=48, color=_TEXT_COLOR)),
        gauge=dict(
            axis=dict(range=[0, 100], tickwidth=1, tickcolor=_TEXT_COLOR,
                      tickfont=dict(color=_TEXT_COLOR)),
            bar=dict(color=bar_color),
            bgcolor="rgba(255,255,255,0.05)",
            borderwidth=0,
            steps=[
                dict(range=[0, 39], color="rgba(239,83,80,0.15)"),
                dict(range=[40, 69], color="rgba(255,193,7,0.15)"),
                dict(range=[70, 100], color="rgba(76,175,80,0.15)"),
            ],
        ),
    ))

    return _apply_layout(
        fig,
        height=250,
        margin=dict(l=30, r=30, t=30, b=10),
    )


# --- Helpers ---


def _find_line_item(statement: dict, candidates: list[str]) -> dict | None:
    """Find the first matching line item from a list of candidate names."""
    for name in candidates:
        if name in statement:
            return statement[name]
    return None


def _safe_pct(numerator: float | None, denominator: float | None) -> float | None:
    """Compute percentage, returning None if either value is missing or zero."""
    if numerator is None or denominator is None or denominator == 0:
        return None
    return round((numerator / denominator) * 100, 1)
