"""Smoke tests for Plotly chart builders."""
import plotly.graph_objects as go

from src.ui.charts import (
    price_chart,
    revenue_profit_chart,
    margin_trends_chart,
    confidence_gauge,
)


# --- price_chart ---


def test_price_chart_returns_figure():
    import pandas as pd
    dates = pd.bdate_range("2024-01-02", periods=60)
    history = [{"date": d.strftime("%Y-%m-%d"), "close": 180 + i * 0.5} for i, d in enumerate(dates)]
    fig = price_chart(history)
    assert isinstance(fig, go.Figure)
    # Should have price + 50-day MA (not enough for 200-day)
    assert len(fig.data) == 2


def test_price_chart_with_200_day_ma():
    import pandas as pd
    dates = pd.bdate_range("2023-03-01", periods=250)
    history = [{"date": d.strftime("%Y-%m-%d"), "close": 180 + i * 0.1} for i, d in enumerate(dates)]
    fig = price_chart(history)
    assert isinstance(fig, go.Figure)
    # Should have price + 50-day MA + 200-day MA
    assert len(fig.data) == 3


def test_price_chart_empty_returns_none():
    assert price_chart(None) is None
    assert price_chart([]) is None
    assert price_chart([{"date": "2024-01-01", "close": 100}]) is None


def test_price_chart_missing_columns_returns_none():
    assert price_chart([{"foo": 1}, {"foo": 2}]) is None


# --- revenue_profit_chart ---


def test_revenue_profit_chart_returns_figure():
    financials = {
        "income_statement": {
            "Total Revenue": {"2024": 383e9, "2023": 383e9},
            "Gross Profit": {"2024": 170e9, "2023": 166e9},
            "Net Income": {"2024": 93e9, "2023": 96e9},
        }
    }
    fig = revenue_profit_chart(financials)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 3  # revenue + gross profit + net income


def test_revenue_profit_chart_revenue_only():
    financials = {"income_statement": {"Revenue": {"2024": 100e9, "2023": 90e9}}}
    fig = revenue_profit_chart(financials)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) == 1  # just revenue


def test_revenue_profit_chart_empty_returns_none():
    assert revenue_profit_chart(None) is None
    assert revenue_profit_chart({}) is None
    assert revenue_profit_chart({"income_statement": {}}) is None


# --- margin_trends_chart ---


def test_margin_trends_chart_returns_figure():
    financials = {
        "income_statement": {
            "Total Revenue": {"2024": 383e9, "2023": 383e9},
            "Gross Profit": {"2024": 170e9, "2023": 166e9},
            "Net Income": {"2024": 93e9, "2023": 96e9},
        }
    }
    fig = margin_trends_chart(financials)
    assert isinstance(fig, go.Figure)
    assert len(fig.data) >= 2  # gross margin + net margin at minimum


def test_margin_trends_chart_no_revenue_returns_none():
    financials = {"income_statement": {"Gross Profit": {"2024": 170e9}}}
    assert margin_trends_chart(financials) is None


def test_margin_trends_chart_empty_returns_none():
    assert margin_trends_chart(None) is None
    assert margin_trends_chart({}) is None


def test_margin_trends_chart_ignores_operating_expense():
    """Operating Expense is a cost, not income — must not be used for operating margin."""
    financials = {
        "income_statement": {
            "Total Revenue": {"2024": 383e9, "2023": 383e9},
            "Operating Expense": {"2024": 270e9, "2023": 265e9},
            "Net Income": {"2024": 93e9, "2023": 96e9},
        }
    }
    fig = margin_trends_chart(financials)
    assert isinstance(fig, go.Figure)
    # Should have net margin only — no operating margin trace since
    # Operating Expense should NOT be matched as operating income
    trace_names = [t.name for t in fig.data]
    assert "Operating Margin" not in trace_names


# --- confidence_gauge ---


def test_confidence_gauge_high():
    fig = confidence_gauge(75, "HIGH")
    assert isinstance(fig, go.Figure)
    assert fig.data[0].value == 75


def test_confidence_gauge_medium():
    fig = confidence_gauge(55, "MEDIUM")
    assert isinstance(fig, go.Figure)


def test_confidence_gauge_low():
    fig = confidence_gauge(25, "LOW")
    assert isinstance(fig, go.Figure)
