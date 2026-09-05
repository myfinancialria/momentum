"""Inject results.json into the page template and write docs/index.html."""
import json, shutil, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from momentum.config import DATA, DOCS

results = DATA / "results.json"
if not results.exists():
    sys.exit("run scripts/run_backtest.py first")

payload = results.read_text()
# The JSON goes inside a <script> tag, so neutralise any sequence that could
# close it early. There is no user-supplied text here, but this is cheap.
payload = payload.replace("</", "<\\/")

tpl = (DOCS / "_template.html").read_text()
(DOCS / "index.html").write_text(tpl.replace("__DATA__", payload))

for name in ("results.json", "current_screen.csv", "equity_curve.csv", "holdings_history.csv"):
    src = DATA / name
    if src.exists():
        shutil.copy(src, DOCS / ("data.json" if name == "results.json" else name))

(DOCS / ".nojekyll").write_text("")
size = (DOCS / "index.html").stat().st_size
print(f"[site] docs/index.html written ({size/1024:.0f} KB)")
