"""Print today's momentum ranking.

    python scripts/screen.py            # top 25 (what the strategy would hold)
    python scripts/screen.py -n 50      # top 50
    python scripts/screen.py --csv out.csv
"""
from __future__ import annotations

import argparse, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import pandas as pd

from momentum import data
from momentum.config import PORTFOLIO
from momentum.screen import Factors
from momentum.universe import market_cap_panel, members_on


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=PORTFOLIO.n_hold)
    ap.add_argument("--csv")
    ap.add_argument("--date", help="as-of date (default: latest close in the cache)")
    args = ap.parse_args()

    pool = data.build_pool()
    close, volume = data.load_prices(pool["yf"].tolist())
    shares = data.load_shares([t for t in pool["yf"] if t in close.columns])
    meta = pool.set_index("yf")[["symbol", "name", "industry"]].to_dict("index")

    mcap = market_cap_panel(close, shares)
    factors = Factors(close, volume)

    asof = pd.Timestamp(args.date) if args.date else close.index[-1]
    if asof not in close.index:
        asof = close.index[close.index <= asof][-1]

    universe = members_on(mcap, asof, PORTFOLIO.universe_top_n)
    ranked = factors.rank_on(asof, universe=universe, n=args.n)

    ranked.insert(1, "symbol", [meta.get(i, {}).get("symbol", i) for i in ranked.index])
    ranked.insert(2, "company", [meta.get(i, {}).get("name", "") for i in ranked.index])
    ranked.insert(3, "industry", [meta.get(i, {}).get("industry", "") for i in ranked.index])

    show = ranked[["rank", "symbol", "company", "score", "ret_12_1", "vol",
                   "ret_3m", "close", "turnover_cr"]].copy()
    for c in ("ret_12_1", "vol", "ret_3m"):
        show[c] = (show[c] * 100).round(1)
    show[["score", "close", "turnover_cr"]] = show[["score", "close", "turnover_cr"]].round(2)

    print(f"\nMomentum ranking as of {asof.date()}  "
          f"(universe: point-in-time top {PORTFOLIO.universe_top_n} by market cap)\n")
    with pd.option_context("display.width", 200, "display.max_columns", 20,
                           "display.max_colwidth", 30):
        print(show.to_string(index=False))

    if args.csv:
        ranked.to_csv(args.csv, index=False)
        print(f"\nwrote {args.csv}")


if __name__ == "__main__":
    main()
