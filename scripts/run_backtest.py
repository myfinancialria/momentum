"""Run the full study and write data/results.json + the report tables."""
from __future__ import annotations

import argparse, json, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from momentum import data, metrics, backtest as bt
from momentum.config import BT, PORTFOLIO, RULES, DATA, as_dict
from momentum.screen import Factors
from momentum.universe import market_cap_panel, membership_history, churn_report
from dataclasses import replace


def jsonable(o):
    if isinstance(o, (np.integer,)): return int(o)
    if isinstance(o, (np.floating,)): return None if np.isnan(o) else float(o)
    if isinstance(o, (pd.Timestamp,)): return str(o.date())
    if isinstance(o, pd.Series): return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, dict): return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [jsonable(x) for x in o]
    if isinstance(o, float) and np.isnan(o): return None
    return o


def curve_points(curve: pd.Series, every: int = 5):
    c = curve.iloc[::every]
    if curve.index[-1] not in c.index:
        c = pd.concat([c, curve.iloc[[-1]]])
    return [{"d": str(i.date()), "v": round(float(v), 4)} for i, v in c.items()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=BT.start)
    ap.add_argument("--end", default=BT.end)
    ap.add_argument("--quick", action="store_true", help="skip robustness sweeps")
    args = ap.parse_args()

    print("[load] pool / prices / shares", flush=True)
    pool = data.build_pool()
    close, volume = data.load_prices(pool["yf"].tolist())
    shares = data.load_shares([t for t in pool["yf"] if t in close.columns])
    bench = data.load_benchmark()

    meta = pool.set_index("yf")[["symbol", "name", "industry"]].to_dict("index")

    print(f"[load] panel {close.shape}, shares {shares.shape}", flush=True)
    mcap = market_cap_panel(close, shares)
    print(f"[universe] mcap panel {mcap.shape}", flush=True)

    factors = Factors(close, volume)
    print("[factors] built", flush=True)

    # ---------------------------------------------------------------- main run
    res = bt.run(factors, mcap, args.start, args.end)
    curve = res["daily"]
    summary = metrics.summarise(curve, "Momentum 25")
    print(f"[main] CAGR {summary['cagr']:.1%}  MDD {summary['max_drawdown']:.1%}", flush=True)

    # ------------------------------------------------------------- benchmark
    b = bench.reindex(curve.index).ffill().dropna()
    b = b / b.iloc[0]
    bench_summary = metrics.summarise(b, "NIFTY 500")

    # ------------------------------------------------------- random null
    print(f"[null] running {BT.n_random_portfolios} random portfolios", flush=True)
    null_cagrs, null_mdds, null_curves = [], [], []
    for i in range(BT.n_random_portfolios):
        r = bt.run(factors, mcap, args.start, args.end,
                   selector=bt.random_selector(BT.seed + i))
        dc = r["daily"]
        null_cagrs.append(metrics.cagr(dc))
        null_mdds.append(metrics.max_drawdown(dc))
        if i < 40:
            null_curves.append(dc)
        if (i + 1) % 25 == 0:
            print(f"[null] {i + 1}/{BT.n_random_portfolios}", flush=True)

    pctile = metrics.percentile_vs(summary["cagr"], null_cagrs)
    print(f"[null] strategy at {pctile:.0f}th percentile of random", flush=True)

    # Null band for the chart: 5th/50th/95th percentile across random curves.
    band = None
    if null_curves:
        nc = pd.concat([c.reindex(curve.index).ffill() for c in null_curves], axis=1)
        band = {
            "p05": curve_points(nc.quantile(0.05, axis=1)),
            "p50": curve_points(nc.quantile(0.50, axis=1)),
            "p95": curve_points(nc.quantile(0.95, axis=1)),
        }

    # ------------------------------------------------------- split sample
    mid = curve.index[len(curve) // 2]
    h1 = curve.loc[:mid] / curve.loc[:mid].iloc[0]
    h2 = curve.loc[mid:] / curve.loc[mid:].iloc[0]
    splits = []
    for lbl, seg, s0, s1 in [("First half", h1, args.start, str(mid.date())),
                             ("Second half", h2, str(mid.date()), args.end)]:
        seg_null = []
        for i in range(60):
            r = bt.run(factors, mcap, s0, s1, selector=bt.random_selector(9000 + i))
            seg_null.append(metrics.cagr(r["daily"]))
        st = metrics.summarise(seg, lbl)
        st["null_pctile"] = metrics.percentile_vs(st["cagr"], seg_null)
        st["null_median_cagr"] = float(np.median(seg_null))
        splits.append(st)
        print(f"[split] {lbl}: {st['cagr']:.1%} -> {st['null_pctile']:.0f}th pctile", flush=True)

    # ------------------------------------------------------- robustness
    robustness = []
    if not args.quick:
        variants = [
            ("Cost 50 bps/side", replace(PORTFOLIO, cost_bps=50)),
            ("Cost 100 bps/side", replace(PORTFOLIO, cost_bps=100)),
            ("Hold 15", replace(PORTFOLIO, n_hold=15)),
            ("Hold 40", replace(PORTFOLIO, n_hold=40)),
            ("Quarterly rebalance", replace(PORTFOLIO, rebalance="QE")),
            ("Universe = top 200", replace(PORTFOLIO, universe_top_n=200)),
            ("Universe = top 750", replace(PORTFOLIO, universe_top_n=750)),
        ]
        for lbl, spec in variants:
            r = bt.run(factors, mcap, args.start, args.end, spec=spec)
            st = metrics.summarise(r["daily"], lbl)
            robustness.append(st)
            print(f"[robust] {lbl}: CAGR {st['cagr']:.1%} MDD {st['max_drawdown']:.1%}", flush=True)

        # Plain 12-1 momentum with no vol divisor, to isolate what the divisor adds.
        raw = Factors(close, volume)
        raw.score = raw.ret_12_1
        r = bt.run(raw, mcap, args.start, args.end)
        st = metrics.summarise(r["daily"], "Raw 12-1 (no vol divisor)")
        robustness.append(st)
        print(f"[robust] raw 12-1: {st['cagr']:.1%}", flush=True)

    # ------------------------------------------------------- current screen
    last = close.index[-1]
    live = factors.rank_on(last, universe=None, n=50)
    from momentum.universe import members_on
    u = members_on(mcap, last, PORTFOLIO.universe_top_n)
    live = factors.rank_on(last, universe=u, n=50)
    live_rows = []
    for tkr, row in live.iterrows():
        m = meta.get(tkr, {})
        live_rows.append({
            "rank": int(row["rank"]), "symbol": m.get("symbol", tkr.replace(".NS", "")),
            "name": m.get("name", ""), "industry": m.get("industry", ""),
            "score": round(float(row["score"]), 3),
            "ret_12_1": round(float(row["ret_12_1"]), 4),
            "vol": round(float(row["vol"]), 4),
            "ret_3m": round(float(row["ret_3m"]), 4),
            "ret_6m": round(float(row["ret_6m"]), 4),
            "ret_12m": round(float(row["ret_12m"]), 4),
            "close": round(float(row["close"]), 2),
            "turnover_cr": round(float(row["turnover_cr"]), 1),
            "pct_off_52w_high": round(float(row["pct_off_52w_high"]), 4),
        })

    # ------------------------------------------------------- holdings / sectors
    hold = res["holdings"]
    sector_mix, top_names = [], []
    if len(hold):
        hold = hold.copy()
        hold["industry"] = [meta.get(i, {}).get("industry", "Unknown") for i in hold.index]
        hold["cname"] = [meta.get(i, {}).get("name", "") for i in hold.index]
        sm = hold["industry"].value_counts(normalize=True).head(12)
        sector_mix = [{"industry": k, "share": round(float(v), 4)} for k, v in sm.items()]
        tn = hold.groupby(["symbol", "cname"]).size().sort_values(ascending=False).head(25)
        top_names = [{"symbol": k[0], "name": k[1], "months": int(v)} for k, v in tn.items()]

    trades = res["trades"]
    turnover_stats = {
        "avg_monthly_turnover": float(trades["turnover"].mean()) if len(trades) else None,
        "avg_names_replaced": float(trades["exited"].mean()) if len(trades) else None,
        "total_cost_drag": float(trades["cost"].sum()) if len(trades) else None,
        "n_rebalances": int(len(trades)),
    }

    churn = churn_report(membership_history(mcap, res["dates"][::3], PORTFOLIO.universe_top_n))

    out = {
        "generated": str(pd.Timestamp.now().date()),
        "config": as_dict(),
        "data_coverage": {
            "pool_symbols": int(len(pool)),
            "priced_symbols": int(close.shape[1]),
            "shares_symbols": int(shares.shape[1]),
            "mcap_symbols": int(mcap.shape[1]),
            "price_first": str(close.index[0].date()),
            "price_last": str(close.index[-1].date()),
        },
        "summary": summary,
        "benchmark": bench_summary,
        "null": {
            "n": BT.n_random_portfolios,
            "cagr_percentile": pctile,
            "median_cagr": float(np.median(null_cagrs)),
            "p05_cagr": float(np.percentile(null_cagrs, 5)),
            "p95_cagr": float(np.percentile(null_cagrs, 95)),
            "median_mdd": float(np.median(null_mdds)),
            "cagrs": [round(float(x), 4) for x in null_cagrs],
        },
        "splits": splits,
        "robustness": robustness,
        "curves": {
            "strategy": curve_points(curve),
            "benchmark": curve_points(b),
            "null_band": band,
            "drawdown": curve_points(metrics.drawdown(curve)),
            "bench_drawdown": curve_points(metrics.drawdown(b)),
        },
        "yearly": {str(k.year): round(float(v), 4)
                   for k, v in metrics.yearly_returns(curve).items()},
        "yearly_bench": {str(k.year): round(float(v), 4)
                         for k, v in metrics.yearly_returns(b).items()},
        "monthly_table": jsonable(metrics.monthly_table(curve).round(4).to_dict("index")),
        "rolling_3y": curve_points(metrics.rolling_cagr(curve, 3).dropna(), every=10),
        "live_screen": live_rows,
        "sector_mix": sector_mix,
        "most_held": top_names,
        "turnover": turnover_stats,
        "universe_churn": jsonable(churn.to_dict("records")) if len(churn) else [],
    }

    (DATA / "results.json").write_text(json.dumps(jsonable(out), indent=1))
    print(f"[done] wrote {DATA / 'results.json'}", flush=True)

    hold_out = hold[["date", "symbol", "cname", "industry", "rank", "score",
                     "ret_12_1", "vol", "close"]] if len(hold) else pd.DataFrame()
    if len(hold_out):
        hold_out.to_csv(DATA / "holdings_history.csv", index=False)
    pd.DataFrame(live_rows).to_csv(DATA / "current_screen.csv", index=False)
    curve.to_frame("equity").to_csv(DATA / "equity_curve.csv")
    print("[done] wrote csv exports", flush=True)


if __name__ == "__main__":
    main()
