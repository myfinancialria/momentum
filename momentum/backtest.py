"""Monthly-rebalanced, equal-weight momentum backtest with costs.

Mechanics
  * Rebalance on the last trading day of each month.
  * Rank the point-in-time NIFTY 500 by the screener's score, take the top N.
  * Equal weight, held until the next rebalance, marked to market daily.
  * Costs charged on the traded value at each rebalance (one-way bps on the sum
    of absolute weight changes), covering brokerage, STT, impact and slippage.

Signals are computed from data up to and including the rebalance close and the
portfolio is assumed to be established at that same close. That is a one-bar
optimism; the 25bps/side cost assumption is deliberately generous to offset it,
and ``--cost-bps`` lets a reader push it further.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import PORTFOLIO, TRADING_DAYS
from .screen import Factors
from .universe import members_on


def rebalance_dates(index: pd.DatetimeIndex, start: str, end: str, freq: str = "ME"):
    """Last trading day of each period inside [start, end]."""
    idx = index[(index >= pd.Timestamp(start)) & (index <= pd.Timestamp(end))]
    return list(pd.Series(idx, index=idx).resample(freq).last().dropna())


def run(factors: Factors, mcap: pd.DataFrame, start: str, end: str,
        spec=PORTFOLIO, selector=None) -> dict:
    """Run the backtest. ``selector`` overrides stock picking (used by the null)."""
    close = factors.close
    dates = rebalance_dates(close.index, start, end, spec.rebalance)
    if len(dates) < 2:
        raise ValueError("not enough rebalance dates")

    weights = pd.Series(dtype=float)
    equity, curve_idx = [1.0], [dates[0]]
    holdings_log, trades_log = [], []
    cost_frac = spec.cost_bps / 10_000.0

    for i, d in enumerate(dates[:-1]):
        nxt = dates[i + 1]
        universe = members_on(mcap, d, spec.universe_top_n)

        if selector is None:
            ranked = factors.rank_on(d, universe=universe, n=spec.n_hold)
            picks = list(ranked.index)
        else:
            picks = selector(d, factors, universe, spec)
            ranked = pd.DataFrame(index=picks)

        if not picks:
            equity.append(equity[-1]); curve_idx.append(nxt)
            continue

        target = pd.Series(1.0 / len(picks), index=picks)

        # Cost on the change from the drifted book to the new target.
        allnames = target.index.union(weights.index)
        turn = (target.reindex(allnames).fillna(0) - weights.reindex(allnames).fillna(0)).abs().sum()
        cost = turn * cost_frac

        # Segment return: equal-weight the picks' price return to the next date.
        seg = close.loc[d:nxt, picks]
        rel = seg.divide(seg.iloc[0], axis=1)
        # A name that stops trading mid-segment holds its last observed value.
        rel = rel.ffill()
        port_path = rel.mean(axis=1, skipna=True)
        seg_ret = float(port_path.iloc[-1]) - 1.0

        equity.append(equity[-1] * (1.0 - cost) * (1.0 + seg_ret))
        curve_idx.append(nxt)

        entered = sorted(set(picks) - set(weights.index))
        exited = sorted(set(weights.index) - set(picks))
        trades_log.append({"date": d, "n": len(picks), "turnover": turn,
                           "cost": cost, "entered": len(entered), "exited": len(exited),
                           "seg_ret": seg_ret})
        if selector is None:
            snap = ranked.copy()
            snap["date"] = d
            snap["symbol"] = [s.replace(".NS", "") for s in snap.index]
            holdings_log.append(snap)

        # Drift the weights with the segment so next period's turnover is honest.
        end_rel = rel.iloc[-1]
        drifted = target * end_rel
        weights = drifted / drifted.sum()

    curve = pd.Series(equity, index=pd.DatetimeIndex(curve_idx), name="equity")
    daily = _daily_curve(close, factors, mcap, dates, spec, selector)
    return {
        "curve": curve,
        "daily": daily,
        "trades": pd.DataFrame(trades_log),
        "holdings": pd.concat(holdings_log) if holdings_log else pd.DataFrame(),
        "dates": dates,
    }


def _daily_curve(close, factors, mcap, dates, spec, selector) -> pd.Series:
    """Daily mark-to-market equity, needed for drawdown and Sharpe."""
    vals, idx = [], []
    eq = 1.0
    cost_frac = spec.cost_bps / 10_000.0
    weights = pd.Series(dtype=float)

    for i, d in enumerate(dates[:-1]):
        nxt = dates[i + 1]
        universe = members_on(mcap, d, spec.universe_top_n)
        if selector is None:
            picks = list(factors.rank_on(d, universe=universe, n=spec.n_hold).index)
        else:
            picks = selector(d, factors, universe, spec)
        if not picks:
            continue
        target = pd.Series(1.0 / len(picks), index=picks)
        allnames = target.index.union(weights.index)
        turn = (target.reindex(allnames).fillna(0) - weights.reindex(allnames).fillna(0)).abs().sum()
        eq *= (1.0 - turn * cost_frac)

        seg = close.loc[d:nxt, picks]
        rel = seg.divide(seg.iloc[0], axis=1).ffill()
        path = rel.mean(axis=1, skipna=True)
        for ts, v in path.items():
            if ts == d and idx:
                continue
            vals.append(eq * float(v)); idx.append(ts)
        eq = eq * float(path.iloc[-1])
        drifted = target * rel.iloc[-1]
        weights = drifted / drifted.sum()

    return pd.Series(vals, index=pd.DatetimeIndex(idx), name="equity").sort_index()


# ------------------------------------------------------------------ random null

def random_selector(seed: int):
    """Pick N names at random from the eligible point-in-time universe.

    This is the benchmark that matters. In a mid/small-heavy universe an equal
    weight basket of random stocks beats the cap-weighted index handily, so
    'beat the NIFTY 500' is a low bar. The question is whether the ruleset beats
    a coin flip drawn from the same universe.
    """
    rng = np.random.default_rng(seed)

    def sel(date, factors, universe, spec):
        mask = factors.eligible(date)
        names = mask[mask].index.intersection(universe)
        if len(names) == 0:
            return []
        k = min(spec.n_hold, len(names))
        return list(rng.choice(np.array(names), size=k, replace=False))

    return sel
