"""Render data/results.json as REPORT.md — the detailed written report."""
from __future__ import annotations
import json, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from momentum.config import DATA, ROOT

D = json.loads((DATA / "results.json").read_text())
S, B, N, C = D["summary"], D["benchmark"], D["null"], D["config"]
R, P = C["rules"], C["portfolio"]

def pc(x, d=1): return "—" if x is None else f"{x*100:.{d}f}%"
def nu(x, d=2): return "—" if x is None else f"{x:.{d}f}"

def row(s, extra=""):
    return (f"| {s['label']} | {pc(s['cagr'])} | {pc(s['total_return'],0)} | {pc(s['max_drawdown'])} "
            f"| {pc(s['ann_vol'])} | {nu(s['mar'])} | {nu(s['sharpe'])} |{extra}")

HDR = ("| | CAGR | Total | Max DD | Vol | MAR | Sharpe |\n"
       "|---|---:|---:|---:|---:|---:|---:|")

verdict_ok = N["cagr_percentile"] >= 80 and all(s["null_pctile"] >= 70 for s in D["splits"])

L = []
A = L.append
A(f"# NSE Momentum — risk-adjusted momentum screener and backtest\n")
A(f"*Generated {D['generated']}. Data cut {D['data_coverage']['price_last']}. "
  f"Full interactive report: **https://myfinancialria.github.io/momentum/***\n")

A("## The rules\n")
A("```")
A(f"SCORE   = (return from t-{R['lookback_days']}d to t-{R['skip_days']}d)  /  (annualised sigma of daily returns, {R['vol_days']}d)")
A(f"          i.e. 12-month momentum skipping the last month, per unit of risk\n")
A("FILTERS   a name must pass all of these to be ranked")
A(f"  1. Close > {R['sma_days']}-day SMA                            trade only established uptrends")
A(f"  2. No single-day move > {pc(R['max_daily_move'],0)} in the lookback       drop news-spike momentum")
A(f"  3. {R['turnover_days']}-day average traded value > Rs {R['min_turnover_cr']} crore    must be exitable")
A(f"  4. Close > Rs {R['min_price']} and >= {R['min_history_days']} bars of history      sanity")
A(f"  5. Inside the point-in-time top {P['universe_top_n']} by market cap   the reconstructed NIFTY 500\n")
A(f"PORTFOLIO Rank descending, hold the top {P['n_hold']}, {P['weighting']} weight")
A(f"          Rebalance {'monthly' if P['rebalance']=='ME' else P['rebalance']}, costs {P['cost_bps']} bps per side on traded value")
A("```\n")

A("## Headline result\n")
A(f"{S['start']} to {S['end']} ({S['years']} years), net of costs.\n")
A(HDR)
A(row(S)); A(row(B))
A("")
A(f"- **Rs 1 grew to Rs {1+S['total_return']:.2f}** against Rs {1+B['total_return']:.2f} for the index.")
A(f"- Worst peak-to-trough loss **{pc(S['max_drawdown'])}**, and the longest time spent below a "
  f"previous high was **{S['longest_dd_days']} days** (~{S['longest_dd_days']/365:.1f} years).")
A(f"- {pc(S['monthly_win_rate'],0)} of months positive; best {pc(S['best_month'])}, worst {pc(S['worst_month'])}.\n")

A("## The honest benchmark: is this better than luck?\n")
A("An equal-weight basket of *randomly chosen* stocks from this universe beat the cap-weighted "
  "NIFTY 500 most of the time over this window — small and mid caps outran large caps and equal "
  "weighting leans into them. So \"it beat the index\" proves very little. The test that matters "
  "is where the ruleset lands inside the distribution of random portfolios drawn from the same "
  "eligible names on the same dates.\n")
A(f"- {N['n']} random 25-stock portfolios: median CAGR **{pc(N['median_cagr'])}**, "
  f"5th–95th percentile {pc(N['p05_cagr'])} to {pc(N['p95_cagr'])}.")
A(f"- The ruleset's {pc(S['cagr'])} sits at the **{N['cagr_percentile']:.0f}th percentile** of that distribution.")
A(f"- For reference the NIFTY 500 itself returned {pc(B['cagr'])} — "
  f"below the random median, which is the whole point.\n")

A("### Split sample\n")
A("The single most useful robustness check: does the edge appear in both halves, or is it one "
  "lucky stretch?\n")
A("| Window | CAGR | Max DD | Random median | Percentile |\n|---|---:|---:|---:|---:|")
for s in D["splits"]:
    A(f"| {s['label']} ({s['start']} → {s['end']}) | {pc(s['cagr'])} | {pc(s['max_drawdown'])} "
      f"| {pc(s['null_median_cagr'])} | **{s['null_pctile']:.0f}th** |")
A("")

A("## Robustness\n")
A("A result that survives at only one setting is a curve fit. Same rules, one knob moved at a time.\n")
A(HDR.replace("| |", "| Variant |"))
A(row({**S, "label": "Base case (as specified)"}))
for r in D["robustness"]:
    A(row(r))
A("")

A("## Year by year\n")
A("| Year | Momentum 25 | NIFTY 500 |\n|---|---:|---:|")
for y, v in D["yearly"].items():
    A(f"| {y} | {pc(v)} | {pc(D['yearly_bench'].get(y))} |")
A("\n*First and last years are partial.*\n")

A("## Turnover and cost\n")
T = D["turnover"]
A(f"- {T['n_rebalances']} monthly rebalances.")
A(f"- Average **{T['avg_names_replaced']:.1f} of {P['n_hold']} names replaced** each month "
  f"({pc(T['avg_monthly_turnover']/2,0)} of the book).")
A(f"- Total cost charged across the whole backtest: {pc(T['total_cost_drag'],1)} of compounded value.")
A(f"- At 100 bps/side the strategy still returns "
  f"{pc(next((r['cagr'] for r in D['robustness'] if '100 bps' in r['label']), None))}.\n")

A("## Current ranking\n")
A(f"Top {min(25,len(D['live_screen']))} as of {D['data_coverage']['price_last']}. "
  "Research output, not advice.\n")
A("| # | Symbol | Company | Industry | Score | 12m−1m | σ ann. | Rs Close |\n|---:|---|---|---|---:|---:|---:|---:|")
for r in D["live_screen"][:25]:
    A(f"| {r['rank']} | **{r['symbol']}** | {r['name'][:34]} | {r['industry'][:26]} | "
      f"{nu(r['score'])} | {pc(r['ret_12_1'],0)} | {pc(r['vol'],0)} | {r['close']:.1f} |")
A("")

A("## Method\n")
cov = D["data_coverage"]
A("**The universe is rebuilt, not assumed.** Running this over *today's* NIFTY 500 would quietly "
  "delete every company that fell out of the index along the way — which is exactly the set that "
  "did badly — and inflate any long-only result. Instead:\n")
A(f"- The candidate pool is the union of NIFTY 500, Total Market 750, Microcap 250 **and the full "
  f"NSE equity list** — {cov['pool_symbols']} symbols, of which {cov['priced_symbols']} have usable "
  f"price history and {cov['mcap_symbols']} have point-in-time share counts.")
A("- Index membership is rebuilt at every rebalance by ranking that pool on market cap computed "
  "from *that date's* price and *that date's* shares outstanding (a real shares-outstanding time "
  "series, not today's count projected backwards).")
A(f"- Prices are split/bonus-adjusted daily closes, {cov['price_first']} to {cov['price_last']}.\n")

A("**Backtest assumptions.** Signals use data up to and including the rebalance close and the book "
  "is assumed established at that same close — one bar of optimism, which the "
  f"{P['cost_bps']} bps/side cost assumption is set generously to offset. Costs are charged on "
  "traded value at each rebalance and cover brokerage, STT, impact and slippage. No leverage, no "
  "shorting, no stop losses, always fully invested.\n")

A("## Caveats\n")
A("- **The pool still has a floor.** A company delisted outright is absent from every current NSE "
  "file and cannot enter the pool at any date. The reconstruction removes most survivorship bias, "
  "not all of it.")
A("- **Reconstructed membership is not official membership.** Market-cap ranking reproduces NSE's "
  "primary selection criterion but not its liquidity screens, cutoff buffers or review calendar, "
  "so names at the 500 boundary differ from the official list.")
A(f"- **One market, one regime.** {S['years']} years covers a COVID recovery, a 2022 correction and "
  "a long mid-cap bull run — but no prolonged Indian bear market. Momentum's known failure mode is "
  "the sharp reversal that ends a downtrend, and this window is thin on those.")
A("- **Backtests are not returns.** No live execution, no impact from trading real size in mid "
  "caps, no taxes.\n")

A("## Reproducing\n")
A("```bash\npip install -r requirements.txt\npython scripts/fetch_data.py     # ~20 min, cached\n"
  "python scripts/run_backtest.py   # writes data/results.json\n"
  "python scripts/make_report.py    # writes REPORT.md\n"
  "python scripts/build_site.py     # writes docs/index.html\n"
  "python scripts/screen.py -n 25   # today's ranking\n```\n")
A("---\n*Research and education only. Backtested results are hypothetical, contain no live "
  "execution, and are not a recommendation to buy or sell any security.*")

(ROOT / "REPORT.md").write_text("\n".join(L))
print(f"[report] wrote REPORT.md ({len('\n'.join(L))//1024} KB), verdict_ok={verdict_ok}")
