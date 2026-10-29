"""Market data: NSE constituent pool, adjusted prices, and point-in-time shares.

Prices come from yfinance with ``auto_adjust=True`` so they are back-adjusted for
splits and bonuses -- the right basis for return work. Shares outstanding come
from ``Ticker.get_shares_full()``, which is an actual time series, so the market
caps used to reconstruct index membership are point-in-time rather than today's
share count projected backwards.

Everything is cached under ``data/`` so a re-run is instant.
"""
from __future__ import annotations

import csv
import hashlib
import io
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import requests
import yfinance as yf

from .config import DATA, NSE_INDEX_CSVS, EQUITY_LIST_CSV, BENCHMARK, BT

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"}

POOL_CSV = DATA / "pool.csv"
CLOSE_PQ = DATA / "close.pkl"
VOLUME_PQ = DATA / "volume.pkl"
SHARES_PQ = DATA / "shares.pkl"
BENCH_PQ = DATA / "benchmark.pkl"


# --------------------------------------------------------------------------- pool

def build_pool(force: bool = False) -> pd.DataFrame:
    """Union of NIFTY 500 + Total Market 750 + Microcap 250, with NSE industry."""
    if POOL_CSV.exists() and not force:
        return pd.read_csv(POOL_CSV)

    frames = []
    for name, url in NSE_INDEX_CSVS.items():
        text = requests.get(url, headers=UA, timeout=60).text
        df = pd.DataFrame(list(csv.DictReader(io.StringIO(text))))
        df.columns = [c.strip() for c in df.columns]
        df = df.rename(columns={"Company Name": "name", "Industry": "industry",
                                "Symbol": "symbol", "ISIN Code": "isin"})
        df["in_" + name] = True
        frames.append(df[["symbol", "name", "industry", "isin", "in_" + name]])
        print(f"[pool] {name}: {len(df)} names", flush=True)

    pool = frames[0]
    for f in frames[1:]:
        pool = pool.merge(f, on=["symbol", "name", "industry", "isin"], how="outer")
    for c in pool.columns:
        if c.startswith("in_"):
            pool[c] = pool[c].fillna(False)
    pool["symbol"] = pool["symbol"].str.strip()
    # NSE seeds these files with DUMMY* placeholder rows for pending corporate actions.
    pool = pool[~pool["symbol"].str.upper().str.startswith("DUMMY")]
    pool["yf"] = pool["symbol"] + ".NS"
    # Everything else listed on NSE. Index files alone give only today's top 750,
    # so a company that has since fallen below rank 750 -- or out of the indices
    # entirely -- could never enter the universe at any past date. Adding the full
    # equity list lets the market-cap reconstruction put those names back where
    # they actually were.
    try:
        text = requests.get(EQUITY_LIST_CSV, headers=UA, timeout=90).text
        eq = pd.DataFrame(list(csv.DictReader(io.StringIO(text))))
        eq.columns = [c.strip() for c in eq.columns]
        eq = eq[eq["SERIES"].str.strip() == "EQ"]
        eq = eq.rename(columns={"SYMBOL": "symbol", "NAME OF COMPANY": "name",
                                "ISIN NUMBER": "isin", "DATE OF LISTING": "listed"})
        eq["symbol"] = eq["symbol"].str.strip()
        eq["industry"] = "Unclassified"
        extra = eq.loc[~eq["symbol"].isin(pool["symbol"]), ["symbol", "name", "industry", "isin", "listed"]]
        for c in pool.columns:
            if c.startswith("in_"):
                extra[c] = False
        pool = pd.concat([pool, extra], ignore_index=True)
        print(f"[pool] + {len(extra)} other NSE-listed names -> {len(pool)}", flush=True)
    except Exception as exc:                           # noqa: BLE001
        print(f"[pool] could not add full equity list: {exc}", flush=True)

    pool = pool.drop_duplicates("symbol").sort_values("symbol").reset_index(drop=True)
    pool["yf"] = pool["symbol"] + ".NS"
    pool.to_csv(POOL_CSV, index=False)
    print(f"[pool] union = {len(pool)} unique symbols", flush=True)
    return pool


# ------------------------------------------------------------------------- prices

def _download_chunk(tickers: list[str], start: str, end: str, tries: int = 3):
    for attempt in range(tries):
        try:
            df = yf.download(tickers, start=start, end=end, auto_adjust=True,
                             progress=False, threads=True, group_by="column")
            if df is not None and len(df):
                return df
        except Exception as exc:                      # noqa: BLE001 - yfinance is flaky
            print(f"[prices] chunk failed ({exc}); retry {attempt + 1}")
        time.sleep(2 + 3 * attempt)
    return None


def _refresh_tail(close: pd.DataFrame, volume: pd.DataFrame, tickers: list[str],
                  start: str, end: str, chunk: int = 40) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Refresh recent rows for cached tickers without re-downloading history."""
    active = [t for t in tickers if t in close.columns]
    if not active:
        return close, volume

    new_close, new_volume = [], []
    for i in range(0, len(active), chunk):
        batch = active[i:i + chunk]
        df = _download_chunk(batch, start, end)
        if df is None or not isinstance(df.columns, pd.MultiIndex):
            continue
        if "Close" in df.columns.get_level_values(0):
            new_close.append(df["Close"])
        if "Volume" in df.columns.get_level_values(0):
            new_volume.append(df["Volume"])
        print(f"[prices] refreshed {min(i + chunk, len(active))}/{len(active)}", flush=True)

    if new_close:
        fresh = pd.concat(new_close, axis=1)
        close = pd.concat([close, fresh], axis=0)
        close = close[~close.index.duplicated(keep="last")].sort_index()
    if new_volume:
        fresh = pd.concat(new_volume, axis=1)
        volume = pd.concat([volume, fresh], axis=0)
        volume = volume[~volume.index.duplicated(keep="last")].sort_index()
    return close, volume


CHUNKS = DATA / "chunks"
NOPRICE_TXT = DATA / "no_price.txt"


def _known_bad() -> set[str]:
    if NOPRICE_TXT.exists():
        return set(NOPRICE_TXT.read_text().split())
    return set()


def load_prices(tickers: list[str], force: bool = False, chunk: int = 40
                ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (close, volume) panels indexed by date, columns = yahoo tickers.

    Incremental: whatever is already cached is kept and only genuinely new
    tickers are fetched, so widening the universe does not re-download the
    market. Chunk checkpoints are named by content hash rather than position,
    so changing the ticker list can never silently reuse the wrong file.
    Yahoo intermittently drops one or two live tickers per batch, so anything
    still missing at the end is retried individually; names that fail even then
    are remembered in ``data/no_price.txt`` and not retried on later runs.
    """
    if force or not (CLOSE_PQ.exists() and VOLUME_PQ.exists()):
        close, volume = pd.DataFrame(), pd.DataFrame()
    else:
        close, volume = pd.read_pickle(CLOSE_PQ), pd.read_pickle(VOLUME_PQ)

    bad = set() if force else _known_bad()
    need = [t for t in tickers if t not in close.columns and t not in bad]
    if need:
        print(f"[prices] {len(need)} new tickers to fetch "
              f"({close.shape[1]} already cached)", flush=True)

    CHUNKS.mkdir(exist_ok=True)
    parts_c, parts_v = [], []
    for i in range(0, len(need), chunk):
        batch = need[i:i + chunk]
        key = hashlib.md5(("|".join(sorted(batch))).encode()).hexdigest()[:12]
        out = CHUNKS / f"c_{key}.pkl"
        if not out.exists():
            df = _download_chunk(batch, BT.price_start, BT.end)
            if df is None:
                print(f"[prices] batch {i} failed entirely", flush=True)
                continue
            if not isinstance(df.columns, pd.MultiIndex):
                df.columns = pd.MultiIndex.from_product([df.columns, batch])
            keep = [c for c in ("Close", "Volume") if c in df.columns.get_level_values(0)]
            df[keep].to_pickle(out)
        d = pd.read_pickle(out)
        if "Close" in d.columns.get_level_values(0):
            parts_c.append(d["Close"]); parts_v.append(d["Volume"])
        print(f"[prices] {min(i + chunk, len(need))}/{len(need)}", flush=True)

    if parts_c:
        close = pd.concat([close] + parts_c, axis=1)
        volume = pd.concat([volume] + parts_v, axis=1)
    close = close.loc[:, ~close.columns.duplicated()]
    volume = volume.loc[:, ~volume.columns.duplicated()]

    still = [t for t in need if t not in close.columns or close[t].notna().sum() < 250]
    if still:
        print(f"[prices] repairing {len(still)} missing individually", flush=True)
        rc, rv, dead = {}, {}, []
        for n, t in enumerate(still, 1):
            d = _download_chunk([t], BT.price_start, BT.end, tries=2)
            ok = False
            if d is not None and len(d):
                if isinstance(d.columns, pd.MultiIndex):
                    d.columns = d.columns.get_level_values(0)
                if "Close" in d and d["Close"].notna().sum() >= 250:
                    rc[t], rv[t] = d["Close"], d["Volume"]; ok = True
            if not ok:
                dead.append(t)
            if n % 50 == 0:
                print(f"[prices] repair {n}/{len(still)}", flush=True)
        if rc:
            close = pd.concat([close.drop(columns=[c for c in rc if c in close.columns]),
                               pd.DataFrame(rc)], axis=1)
            volume = pd.concat([volume.drop(columns=[c for c in rv if c in volume.columns]),
                                pd.DataFrame(rv)], axis=1)
        NOPRICE_TXT.write_text("\n".join(sorted(_known_bad() | set(dead))))
        print(f"[prices] rescued {len(rc)}/{len(still)}; {len(dead)} have no usable history",
              flush=True)

    close, volume = close.sort_index(), volume.sort_index()

    # Existing caches contain the full historical panel but otherwise stop at
    # the date of the last run. Refresh only a short overlap window so a daily
    # action advances the data without downloading eight years again.
    if len(close.index):
        refresh_start = max(pd.Timestamp(BT.price_start),
                            close.index[-1] - pd.Timedelta(days=7))
        refresh_end = (pd.Timestamp(BT.end) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
        if pd.Timestamp(refresh_end) > close.index[-1]:
            close, volume = _refresh_tail(
                close, volume, tickers,
                refresh_start.strftime("%Y-%m-%d"), refresh_end, chunk=chunk)

    keep = close.notna().sum() > 250
    close, volume = close.loc[:, keep], volume.loc[:, keep.reindex(volume.columns).fillna(False)]
    close.to_pickle(CLOSE_PQ); volume.to_pickle(VOLUME_PQ)
    print(f"[prices] panel {close.shape[1]} symbols x {close.shape[0]} days", flush=True)
    return close, volume


def _assemble() -> tuple[pd.DataFrame, pd.DataFrame]:
    closes, volumes = [], []
    for f in sorted(CHUNKS.glob("c*.pkl")):
        df = pd.read_pickle(f)
        if "Close" in df.columns.get_level_values(0):
            closes.append(df["Close"])
        if "Volume" in df.columns.get_level_values(0):
            volumes.append(df["Volume"])
    close = pd.concat(closes, axis=1) if closes else pd.DataFrame()
    volume = pd.concat(volumes, axis=1) if volumes else pd.DataFrame()
    close = close.loc[:, ~close.columns.duplicated()]
    volume = volume.loc[:, ~volume.columns.duplicated()]
    return close.dropna(axis=1, how="all"), volume


# ------------------------------------------------------------------------- shares

def _shares_one(ticker: str) -> tuple[str, pd.Series | None]:
    for attempt in range(2):
        try:
            s = yf.Ticker(ticker).get_shares_full(start=BT.shares_start)
            if s is not None and len(s):
                s = s[~s.index.duplicated(keep="last")]
                s.index = pd.to_datetime(s.index).tz_localize(None).normalize()
                return ticker, s.groupby(level=0).last()
        except Exception:                              # noqa: BLE001
            time.sleep(1 + attempt)
    return ticker, None


def load_shares(tickers: list[str], force: bool = False, workers: int = 8) -> pd.DataFrame:
    """Point-in-time shares outstanding, daily, forward-filled."""
    have = pd.DataFrame()
    if SHARES_PQ.exists() and not force:
        have = pd.read_pickle(SHARES_PQ)
        tickers = [t for t in tickers if t not in have.columns]
        if not tickers:
            return have
        print(f"[shares] {len(tickers)} new tickers ({have.shape[1]} cached)", flush=True)

    out, missing = {}, []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_shares_one, t): t for t in tickers}
        for n, fut in enumerate(as_completed(futs), 1):
            tk, s = fut.result()
            if s is None:
                missing.append(tk)
            else:
                out[tk] = s
            if n % 50 == 0:
                print(f"[shares] {n}/{len(tickers)} ({len(missing)} missing)", flush=True)

    shares = pd.DataFrame(out).sort_index()
    if len(have):
        shares = pd.concat([have, shares], axis=1)
        shares = shares.loc[:, ~shares.columns.duplicated()].sort_index()
    print(f"[shares] got {shares.shape[1]}/{len(tickers)}; missing {len(missing)}", flush=True)
    shares.to_pickle(SHARES_PQ)
    return shares


# ---------------------------------------------------------------------- benchmark

def load_benchmark(force: bool = False) -> pd.Series:
    if BENCH_PQ.exists() and not force:
        s = pd.read_pickle(BENCH_PQ)["close"]
        if len(s) and pd.Timestamp(BT.end) > s.index[-1]:
            start = max(pd.Timestamp(BT.price_start), s.index[-1] - pd.Timedelta(days=7))
            end = (pd.Timestamp(BT.end) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
            fresh = yf.download(BENCHMARK, start=start.strftime("%Y-%m-%d"), end=end,
                                auto_adjust=True, progress=False)
            if len(fresh):
                fs = fresh["Close"]
                if isinstance(fs, pd.DataFrame):
                    fs = fs.iloc[:, 0]
                s = pd.concat([s, fs])
                s = s[~s.index.duplicated(keep="last")].sort_index()
                s.name = "close"
                s.to_frame().to_pickle(BENCH_PQ)
        return s
    df = yf.download(BENCHMARK, start=BT.price_start,
                     end=(pd.Timestamp(BT.end) + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
                     auto_adjust=True, progress=False)
    s = df["Close"]
    if isinstance(s, pd.DataFrame):
        s = s.iloc[:, 0]
    s.name = "close"
    s.to_frame().to_pickle(BENCH_PQ)
    return s
