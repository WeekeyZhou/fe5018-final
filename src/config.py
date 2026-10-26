"""Project-wide configuration for the FE5108 class project.

Paths, data file names, analysis periods and the shared chart style.
Change values here (not in your own notebook) so the whole team stays consistent.

Usage from a notebook in partN/:
    import sys; sys.path.append("..")
    from src import config, utils
    config.apply_style()
"""

from pathlib import Path

import matplotlib as mpl

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
DATA_RAW = ROOT / "data" / "raw"
FIG_DIR = ROOT / "output" / "figures"
TAB_DIR = ROOT / "output" / "tables"

# Data files provided by the professor (do not edit them)
FILE_FF_MSCI = DATA_RAW / "class project data (FF MSCI) (parts 1 and 5).xlsx"
FILE_PART2 = DATA_RAW / "class project data (part 2 - factor portfolio construction).csv"
FILE_PART3 = DATA_RAW / "class project data (part 3 - pf construction).xlsx"

# Sheet names inside FILE_FF_MSCI
SHEET_FF_BETA = "FF - portfolios sorted on beta"
SHEET_FF_MOM = "FF - portfolios sorted on pmom"
SHEET_FF3 = "FF - 3 factor returns"
SHEET_MSCI = "MSCI - factor totret index"

# --------------------------------------------------------------------------
# Analysis periods, as stated in the assignment (inclusive, "YYYY-MM")
# --------------------------------------------------------------------------
PERIODS = {
    # Part 1
    "1A_pre":  ("1927-01", "1992-12"),   # "1927 through 1992"
    "1A_post": ("1993-01", "2023-07"),   # post-publication
    "1C":      ("1995-01", "2023-07"),
    "1D":      ("1995-01", "2023-07"),
    "1E":      ("1995-12", "2023-07"),   # first month with 12m trailing vol
    # Part 2 (portfolio formation dates; returns cover 1999-2018)
    "2B":      ("1998-12", "2018-11"),
    # Part 3
    "3_seed":  ("1995-01", "2004-12"),   # covariance estimation, 3A/3B
    "3C":      ("2005-01", "2023-07"),   # out-of-sample
    "3D_seed": ("2006-01", "2015-12"),
    "3D_oos":  ("2016-01", "2023-07"),
    "3E":      ("2005-01", "2023-07"),
    "3E_gfc":  ("2008-09", "2009-02"),
    "3E_covid": ("2020-02", "2020-03"),
}

MONTHS_PER_YEAR = 12

# --------------------------------------------------------------------------
# Chart style
# Figures are saved at their PRINTED size, so font sizes below are the sizes
# the reader actually sees in the report. Do not resize figures in Word.
# --------------------------------------------------------------------------
FIG_FULL = (6.0, 2.8)      # full text width
FIG_HALF = (3.0, 2.3)      # half width, two side by side
FIG_TALL = (6.0, 4.0)      # full width, e.g. 2x2 panels or heatmap
DPI = 300

FONT_SIZE = 8              # axis labels, general text
FONT_SMALL = 7             # tick labels, legend
FONT_TITLE = 9             # chart title
FONT_NOTE = 6.5            # source / footnote line under the chart

# Colour-blind-safe palette (Okabe-Ito). Use in this order for series.
COLORS = ["#0072B2", "#E69F00", "#009E73", "#D55E00",
          "#CC79A7", "#56B4E9", "#F0E442", "#000000"]
COLOR_MARKET = "#4D4D4D"   # always use this for the market / benchmark line
COLOR_POS = "#009E73"      # e.g. top-5 weights (3A)
COLOR_NEG = "#D55E00"      # e.g. bottom-5 weights (3A)


def apply_style() -> None:
    """Apply the team chart style. Call once at the top of every notebook."""
    mpl.rcParams.update({
        "figure.figsize": FIG_FULL,
        "figure.dpi": 110,                 # on-screen preview
        "savefig.dpi": DPI,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.03,
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "font.size": FONT_SIZE,
        "axes.titlesize": FONT_TITLE,
        "axes.titleweight": "bold",
        "axes.labelsize": FONT_SIZE,
        "xtick.labelsize": FONT_SMALL,
        "ytick.labelsize": FONT_SMALL,
        "legend.fontsize": FONT_SMALL,
        "legend.frameon": False,
        "axes.prop_cycle": mpl.cycler(color=COLORS),
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": "#E5E5E5",
        "grid.linewidth": 0.5,
        "axes.linewidth": 0.6,
        "lines.linewidth": 1.2,
        "xtick.major.width": 0.6,
        "ytick.major.width": 0.6,
        "figure.constrained_layout.use": True,
    })
