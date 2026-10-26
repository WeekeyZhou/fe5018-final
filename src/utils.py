"""Shared helper functions for the FE5108 class project.

Everyone imports from here so that every part converts units, annualizes
and saves charts in exactly the same way.

Team conventions
----------------
* Returns are monthly and in DECIMALS (0.01 = 1%).
  Fama-French files are in percent -> use pct_to_decimal().
  MSCI files are index levels      -> use levels_to_returns().
* Index = monthly pandas Period ('M'), each row = return earned IN that month.
  -> use to_monthly_index().
* Volatility is always annualized as  std(monthly) * sqrt(12).
* Annualized return comes in two flavours; you must say which one you use:
    "arithmetic": mean(monthly) * 12
    "geometric" : (prod(1 + r)) ** (12 / n) - 1   (compound growth rate)
  The assignment asks you to think about which mean is appropriate (1A, 2C),
  so the choice is made per question and stated in the report.

Usage from a notebook in partN/:
    import sys; sys.path.append("..")
    from src import config, utils
    config.apply_style()
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

from . import config

M = config.MONTHS_PER_YEAR


# --------------------------------------------------------------------------
# Units and dates
# --------------------------------------------------------------------------
def pct_to_decimal(x):
    """Fama-French percent returns (1.5 = 1.5%) -> decimals (0.015)."""
    return x / 100.0


def to_monthly_index(obj, fmt: str | None = None):
    """Convert the index to monthly pandas Periods.

    Handles Fama-French 'YYYYMM' integers/strings (e.g. 199501),
    MSCI text dates (e.g. 'Jan 31, 1995') and normal datetimes.
    """
    obj = obj.copy()
    idx = pd.Index(obj.index).astype(str).str.strip()
    if fmt is None and idx.str.fullmatch(r"\d{6}(\.0)?").all():
        fmt = "%Y%m"
        idx = idx.str[:6]
    obj.index = pd.to_datetime(idx, format=fmt).to_period("M")
    obj.index.name = "month"
    return obj


def levels_to_returns(levels):
    """Index levels (e.g. MSCI) -> month-end to month-end decimal returns.

    Strips thousands separators such as '1,182.011' first.
    The first row is dropped (no prior level).
    """
    if isinstance(levels, pd.DataFrame):
        levels = levels.apply(lambda s: pd.to_numeric(
            s.astype(str).str.replace(",", ""), errors="coerce"))
    else:
        levels = pd.to_numeric(levels.astype(str).str.replace(",", ""), errors="coerce")
    return levels.pct_change().iloc[1:]


def select_period(obj, key: str):
    """Slice to an analysis period defined in config.PERIODS, e.g. '1C'."""
    start, end = config.PERIODS[key]
    return obj.loc[start:end]


# --------------------------------------------------------------------------
# Annualization and performance statistics
# --------------------------------------------------------------------------
def annualized_return(r, method: str):
    """Annualized return of monthly decimal returns.

    method="arithmetic": mean * 12
    method="geometric" : prod(1 + r) ** (12 / n) - 1
    """
    r = r.dropna() if isinstance(r, pd.Series) else r
    if method == "arithmetic":
        return r.mean() * M
    if method == "geometric":
        n = r.count()
        return (1 + r).prod() ** (M / n) - 1
    raise ValueError('method must be "arithmetic" or "geometric"')


def annualized_volatility(r):
    """std(monthly, sample) * sqrt(12)."""
    return r.std(ddof=1) * np.sqrt(M)


def sharpe_ratio(r, rf, method: str):
    """Assignment footnote 2:
    (annualized strategy return - annualized risk-free return) / annualized volatility.

    r and rf must be aligned monthly decimal series; the same `method`
    is used to annualize both.
    """
    r, rf = r.align(rf, join="inner")
    return (annualized_return(r, method) - annualized_return(rf, method)) / annualized_volatility(r)


def tracking_error(r, benchmark):
    """Annualized std of the monthly return difference (r - benchmark)."""
    r, benchmark = r.align(benchmark, join="inner")
    return annualized_volatility(r - benchmark)


def t_stat_mean(r):
    """t-stat of the mean monthly return: mean / (std / sqrt(n)).
    No Newey-West adjustment (as allowed in 1A)."""
    r = r.dropna()
    return r.mean() / (r.std(ddof=1) / np.sqrt(r.count()))


def cumulative_value(r, start_value: float = 1.0):
    """Value of `start_value` invested, compounding monthly decimal returns."""
    return start_value * (1 + r).cumprod()


# --------------------------------------------------------------------------
# Charts and tables
# --------------------------------------------------------------------------
def new_fig(size: str = "full", nrows: int = 1, ncols: int = 1, **kwargs):
    """Create a figure at report size: size = "full", "half" or "tall"."""
    figsize = {"full": config.FIG_FULL, "half": config.FIG_HALF,
               "tall": config.FIG_TALL}[size]
    return plt.subplots(nrows, ncols, figsize=figsize, **kwargs)


def percent_axis(ax, axis: str = "y", decimals: int = 0):
    """Show decimal values as percentages on an axis (0.05 -> 5%)."""
    fmt = PercentFormatter(xmax=1.0, decimals=decimals)
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(fmt)


def save_fig(fig, name: str, source: str | None = None):
    """Save to output/figures/<name>.png at print size.

    name   : include the question number, e.g. "fig_1C_sharpe"
    source : one-line note printed under the chart, e.g.
             "Source: MSCI, Kenneth French Data Library. Jan 1995 - Jul 2023. US large+mid cap."
    """
    if source:
        fig.text(0.0, -0.02, source, ha="left", va="top",
                 fontsize=config.FONT_NOTE, color="#555555")
    config.FIG_DIR.mkdir(parents=True, exist_ok=True)
    path = config.FIG_DIR / f"{name}.png"
    fig.savefig(path)
    return path


def save_table(df: pd.DataFrame, name: str, float_format: str = "%.4f"):
    """Save to output/tables/<name>.csv, e.g. name = "tab_3A_weights"."""
    config.TAB_DIR.mkdir(parents=True, exist_ok=True)
    path = config.TAB_DIR / f"{name}.csv"
    df.to_csv(path, float_format=float_format)
    return path
