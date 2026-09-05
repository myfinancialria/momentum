"""Performance statistics for an equity curve."""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import TRADING_DAYS

RF = 0.06   # Indian risk-free ~6%; used only for Sharpe/Sortino


def _years(curve: pd.Series) -> float:
    return max((curve.index[-1] - curve.index[0]).days / 365.25, 1e-9)


def cagr(curve: pd.Series) -> float:
    return float(curve.iloc[-1] / curve.iloc[0]) ** (1 / _years(curve)) - 1.0


def drawdown(curve: pd.Series) -> pd.Series:
    return curve / curve.cummax() - 1.0


def max_drawdown(curve: pd.Series) -> float:
    return float(drawdown(curve).min())


def summarise(curve: pd.Series, label: str = "") -> dict:
    """Headline stats from a daily equity curve."""
    rets = curve.pct_change().dropna()
    ann_vol = float(rets.std() * np.sqrt(TRADING_DAYS))
    c = cagr(curve)
    downside = rets[rets < 0]
    dvol = float(downside.std() * np.sqrt(TRADING_DAYS)) if len(downside) else np.nan
    mdd = max_drawdown(curve)
    dd = drawdown(curve)

    # Longest stretch below a previous peak, in calendar days.
    under = dd < -1e-9
    longest, run_start = 0, None
    for ts, u in under.items():
        if u and run_start is None:
            run_start = ts
        elif not u and run_start is not None:
            longest = max(longest, (ts - run_start).days); run_start = None
    if run_start is not None:
        longest = max(longest, (under.index[-1] - run_start).days)

    monthly = curve.resample("ME").last().pct_change().dropna()
    return {
        "label": label,
        "start": str(curve.index[0].date()),
        "end": str(curve.index[-1].date()),
        "years": round(_years(curve), 2),
        "total_return": float(curve.iloc[-1] / curve.iloc[0] - 1.0),
        "cagr": c,
        "ann_vol": ann_vol,
        "max_drawdown": mdd,
        "mar": c / abs(mdd) if mdd else np.nan,
        "sharpe": (c - RF) / ann_vol if ann_vol else np.nan,
        "sortino": (c - RF) / dvol if dvol and not np.isnan(dvol) else np.nan,
        "longest_dd_days": longest,
        "monthly_win_rate": float((monthly > 0).mean()) if len(monthly) else np.nan,
        "best_month": float(monthly.max()) if len(monthly) else np.nan,
        "worst_month": float(monthly.min()) if len(monthly) else np.nan,
    }


def yearly_returns(curve: pd.Series) -> pd.Series:
    """Calendar-year returns, with the first and last years partial."""
    yr = curve.resample("YE").last()
    first = pd.Series([curve.iloc[0]], index=[curve.index[0]])
    return pd.concat([first, yr]).pct_change().dropna()


def monthly_table(curve: pd.Series) -> pd.DataFrame:
    m = curve.resample("ME").last().pct_change().dropna()
    df = m.to_frame("ret")
    df["year"], df["month"] = df.index.year, df.index.month
    return df.pivot_table(index="year", columns="month", values="ret")


def rolling_cagr(curve: pd.Series, window_years: int = 3) -> pd.Series:
    w = int(window_years * TRADING_DAYS)
    if len(curve) <= w:
        return pd.Series(dtype=float)
    return (curve / curve.shift(w)) ** (1 / window_years) - 1.0


def percentile_vs(value: float, sample: list[float]) -> float:
    """Where ``value`` sits inside ``sample``, 0-100."""
    arr = np.asarray(sample, dtype=float)
    arr = arr[~np.isnan(arr)]
    return float((arr < value).mean() * 100) if len(arr) else np.nan
