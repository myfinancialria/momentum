"""Download and cache everything the backtest needs."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from momentum import data

force = "--force" in sys.argv
try:
    pool = data.build_pool(force=force or "--refresh-pool" in sys.argv)
except Exception as exc:
    if not data.POOL_CSV.exists():
        raise
    print(f"[pool] refresh failed ({exc}); using cached pool", flush=True)
    pool = data.build_pool()
tickers = pool["yf"].tolist()
print(f"pool: {len(tickers)} tickers")

close, volume = data.load_prices(tickers, force=force)
print("prices done", close.shape)

bench = data.load_benchmark(force=force)
print("benchmark done", bench.shape, bench.index.min(), bench.index.max())

# Only bother fetching share counts for names we actually have prices for.
have = [t for t in tickers if t in close.columns]
shares = data.load_shares(have, force="--force" in sys.argv)
print("shares done", shares.shape)
print("ALL DATA READY")
