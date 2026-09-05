"""Point-in-time index membership.

A backtest run over *today's* NIFTY 500 quietly deletes every company that fell
out of the index along the way -- which is precisely the set of companies that
did badly. That inflates any long-only result.

The fix here is to rebuild membership from data. The candidate pool is the union
of NIFTY 500, Total Market 750 and Microcap 250, so names that dropped out of the
500 are still present. At each rebalance date the pool is ranked by *point-in-time*
market cap (that date's adjusted price times that date's shares outstanding) and
the top 500 are treated as the index.

This reproduces NSE's own primary selection criterion -- full market
capitalisation -- but not its liquidity screens, cutoff buffers or the quarterly
review calendar, so membership at the edges differs from the official list. It is
a far better approximation than a static current-500 snapshot, and it is
reproducible from public data, which the official historical lists are not.

Known residual bias: companies delisted outright (rather than merely demoted) are
absent from every current NSE file and so cannot enter the pool at all.
"""
from __future__ import annotations

import pandas as pd


def market_cap_panel(close: pd.DataFrame, shares: pd.DataFrame) -> pd.DataFrame:
    """Daily market cap = adjusted close x point-in-time shares outstanding.

    Note the adjusted close is split/bonus adjusted while the share count is not,
    so their product is only a *ranking* quantity, not a rupee market cap. Rank is
    all index membership needs.
    """
    aligned = shares.reindex(close.index).ffill()
    common = close.columns.intersection(aligned.columns)
    return (close[common] * aligned[common]).dropna(how="all")


def members_on(mcap: pd.DataFrame, date: pd.Timestamp, top_n: int = 500) -> pd.Index:
    """The top ``top_n`` names by market cap on ``date``."""
    if date not in mcap.index:
        prior = mcap.index[mcap.index <= date]
        if not len(prior):
            return pd.Index([])
        date = prior[-1]
    row = mcap.loc[date].dropna()
    return row.nlargest(min(top_n, len(row))).index


def membership_history(mcap: pd.DataFrame, dates, top_n: int = 500) -> dict:
    return {d: members_on(mcap, d, top_n) for d in dates}


def churn_report(history: dict) -> pd.DataFrame:
    """How much the reconstructed index turns over -- a sanity check on the method."""
    rows, prev, prev_d = [], None, None
    for d, members in history.items():
        if prev is not None:
            entered = len(set(members) - set(prev))
            exited = len(set(prev) - set(members))
            rows.append({"date": d, "n": len(members), "entered": entered, "exited": exited})
        prev, prev_d = members, d
    return pd.DataFrame(rows)
