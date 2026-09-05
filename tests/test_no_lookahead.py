"""Verify the screener cannot see the future.

The check that matters for any backtest: rebuild the factor panels from data
truncated at the signal date and confirm the ranking is bit-for-bit identical to
the one computed on the full history. If any indicator leaked a future bar, the
truncated run would disagree.

    python tests/test_no_lookahead.py
"""
from __future__ import annotations

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pandas as pd

from momentum.config import PORTFOLIO, DATA
from momentum.screen import Factors
from momentum.universe import market_cap_panel, members_on

DATES = ["2019-03-29", "2021-07-30", "2023-11-30", "2025-05-30"]


def main() -> int:
    close = pd.read_pickle(DATA / "close.pkl")
    volume = pd.read_pickle(DATA / "volume.pkl")
    shares = pd.read_pickle(DATA / "shares.pkl")

    full_f = Factors(close, volume)
    full_m = market_cap_panel(close, shares)

    failures = 0
    for ds in DATES:
        d = close.index[close.index <= ds][-1]
        # Truncate prices, volume AND share counts to <= d.
        tf = Factors(close.loc[:d], volume.loc[:d])
        tm = market_cap_panel(close.loc[:d], shares.loc[:d])

        n = PORTFOLIO.n_hold
        full = list(full_f.rank_on(d, universe=members_on(full_m, d, PORTFOLIO.universe_top_n), n=n).index)
        trunc = list(tf.rank_on(d, universe=members_on(tm, d, PORTFOLIO.universe_top_n), n=n).index)

        if full == trunc:
            print(f"  ok   {d.date()}  {n}/{n} identical")
        else:
            failures += 1
            print(f"  FAIL {d.date()}  overlap {len(set(full) & set(trunc))}/{n}")
            print(f"       full-history : {full[:8]}")
            print(f"       truncated    : {trunc[:8]}")

    print("\nNO LOOK-AHEAD" if not failures else f"\n{failures} DATE(S) LEAKED FUTURE DATA")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
