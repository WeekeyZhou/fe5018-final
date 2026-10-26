"""Shared helper functions for the FE5108 class project.

Everyone imports from here so that every part annualizes returns and
computes Sharpe ratios in exactly the same way.

Conventions (see README):
    * returns are monthly, in DECIMALS (0.01 = 1%)
    * index = month-end (pandas Period 'M')

TODO: agree on the annualization method as a team, then fill these in.
"""

import pandas as pd


def annualized_return(monthly_returns: pd.Series) -> float:
    """Annualized average return from a series of monthly decimal returns."""
    raise NotImplementedError("Agree on the method as a team first")


def annualized_volatility(monthly_returns: pd.Series) -> float:
    """Annualized standard deviation of monthly decimal returns."""
    raise NotImplementedError


def sharpe_ratio(monthly_returns: pd.Series, monthly_rf: pd.Series) -> float:
    """(annualized return - annualized risk-free return) / annualized volatility.

    Definition as given in footnote 2 of the assignment.
    """
    raise NotImplementedError
