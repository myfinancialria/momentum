"""Central configuration for the momentum screener and backtest.

Every number a reader might want to challenge lives here, so the rules on the
published page and the rules in the backtest cannot drift apart.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DOCS = ROOT / "docs"
DATA.mkdir(exist_ok=True)
DOCS.mkdir(exist_ok=True)

# NSE constituent files. The union of these three is the candidate pool: a name
# that has since fallen out of the NIFTY 500 is almost always still inside Total
# Market 750 or Microcap 250, so the pool captures the dropouts that a
# current-500-only backtest silently deletes.
NSE_INDEX_CSVS = {
    "nifty500": "https://nsearchives.nseindia.com/content/indices/ind_nifty500list.csv",
    "totalmarket": "https://nsearchives.nseindia.com/content/indices/ind_niftytotalmarket_list.csv",
    "microcap250": "https://nsearchives.nseindia.com/content/indices/ind_niftymicrocap250_list.csv",
}

EQUITY_LIST_CSV = "https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv"

BENCHMARK = "^CRSLDX"        # NIFTY 500 total-return-ish price index on Yahoo
BENCHMARK_NAME = "NIFTY 500"

TRADING_DAYS = 252


@dataclass(frozen=True)
class Rules:
    """The screening ruleset: risk-adjusted momentum.

    score = 12-month return skipping the most recent month, divided by
    annualised daily volatility. The skip-month avoids the well-documented
    short-term reversal effect; the vol divisor stops the ranking being
    dominated by a handful of violently volatile names.
    """

    lookback_days: int = 252          # 12 months
    skip_days: int = 21               # skip the most recent month
    vol_days: int = 252               # window for annualised volatility
    sma_days: int = 200               # trend filter
    max_daily_move: float = 0.15      # reject news-spike momentum
    spike_window: int = 252           # window the spike test is applied over
    turnover_days: int = 20
    min_turnover_cr: float = 5.0      # Rs crore, 20-day average traded value
    min_price: float = 10.0
    min_history_days: int = 300       # need enough bars to score at all
    stop_loss_pct: float = 0.08       # illustrative protective stop below entry


@dataclass(frozen=True)
class PortfolioSpec:
    n_hold: int = 25
    rebalance: str = "ME"             # month-end
    weighting: str = "equal"
    cost_bps: float = 25.0            # per side, on traded value
    universe_top_n: int = 500         # point-in-time "NIFTY 500" by market cap


@dataclass(frozen=True)
class Backtest:
    price_start: str = "2015-01-01"
    shares_start: str = "2016-01-01"
    start: str = "2018-01-01"
    # Keep the default moving so unattended daily runs never go stale.
    end: str = field(default_factory=lambda: date.today().isoformat())
    n_random_portfolios: int = 200    # the honest benchmark
    # Keep the random-null comparison reproducible across daily screen refreshes.
    seed: int = 20260905


RULES = Rules()
PORTFOLIO = PortfolioSpec()
BT = Backtest()


def as_dict() -> dict:
    return {"rules": asdict(RULES), "portfolio": asdict(PORTFOLIO), "backtest": asdict(BT)}
