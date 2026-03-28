"""Tests for UI component logic (no Streamlit dependency)."""
import pytest


def _format_ratio_value(val):
    """Format a ratio value safely — mirrors logic in components.py ratio table."""
    try:
        return f"{float(val):.2f}"
    except (ValueError, TypeError):
        return str(val)


@pytest.mark.parametrize("val, expected", [
    (28.5, "28.50"),
    (0, "0.00"),
    (-3.14, "-3.14"),
    ("28.5x", "28.5x"),
    ("N/A", "N/A"),
    ("N/M", "N/M"),
    (None, "None"),
])
def test_format_ratio_value_handles_all_types(val, expected):
    """Ratio table must not crash on string values from Claude (bug #14)."""
    assert _format_ratio_value(val) == expected


# --- Dollar-sign escaping for Streamlit LaTeX ---

from src.ui.components import _escape_dollars


@pytest.mark.parametrize("text, expected", [
    ("a $2.6B net cash position", r"a \$2.6B net cash position"),
    ("no dollars here", "no dollars here"),
    ("$100M revenue and $50M profit", r"\$100M revenue and \$50M profit"),
    ("", ""),
])
def test_escape_dollars(text, expected):
    """Dollar signs must be escaped to prevent Streamlit LaTeX rendering."""
    assert _escape_dollars(text) == expected
