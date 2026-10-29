# momentum

A rules-based **momentum screener for NSE equities** — filter, rank, backtest, publish.

**📊 Full interactive report → [myfinancialria.github.io/momentum](https://myfinancialria.github.io/momentum/)**
· Written report → [REPORT.md](REPORT.md)

---

## The ruleset

Risk-adjusted momentum: rank by how much a stock has run *per unit of risk taken*, not by raw
return, so the ranking isn't dominated by a handful of violently volatile names.

```
SCORE   = (return from t-252d to t-21d)  /  (annualised sigma of daily returns, 252d)
          i.e. 12-month momentum skipping the last month, per unit of risk

FILTERS   a name must pass all of these to be ranked
  1. Close > 200-day SMA                          trade only established uptrends
  2. No single-day move > 15% in the lookback     drop news-spike momentum
  3. 20-day average traded value > Rs 5 crore     must be exitable
  4. Close > Rs 10 and >= 300 bars of history     sanity
  5. Inside the point-in-time top 500 by mcap     the reconstructed NIFTY 500

PORTFOLIO Rank descending, hold the top 25, equal weight
          Rebalance monthly, costs 25 bps per side on traded value
```

The skip-month avoids short-term reversal; the volatility divisor is what makes this
*risk-adjusted* rather than plain 12-1 momentum. Every one of these numbers lives in
[`momentum/config.py`](momentum/config.py), so the rules on the website and the rules in the
backtest cannot drift apart.

## Why the universe is rebuilt rather than downloaded

This is the part that decides whether the result means anything.

Backtesting over *today's* NIFTY 500 quietly deletes every company that fell out of the index
along the way — which is precisely the set that did badly. That single shortcut can add several
points of CAGR to any long-only strategy.

So membership is reconstructed from data instead:

- **Pool**: NIFTY 500 ∪ Total Market 750 ∪ Microcap 250 ∪ the full NSE equity list
  (~2,300 symbols). A company that has since collapsed out of the indices is still in the pool.
- **Membership at date *t***: rank the pool by market cap computed from *that date's* adjusted
  price × *that date's* shares outstanding — a real shares-outstanding time series
  (`yfinance.Ticker.get_shares_full`), not today's share count projected backwards — and take
  the top 500.

This reproduces NSE's primary selection criterion (full market capitalisation) but not its
liquidity screens, cutoff buffers or review calendar, so names at the boundary differ from the
official list. It is far better than a static snapshot and, unlike the official historical
lists, it is reproducible from public data.

## The benchmark that actually tests the rule

Beating the NIFTY 500 is a weak claim in a mid-cap-heavy market: an equal-weight basket of
**randomly chosen** stocks from this universe beat the cap-weighted index most of the time over
the test window. So the study scores the ruleset against a **random-portfolio null** — a few
hundred random 25-stock portfolios drawn from the same eligible names on the same dates — and
reports where the strategy lands in that distribution, in each half of the sample separately.

## Layout

```
momentum/
  config.py      every tunable number, in one place
  data.py        NSE constituent files, adjusted prices, point-in-time share counts (cached)
  universe.py    market-cap reconstruction of index membership
  screen.py      the score and the filters
  backtest.py    monthly rebalance, equal weight, costs, and the random null
  metrics.py     CAGR, drawdown, MAR, Sharpe, Sortino, rolling and percentile stats
scripts/
  fetch_data.py    download and cache everything (~20 min first run, instant after)
  run_backtest.py  the full study -> data/results.json
  make_report.py   -> REPORT.md
  build_site.py    -> docs/index.html (GitHub Pages)
  screen.py        today's ranking, on the command line
docs/            the published site
```

## Running it

```bash
pip install -r requirements.txt

python scripts/fetch_data.py       # caches to data/ ; safe to re-run, incremental
python scripts/run_backtest.py     # the study
python scripts/make_report.py      # REPORT.md
python scripts/build_site.py       # docs/index.html

python scripts/screen.py -n 25     # today's top 25
python scripts/screen.py --date 2024-06-28 -n 10   # or any past date
```

The published GitHub Pages site also has a weekday GitHub Actions refresh at 18:15 IST. It
refreshes the cached price tail, rebuilds the live screen, and republishes the page without
rerunning the full historical study. Run `python scripts/fetch_data.py --refresh-pool` followed
by `python scripts/update_daily.py` for the same local workflow. Every live-screen row includes
the signal/entry date, latest-close entry price, and an illustrative 8% protective stop-loss;
the historical backtest does not model intraday stop execution.

Data comes from NSE's public constituent files and Yahoo Finance. No API key needed.

## Caveats

- **The pool has a floor.** A company delisted outright is in no current NSE file and cannot
  enter the pool at any date. Most survivorship bias is removed; not all of it.
- **One market, one regime.** The window covers a COVID recovery, the 2022 correction and a long
  mid-cap bull run — but no prolonged Indian bear market. Momentum's known failure mode is the
  violent reversal that ends a downtrend, and this window is thin on those.
- **Backtests are not returns.** No live execution, no market impact from trading real size in
  mid caps, no taxes.

---

*Research and education only. Backtested results are hypothetical, contain no live execution,
and are not a recommendation to buy or sell any security.*
