"""The momentum ruleset: score, filters, ranking.

The rules, in one place:

    SCORE   = (12-month return, skipping the most recent month)
              / (annualised standard deviation of daily returns, 252d)

    FILTERS (a name must pass all of them to be rankable)
      1. Close > 200-day simple moving average          -- trade only uptrends
      2. No single-day move greater than 15% in the
         lookback window                                -- drop news-spike momentum
      3. 20-day average traded value > Rs 5 crore       -- must be exitable
      4. Close > Rs 10 and >= 300 bars of history       -- sanity
      5. Member of the point-in-time NIFTY 500          -- see universe.py

    RANK    = descending score; the top N become the portfolio.

Everything is computed on a full price panel and only *then* sampled at
rebalance dates. Slicing the panel to the backtest window before computing
lookbacks would leave the first year uninvestable -- a mistake worth naming.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import RULES, TRADING_DAYS


class Factors:
    """Precomputed daily factor panels, aligned on the price panel's index."""

    def __init__(self, close: pd.DataFrame, volume: pd.DataFrame, rules=RULES):
        self.rules = rules
        self.close = close
        r = rules

        daily_ret = close.pct_change()

        # 12-1 momentum: price at t-skip over price at t-lookback.
        px_skip = close.shift(r.skip_days)
        px_back = close.shift(r.lookback_days)
        self.ret_12_1 = px_skip / px_back - 1.0

        # Annualised volatility of daily returns.
        self.vol = daily_ret.rolling(r.vol_days, min_periods=r.vol_days // 2).std() \
            * np.sqrt(TRADING_DAYS)

        # The score. Guard against a near-zero denominator.
        self.score = self.ret_12_1 / self.vol.where(self.vol > 1e-6)

        # Filter inputs.
        self.sma = close.rolling(r.sma_days, min_periods=r.sma_days).mean()
        self.max_move = daily_ret.abs().rolling(r.spike_window,
                                                min_periods=r.spike_window // 2).max()
        turnover = close * volume                       # rupees traded
        self.turnover_cr = turnover.rolling(
            r.turnover_days, min_periods=r.turnover_days).mean() / 1e7   # -> Rs crore
        self.bars = close.notna().cumsum()

        # Reference returns used for reporting, not for ranking.
        self.ret_6m = close / close.shift(126) - 1.0
        self.ret_3m = close / close.shift(63) - 1.0
        self.ret_12m = close / close.shift(TRADING_DAYS) - 1.0
        self.dd_from_high = close / close.rolling(TRADING_DAYS, min_periods=60).max() - 1.0

    # ------------------------------------------------------------------ per-date

    def eligible(self, date: pd.Timestamp) -> pd.Series:
        """Boolean mask of names passing every filter on ``date``."""
        r = self.rules
        row = lambda panel: panel.loc[date]      # noqa: E731 - local shorthand
        px = row(self.close)
        return (
            px.notna()
            & (px > r.min_price)
            & (px > row(self.sma))
            & (row(self.max_move) <= r.max_daily_move)
            & (row(self.turnover_cr) > r.min_turnover_cr)
            & (row(self.bars) >= r.min_history_days)
            & row(self.score).notna()
        )

    def rank_on(self, date: pd.Timestamp, universe: pd.Index | None = None,
                n: int | None = None) -> pd.DataFrame:
        """Ranked table of candidates on ``date``, best first."""
        mask = self.eligible(date)
        if universe is not None:
            mask &= pd.Series(mask.index.isin(universe), index=mask.index)
        names = mask[mask].index
        if not len(names):
            return pd.DataFrame()

        out = pd.DataFrame({
            "score": self.score.loc[date, names],
            "ret_12_1": self.ret_12_1.loc[date, names],
            "vol": self.vol.loc[date, names],
            "ret_12m": self.ret_12m.loc[date, names],
            "ret_6m": self.ret_6m.loc[date, names],
            "ret_3m": self.ret_3m.loc[date, names],
            "close": self.close.loc[date, names],
            "turnover_cr": self.turnover_cr.loc[date, names],
            "pct_off_52w_high": self.dd_from_high.loc[date, names],
        }).sort_values("score", ascending=False)
        out.insert(0, "rank", range(1, len(out) + 1))
        return out.head(n) if n else out
