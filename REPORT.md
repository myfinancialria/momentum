# NSE Momentum — risk-adjusted momentum screener and backtest

*Generated 2026-09-05. Data cut 2026-09-04. Full interactive report: **https://myfinancialria.github.io/momentum/***

## The rules

```
SCORE   = (return from t-252d to t-21d)  /  (annualised sigma of daily returns, 252d)
          i.e. 12-month momentum skipping the last month, per unit of risk

FILTERS   a name must pass all of these to be ranked
  1. Close > 200-day SMA                            trade only established uptrends
  2. No single-day move > 15% in the lookback       drop news-spike momentum
  3. 20-day average traded value > Rs 5.0 crore    must be exitable
  4. Close > Rs 10.0 and >= 300 bars of history      sanity
  5. Inside the point-in-time top 500 by market cap   the reconstructed NIFTY 500

PORTFOLIO Rank descending, hold the top 25, equal weight
          Rebalance monthly, costs 25.0 bps per side on traded value
```

## Headline result

2018-01-31 to 2026-09-04 (8.59 years), net of costs.

| | CAGR | Total | Max DD | Vol | MAR | Sharpe |
|---|---:|---:|---:|---:|---:|---:|
| Momentum 25 | 21.0% | 413% | -38.1% | 20.5% | 0.55 | 0.73 |
| NIFTY 500 | 10.7% | 140% | -38.3% | 16.9% | 0.28 | 0.28 |

- **Rs 1 grew to Rs 5.13** against Rs 2.40 for the index.
- Worst peak-to-trough loss **-38.1%**, and the longest time spent below a previous high was **704 days** (~1.9 years).
- 62% of months positive; best 14.0%, worst -24.4%.

## The honest benchmark: is this better than luck?

An equal-weight basket of *randomly chosen* stocks from this universe beat the cap-weighted NIFTY 500 most of the time over this window — small and mid caps outran large caps and equal weighting leans into them. So "it beat the index" proves very little. The test that matters is where the ruleset lands inside the distribution of random portfolios drawn from the same eligible names on the same dates.

**What this null does and does not test.** The random portfolios are drawn from names that already passed every filter — above the 200-day average, liquid enough, no spike — and only the *ranking* is randomised. So the percentile below measures what the momentum score adds *on top of* the filters, which is the strict reading. It gives the score no credit for the filters' own contribution. The `Raw 12-1 (no vol divisor)` row in the robustness table is what isolates the volatility divisor specifically.

- 200 random 25-stock portfolios: median CAGR **10.0%**, 5th–95th percentile 6.6% to 13.5%.
- The ruleset's 21.0% sits at the **100th percentile** of that distribution.
- For reference the NIFTY 500 itself returned 10.7% — below the random median, which is the whole point.

### Split sample

The single most useful robustness check: does the edge appear in both halves, or is it one lucky stretch?

| Window | CAGR | Max DD | Random median | Percentile |
|---|---:|---:|---:|---:|
| First half (2018-01-31 → 2022-05-25) | 16.7% | -38.1% | 6.2% | **100th** |
| Second half (2022-05-25 → 2026-09-04) | 25.4% | -30.2% | 13.7% | **100th** |

## Robustness

A result that survives at only one setting is a curve fit. Same rules, one knob moved at a time.

| Variant | CAGR | Total | Max DD | Vol | MAR | Sharpe |
|---|---:|---:|---:|---:|---:|---:|
| Base case (as specified) | 21.0% | 413% | -38.1% | 20.5% | 0.55 | 0.73 |
| Cost 50 bps/side | 18.4% | 328% | -40.0% | 20.5% | 0.46 | 0.61 |
| Cost 100 bps/side | 13.6% | 198% | -43.8% | 20.5% | 0.31 | 0.37 |
| Hold 15 | 23.2% | 499% | -37.0% | 21.7% | 0.63 | 0.79 |
| Hold 40 | 19.2% | 354% | -38.7% | 19.6% | 0.50 | 0.68 |
| Quarterly rebalance | 19.8% | 358% | -36.4% | 20.5% | 0.54 | 0.67 |
| Universe = top 200 | 14.7% | 225% | -38.8% | 19.3% | 0.38 | 0.45 |
| Universe = top 750 | 22.4% | 469% | -38.7% | 21.1% | 0.58 | 0.78 |
| Raw 12-1 (no vol divisor) | 21.2% | 423% | -44.4% | 22.0% | 0.48 | 0.69 |

### What the volatility divisor actually buys

Plain 12-1 momentum with no volatility divisor returns 21.2% against the ruleset's 21.0% — a difference of 0.3% in favour of the raw version. So the divisor is **not** what generates the return.

What it does is cut the drawdown: -38.1% against -44.4%, which moves MAR from 0.48 to 0.55. Dividing by volatility keeps the most violent names out of a 25-stock book, and that shows up in the depth of the hole rather than in the compounding. If you only care about CAGR, this term is not earning its place; if you have to sit through the drawdown, it is.

## Year by year

| Year | Momentum 25 | NIFTY 500 |
|---|---:|---:|
| 2018 | -9.2% | -5.4% |
| 2019 | 7.6% | 7.7% |
| 2020 | 22.9% | 16.7% |
| 2021 | 84.1% | 30.2% |
| 2022 | 4.5% | 3.0% |
| 2023 | 74.8% | 25.8% |
| 2024 | 24.5% | 15.2% |
| 2025 | -11.2% | 6.7% |
| 2026 | 14.9% | -2.6% |

*First and last years are partial.*

## Turnover and cost

- 104 monthly rebalances.
- Average **8.1 of 25 names replaced** each month (35% of the book).
- Total cost charged across the whole backtest: 18.3% of compounded value.
- At 100 bps/side the strategy still returns 13.6%.

## Current ranking

Top 25 as of 2026-09-04. Research output, not advice.

| # | Symbol | Company | Industry | Score | 12m−1m | σ ann. | Rs Close |
|---:|---|---|---|---:|---:|---:|---:|
| 1 | **MTARTECH** | MTAR Technologies Ltd. | Capital Goods | 6.22 | 379% | 61% | 7161.0 |
| 2 | **SANSERA** | Sansera Engineering Ltd. | Automobile and Auto Compon | 4.73 | 191% | 40% | 3782.6 |
| 3 | **ATHERENERG** | Ather Energy Ltd. | Automobile and Auto Compon | 3.85 | 190% | 49% | 1584.0 |
| 4 | **LAURUSLABS** | Laurus Labs Ltd. | Healthcare | 3.76 | 110% | 29% | 1840.0 |
| 5 | **HFCL** | HFCL Ltd. | Telecommunication | 3.73 | 185% | 49% | 231.4 |
| 6 | **RRKABEL** | R R Kabel Ltd. | Capital Goods | 3.35 | 129% | 39% | 2454.1 |
| 7 | **FEDERALBNK** | Federal Bank Ltd. | Financial Services | 3.20 | 83% | 26% | 343.0 |
| 8 | **HAPPYFORGE** | Happy Forgings Limited | Unclassified | 3.03 | 108% | 36% | 2238.5 |
| 9 | **DIACABS** | Diamond Power Infrastructure Ltd. | Capital Goods | 3.01 | 141% | 47% | 331.8 |
| 10 | **ACUTAAS** | Acutaas Chemicals Ltd. | Healthcare | 2.98 | 131% | 44% | 3168.5 |
| 11 | **ADANIENSOL** | Adani Energy Solutions Ltd. | Power | 2.83 | 112% | 40% | 1409.6 |
| 12 | **AETHER** | Aether Industries Ltd. | Chemicals | 2.83 | 110% | 39% | 1625.6 |
| 13 | **SKYGOLD** | SKY GOLD AND DIAMONDS Ltd. | Consumer Durables | 2.83 | 137% | 49% | 781.5 |
| 14 | **SHRIRAMFIN** | Shriram Finance Ltd. | Financial Services | 2.75 | 97% | 35% | 1041.0 |
| 15 | **SONACOMS** | Sona BLW Precision Forgings Ltd. | Automobile and Auto Compon | 2.48 | 77% | 31% | 789.0 |
| 16 | **BHEL** | Bharat Heavy Electricals Ltd. | Capital Goods | 2.47 | 89% | 36% | 431.1 |
| 17 | **KTKBANK** | Karnataka Bank Ltd. | Financial Services | 2.38 | 81% | 34% | 340.1 |
| 18 | **NATIONALUM** | National Aluminium Co. Ltd. | Metals & Mining | 2.24 | 92% | 41% | 374.1 |
| 19 | **ARVIND** | Arvind Ltd. | Textiles | 2.23 | 88% | 40% | 553.0 |
| 20 | **BELRISE** | Belrise Industries Ltd. | Automobile and Auto Compon | 2.03 | 74% | 36% | 236.9 |
| 21 | **SAILIFE** | Sai Life Sciences Ltd. | Healthcare | 2.02 | 67% | 33% | 1584.3 |
| 22 | **ANANDRATHI** | Anand Rathi Wealth Ltd. | Financial Services | 1.97 | 42% | 21% | 2215.9 |
| 23 | **IDEA** | Vodafone Idea Ltd. | Telecommunication | 1.96 | 92% | 47% | 15.0 |
| 24 | **MCX** | Multi Commodity Exchange of India  | Financial Services | 1.89 | 71% | 38% | 3275.4 |
| 25 | **SYRMA** | Syrma SGS Technology Ltd. | Capital Goods | 1.89 | 79% | 42% | 1457.3 |

## Method

**The universe is rebuilt, not assumed.** Running this over *today's* NIFTY 500 would quietly delete every company that fell out of the index along the way — which is exactly the set that did badly — and inflate any long-only result. Instead:

- The candidate pool is the union of NIFTY 500, Total Market 750, Microcap 250 **and the full NSE equity list** — 2294 symbols, of which 1931 have usable price history and 1927 have point-in-time share counts.
- Index membership is rebuilt at every rebalance by ranking that pool on market cap computed from *that date's* price and *that date's* shares outstanding (a real shares-outstanding time series, not today's count projected backwards).
- Prices are split/bonus-adjusted daily closes, 2015-01-01 to 2026-09-04.

**Backtest assumptions.** Signals use data up to and including the rebalance close and the book is assumed established at that same close — one bar of optimism, which the 25.0 bps/side cost assumption is set generously to offset. Costs are charged on traded value at each rebalance and cover brokerage, STT, impact and slippage. No leverage, no shorting, no stop losses, always fully invested.

## Caveats

- **The pool still has a floor.** A company delisted outright is absent from every current NSE file and cannot enter the pool at any date. The reconstruction removes most survivorship bias, not all of it.
- **Reconstructed membership is not official membership.** Market-cap ranking reproduces NSE's primary selection criterion but not its liquidity screens, cutoff buffers or review calendar, so names at the 500 boundary differ from the official list.
- **One market, one regime.** 8.59 years covers a COVID recovery, a 2022 correction and a long mid-cap bull run — but no prolonged Indian bear market. Momentum's known failure mode is the sharp reversal that ends a downtrend, and this window is thin on those.
- **Backtests are not returns.** No live execution, no impact from trading real size in mid caps, no taxes.

## Reproducing

```bash
pip install -r requirements.txt
python scripts/fetch_data.py     # ~20 min, cached
python scripts/run_backtest.py   # writes data/results.json
python scripts/make_report.py    # writes REPORT.md
python scripts/build_site.py     # writes docs/index.html
python scripts/screen.py -n 25   # today's ranking
```

---
*Research and education only. Backtested results are hypothetical, contain no live execution, and are not a recommendation to buy or sell any security.*