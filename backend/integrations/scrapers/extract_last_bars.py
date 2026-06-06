"""Extract per-ticker last real trading bar from historical_data.json.

Output: integrations/data/last_bars.json — a small (~50-100 KB) map
of {ticker: {Open, High, Low, Close, Volume, Date}} that the live
scraper uses as a stub when the PSX intraday endpoint returns no
data for a ticker. Replaces the previous flat-LastClose fallback
(which produced cosmetic OHLC duplicates and zero-volume rows in
live_market_data) with a real prior-day bar so frontend charts
show natural OHLC ranges.

Run as: `python -m integrations.scrapers.extract_last_bars`.
Invoked by bin/run_warm_1_scrape_hist.sh right after the
historical_scraper run, before the GCS upload.
"""
import json
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
HIST_FILE = DATA_DIR / "historical_data.json"
OUT_FILE = DATA_DIR / "last_bars.json"


def main() -> None:
    if not HIST_FILE.exists():
        print(f"missing {HIST_FILE}, skipping last_bars extraction")
        return

    df = pd.read_json(HIST_FILE)
    df = df.sort_values(["Symbol", "Date"])

    # Take the last 2 bars per ticker — the most recent (T) becomes
    # the stub OHLC, and the one before (T-1) gives PriorClose so the
    # historical-stub path can compute a real day-over-day change_pct
    # instead of always returning 0 (close vs same close).
    last_two = df.groupby("Symbol", as_index=False).tail(2)

    out = {}
    for sym, group in last_two.groupby("Symbol"):
        rows = group.sort_values("Date").to_dict(orient="records")
        last_row = rows[-1]
        prior_close = rows[-2]["Close"] if len(rows) >= 2 else None
        out[sym] = {
            "Open": float(last_row["Open"]),
            "High": float(last_row["High"]),
            "Low": float(last_row["Low"]),
            "Close": float(last_row["Close"]),
            "Volume": int(last_row["Volume"]),
            "Date": pd.Timestamp(last_row["Date"]).isoformat(),
            "PriorClose": float(prior_close) if prior_close is not None else None,
        }

    OUT_FILE.write_text(json.dumps(out, indent=2))
    print(f"wrote {len(out)} last bars -> {OUT_FILE} ({OUT_FILE.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
