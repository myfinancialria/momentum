"""Refresh the live screen in results.json without rerunning the full backtest."""
from __future__ import annotations

import json
import pathlib
import sys

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from momentum import data
from momentum.config import DATA, PORTFOLIO, RULES, as_dict
from momentum.screen import Factors
from momentum.universe import market_cap_panel, members_on


def main() -> None:
    pool = data.build_pool()
    # fetch_data.py handles new symbols; this step only reads the refreshed
    # usable panel so a few newly listed/delisted tickers cannot block publishing.
    close, volume = data.load_prices(pool["yf"].tolist(), include_new=False,
                                      refresh_tail=False)
    shares = data.load_shares([t for t in pool["yf"] if t in close.columns])
    if close.empty:
        raise RuntimeError("price cache is empty; refusing to publish an empty screen")

    meta = pool.set_index("yf")[["symbol", "name", "industry"]].to_dict("index")
    mcap = market_cap_panel(close, shares)
    factors = Factors(close, volume)
    last = close.index[-1]
    universe = members_on(mcap, last, PORTFOLIO.universe_top_n)
    live = factors.rank_on(last, universe=universe, n=50)
    if live.empty:
        raise RuntimeError(f"no eligible names at {last.date()}; refusing to publish an empty screen")

    live_rows = []
    for ticker, row in live.iterrows():
        m = meta.get(ticker, {})
        entry = float(row["close"])
        live_rows.append({
            "rank": int(row["rank"]),
            "symbol": m.get("symbol", ticker.replace(".NS", "")),
            "name": m.get("name", ""),
            "industry": m.get("industry", ""),
            "score": round(float(row["score"]), 3),
            "ret_12_1": round(float(row["ret_12_1"]), 4),
            "vol": round(float(row["vol"]), 4),
            "ret_3m": round(float(row["ret_3m"]), 4),
            "ret_6m": round(float(row["ret_6m"]), 4),
            "ret_12m": round(float(row["ret_12m"]), 4),
            "close": round(entry, 2),
            "turnover_cr": round(float(row["turnover_cr"]), 1),
            "pct_off_52w_high": round(float(row["pct_off_52w_high"]), 4),
            "entry_date": str(last.date()),
            "entry_price": round(entry, 2),
            "stop_loss": round(entry * (1.0 - RULES.stop_loss_pct), 2),
            "stop_loss_pct": RULES.stop_loss_pct,
        })

    results_path = DATA / "results.json"
    if not results_path.exists():
        raise RuntimeError("results.json is missing; run the full backtest once before daily updates")
    results = json.loads(results_path.read_text())
    results["generated"] = str(pd.Timestamp.now().date())
    results["config"] = as_dict()
    results["data_coverage"] = {
        **results.get("data_coverage", {}),
        "pool_symbols": int(len(pool)),
        "priced_symbols": int(close.shape[1]),
        "shares_symbols": int(shares.shape[1]),
        "mcap_symbols": int(mcap.shape[1]),
        "price_first": str(close.index[0].date()),
        "price_last": str(last.date()),
    }
    results["screen_asof"] = str(last.date())
    results["live_screen"] = live_rows
    results_path.write_text(json.dumps(results, indent=1))
    pd.DataFrame(live_rows).to_csv(DATA / "current_screen.csv", index=False)
    print(f"[daily] screen updated for {last.date()} ({len(live_rows)} names)")


if __name__ == "__main__":
    main()
