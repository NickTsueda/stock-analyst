"""FRED data source — Federal Reserve Economic Data for macro indicators.

Fetches: Fed Funds Rate, GDP growth, unemployment, CPI YoY, yield spread (10Y-2Y).
Returns (data, warnings) and never raises.
"""
from __future__ import annotations

import logging
from datetime import datetime

from fredapi import Fred

from src.config import settings

logger = logging.getLogger(__name__)


def get_macro_context() -> tuple[dict, list[str]]:
    """Fetch latest macro indicators from FRED.

    Returns (data_dict, warnings). data_dict keys match MacroContext fields:
    fed_funds_rate, gdp_growth, unemployment_rate, cpi_yoy, yield_spread, as_of_date.
    """
    warnings = []
    result = {}

    try:
        fred = Fred(api_key=settings.FRED_API_KEY)
    except Exception as e:
        logger.warning("FRED client initialization failed: %s", e)
        return {}, [f"FRED unavailable: {e}"]

    # Fed Funds Rate — latest value
    result["fed_funds_rate"] = _get_latest_value(fred, "FEDFUNDS", warnings)

    # GDP — compute quarter-over-quarter annualized growth
    result["gdp_growth"] = _get_growth_rate(fred, "GDPC1", warnings, label="GDP")

    # Unemployment — latest value
    result["unemployment_rate"] = _get_latest_value(fred, "UNRATE", warnings)

    # CPI — compute YoY change
    result["cpi_yoy"] = _get_yoy_change(fred, "CPIAUCSL", warnings, label="CPI")

    # Yield spread (10Y - 2Y) — latest value
    result["yield_spread"] = _get_latest_value(fred, "T10Y2Y", warnings)

    # Determine as-of date from whatever data we got
    result["as_of_date"] = datetime.now().strftime("%Y-%m-%d")

    # If we got nothing at all, report it
    values = [v for k, v in result.items() if k != "as_of_date" and v is not None]
    if not values:
        warnings.append("No FRED data retrieved — all series failed")
        return {}, warnings

    return result, warnings


def _get_latest_value(
    fred: Fred, series_id: str, warnings: list[str]
) -> float | None:
    """Get the most recent value of a FRED series."""
    try:
        series = fred.get_series(series_id)
        if series is None or series.empty:
            warnings.append(f"FRED series {series_id} returned empty data")
            return None
        val = series.iloc[-1]
        return round(float(val), 2) if val == val else None  # NaN check
    except Exception as e:
        warnings.append(f"FRED series {series_id} failed: {e}")
        return None


def _get_growth_rate(
    fred: Fred, series_id: str, warnings: list[str], label: str = ""
) -> float | None:
    """Compute period-over-period growth rate from a FRED series."""
    try:
        series = fred.get_series(series_id)
        if series is None or len(series) < 2:
            warnings.append(f"FRED {label or series_id}: insufficient data for growth calc")
            return None
        current = float(series.iloc[-1])
        previous = float(series.iloc[-2])
        if previous == 0:
            return None
        growth = (current - previous) / previous * 100
        return round(growth, 2)
    except Exception as e:
        warnings.append(f"FRED {label or series_id} growth calc failed: {e}")
        return None


def _get_yoy_change(
    fred: Fred, series_id: str, warnings: list[str], label: str = ""
) -> float | None:
    """Compute year-over-year percentage change from a FRED series."""
    try:
        series = fred.get_series(series_id)
        if series is None or len(series) < 2:
            warnings.append(f"FRED {label or series_id}: insufficient data for YoY calc")
            return None
        current = float(series.iloc[-1])
        # Find value ~12 months ago
        year_ago = float(series.iloc[0]) if len(series) == 2 else float(series.iloc[-13]) if len(series) >= 13 else float(series.iloc[0])
        if year_ago == 0:
            return None
        yoy = (current - year_ago) / year_ago * 100
        return round(yoy, 2)
    except Exception as e:
        warnings.append(f"FRED {label or series_id} YoY calc failed: {e}")
        return None
