"""S&P 500 stratified random stock screener.

Fetches the full S&P 500 from Wikipedia, then selects a proportional
sample across GICS sectors. Default sample size is 50.
"""
from __future__ import annotations

import math

import pandas as pd


_SP500_WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"


def fetch_sp500_tickers() -> pd.DataFrame:
    """Fetch S&P 500 constituents from Wikipedia.

    Returns DataFrame with at least 'Symbol' and 'GICS Sector' columns.
    """
    tables = pd.read_html(_SP500_WIKI_URL)
    df = tables[0]
    # Some symbols have dots (BRK.B) — yfinance uses hyphens (BRK-B)
    df["Symbol"] = df["Symbol"].str.replace(".", "-", regex=False)
    return df[["Symbol", "Security", "GICS Sector"]].copy()


def compute_sector_allocation(
    sp500: pd.DataFrame, sample_size: int = 50
) -> dict[str, int]:
    """Compute how many stocks to pick per sector, proportional to sector weight.

    Every sector gets at least 1 pick. Remainders are distributed to the
    largest sectors first (largest remainder method).
    """
    sector_counts = sp500["GICS Sector"].value_counts()
    total = len(sp500)

    # Raw proportional allocation (float)
    raw = {sector: (count / total) * sample_size for sector, count in sector_counts.items()}

    # Floor each, guarantee minimum 1
    floored = {sector: max(1, math.floor(val)) for sector, val in raw.items()}
    assigned = sum(floored.values())
    remaining = sample_size - assigned

    # Distribute remaining slots by largest fractional remainder
    remainders = {sector: raw[sector] - floored[sector] for sector in raw}
    for sector in sorted(remainders, key=remainders.get, reverse=True):
        if remaining <= 0:
            break
        floored[sector] += 1
        remaining -= 1

    return floored


def select_stratified_sample(
    sp500: pd.DataFrame, sample_size: int = 50, seed: int | None = None
) -> pd.DataFrame:
    """Select a stratified random sample from the S&P 500.

    Returns a DataFrame with 'Symbol' and 'GICS Sector' (and other columns
    from the source). Each sector is represented proportionally.
    """
    allocation = compute_sector_allocation(sp500, sample_size)
    samples = []
    for sector, n in allocation.items():
        sector_df = sp500[sp500["GICS Sector"] == sector]
        n_pick = min(n, len(sector_df))
        samples.append(sector_df.sample(n=n_pick, random_state=seed))
    return pd.concat(samples).reset_index(drop=True)
