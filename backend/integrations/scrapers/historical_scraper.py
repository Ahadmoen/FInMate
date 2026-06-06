"""Historical OHLCV scraper.

By default this is **incremental**: for each symbol it looks up the
latest date already in `historical_data.json` and only fetches
`(latest + 1 day) → today`. A symbol that's already up to date is
skipped entirely. A symbol with no existing data is full-backfilled
from `FULL_BACKFILL_START`.

Pass `--full` to force a full re-backfill from `FULL_BACKFILL_START`
for every symbol (useful after schema changes or when you suspect
stale data).

Robustness:
  - **Per-fetch timeout** via socket.setdefaulttimeout — the underlying
    `psx` library has no request timeout, so a wedged PSX endpoint can
    block indefinitely. The socket-level cap forces a hard fail.
  - **Symbol-level wall-clock budget** via concurrent.futures — even if
    `psx` retries internally we cap total time per symbol.
  - **Periodic checkpointing** — every CHECKPOINT_EVERY symbols we
    write the merged file to disk, so a kill mid-run loses at most the
    most-recent batch (not the whole multi-hour run).
"""
import argparse
import concurrent.futures as cf
import datetime
import json
import os
import socket
from pathlib import Path

import pandas as pd
from psx import stocks

from .symbols import SYMBOLS as _ALL_SYMBOLS

# SCRAPER_LIMIT=20 → run over first 20 symbols only (curated set is at the top).
_limit = int(os.environ.get("SCRAPER_LIMIT", "0") or 0)
SYMBOLS = _ALL_SYMBOLS[:_limit] if _limit > 0 else _ALL_SYMBOLS

FULL_BACKFILL_START = datetime.date(2000, 1, 1)
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT_FILE = DATA_DIR / "historical_data.json"

# Robustness knobs.
SOCKET_TIMEOUT_SEC = float(os.environ.get("HISTORICAL_SOCKET_TIMEOUT", "60"))
SYMBOL_TIMEOUT_SEC = float(os.environ.get("HISTORICAL_SYMBOL_TIMEOUT", "300"))
CHECKPOINT_EVERY = int(os.environ.get("HISTORICAL_CHECKPOINT_EVERY", "25"))
# Daily-warm-only stop-gap: if a symbol's existing latest_date is older
# than MAX_LOOKBACK_DAYS, skip the fetch entirely. PSX is the source of
# truth — if a symbol has been silent for 30+ days it's effectively
# delisted/halted, and probing month-by-month from 2017 to today on
# every daily run is the dominant cost. Pass --full to ignore this cap.
MAX_LOOKBACK_DAYS = int(os.environ.get("HISTORICAL_MAX_LOOKBACK_DAYS", "30"))
# PSX rate-limits by per-IP request volume per rolling window. To keep the
# daily warm run under the cap, pause HISTORICAL_BATCH_PAUSE_SEC after every
# HISTORICAL_BATCH_SIZE actual PSX fetches so the window resets between
# batches. Both default to 0 (disabled) → behaviour unchanged unless set.
HISTORICAL_BATCH_SIZE = int(os.environ.get("HISTORICAL_BATCH_SIZE", "0") or 0)
HISTORICAL_BATCH_PAUSE_SEC = float(os.environ.get("HISTORICAL_BATCH_PAUSE_SEC", "0") or 0)

# Apply socket timeout at module load — guards every TCP read in psx lib.
socket.setdefaulttimeout(SOCKET_TIMEOUT_SEC)


def _fetch_inner(symbol: str, start: datetime.date, end: datetime.date) -> pd.DataFrame:
    """Pure psx.stocks() call, isolated so we can wrap it in a timeout."""
    return stocks(symbol, start=start, end=end)


def fetch_one(symbol: str, start: datetime.date, end: datetime.date) -> pd.DataFrame:
    print(f"\n=== {symbol} ===")
    if start > end:
        print(f"  up to date (latest >= {end})")
        return pd.DataFrame()
    print(f"  fetching {start} → {end}")

    # Run the fetch in a worker thread we can time out on. CRITICAL: do
    # NOT use `with cf.ThreadPoolExecutor(...)` — its __exit__ calls
    # shutdown(wait=True), which blocks on the leaked worker thread and
    # defeats the timeout. Manual shutdown(wait=False) lets the main
    # loop continue; socket.setdefaulttimeout will eventually free the
    # leaked thread. (We accept a small thread leak — bounded because
    # PSX timeouts cap how long any leaked thread can hang.)
    ex = cf.ThreadPoolExecutor(max_workers=1)
    try:
        future = ex.submit(_fetch_inner, symbol, start, end)
        try:
            data = future.result(timeout=SYMBOL_TIMEOUT_SEC)
        except cf.TimeoutError:
            print(f"  TIMEOUT after {SYMBOL_TIMEOUT_SEC}s — abandoning")
            return pd.DataFrame()
        except Exception as exc:
            print(f"  FAILED: {exc}")
            return pd.DataFrame()
    finally:
        # Don't wait for the worker — if the fetch is hung this would
        # block the main loop indefinitely (the bug we just hit).
        ex.shutdown(wait=False, cancel_futures=True)

    if data.empty:
        print("  no rows returned")
        return pd.DataFrame()

    data = data.reset_index()
    data.insert(0, "Symbol", symbol)
    print(
        f"  fetched {len(data)} rows "
        f"({data['Date'].min().date()} to {data['Date'].max().date()})"
    )
    return data


def load_existing(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    raw = json.loads(path.read_text())
    if not raw:
        return pd.DataFrame()
    df = pd.DataFrame(raw)
    df["Date"] = pd.to_datetime(df["Date"])
    return df


def latest_per_symbol(df: pd.DataFrame) -> dict[str, datetime.date]:
    """Map each symbol to its most recent close date in the existing file."""
    if df.empty:
        return {}
    return {
        sym: pd.Timestamp(d).date()
        for sym, d in df.groupby("Symbol")["Date"].max().items()
    }


def merge(existing: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    if existing.empty and new.empty:
        return existing
    combined = pd.concat([existing, new] if not existing.empty else [new], ignore_index=True)
    combined = combined.drop_duplicates(subset=["Symbol", "Date"], keep="last")
    return combined.sort_values(["Symbol", "Date"]).reset_index(drop=True)


def _flush(frames: list, label: str) -> pd.DataFrame:
    """Merge, write to disk, and return the merged frame so the caller can
    reset its `frames` list to just `[merged]` without losing history."""
    if not frames:
        return pd.DataFrame()
    merged = merge(pd.DataFrame(), pd.concat(frames, ignore_index=True))
    merged.to_json(OUTPUT_FILE, orient="records", date_format="iso", indent=2)
    print(
        f"  [{label}] saved {len(merged)} rows across "
        f"{merged['Symbol'].nunique()} symbols -> {OUTPUT_FILE}"
    )
    return merged


def main(full: bool = False) -> None:
    import time as _time
    from ml_services import mlflow_utils
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    started = _time.time()
    existing = load_existing(OUTPUT_FILE)
    latest_by_sym = {} if full else latest_per_symbol(existing)
    end = datetime.date.today()
    stale_cutoff = end - datetime.timedelta(days=MAX_LOOKBACK_DAYS)

    frames = [existing] if not existing.empty else []
    fetched_syms = 0
    skipped_syms = 0
    stale_skipped = 0
    since_checkpoint = 0
    psx_fetches = 0

    with mlflow_utils.run("data_quality_v2", run_name=f"historical_scraper_{int(started)}",
                          tags={"scraper": "historical", "kind": "scraper_health",
                                "mode": "full" if full else "incremental"}):
        for symbol in SYMBOLS:
            latest = latest_by_sym.get(symbol)
            if not full and latest is not None and latest < stale_cutoff:
                stale_skipped += 1
                continue
            start = FULL_BACKFILL_START if latest is None else latest + datetime.timedelta(days=1)
            df = fetch_one(symbol, start, end)
            psx_fetches += 1
            if (HISTORICAL_BATCH_SIZE and HISTORICAL_BATCH_PAUSE_SEC
                    and psx_fetches % HISTORICAL_BATCH_SIZE == 0):
                print(f"  batch pause: {HISTORICAL_BATCH_PAUSE_SEC:.0f}s after "
                      f"{psx_fetches} PSX fetches (let rate-limit window reset)")
                _time.sleep(HISTORICAL_BATCH_PAUSE_SEC)
            if df.empty:
                skipped_syms += 1
                continue
            frames.append(df)
            fetched_syms += 1
            since_checkpoint += 1

            if since_checkpoint >= CHECKPOINT_EVERY:
                merged = _flush(frames, f"checkpoint @ {fetched_syms} fetched")
                frames = [merged] if not merged.empty else []
                since_checkpoint = 0

        if not frames:
            print("no data to write")
            mlflow_utils.log_metrics({
                "duration_sec": _time.time() - started,
                "fetched_symbols": 0,
                "items_total": 0,
            })
            return

        merged_final = _flush(frames, "final")
        mode = "full" if full else "incremental"
        print(
            f"\n[{mode}] fetched {fetched_syms}, "
            f"empty/up-to-date {skipped_syms}, "
            f"stale-skipped {stale_skipped} (latest > {MAX_LOOKBACK_DAYS} days old)"
        )

        # Data-quality summary on the final dataset.
        try:
            total_rows = int(len(merged_final)) if merged_final is not None and not merged_final.empty else 0
            unique_symbols = int(merged_final["Symbol"].nunique()) if total_rows else 0
            date_min = str(merged_final["Date"].min()) if total_rows else None
            date_max = str(merged_final["Date"].max()) if total_rows else None
            nan_close_pct = float(merged_final["Close"].isna().mean() * 100) if total_rows else 0.0
            nan_volume_pct = float(merged_final["Volume"].isna().mean() * 100) if total_rows and "Volume" in merged_final else 0.0
        except Exception:
            total_rows = unique_symbols = 0
            date_min = date_max = None
            nan_close_pct = nan_volume_pct = 0.0

        mlflow_utils.log_params({
            "scraper": "historical",
            "mode": "full" if full else "incremental",
            "symbols_attempted": len(SYMBOLS),
            "max_lookback_days": MAX_LOOKBACK_DAYS,
            "date_min": date_min,
            "date_max": date_max,
        })
        mlflow_utils.log_metrics({
            "fetched_symbols": fetched_syms,
            "skipped_symbols": skipped_syms,
            "stale_skipped_symbols": stale_skipped,
            "total_rows": total_rows,
            "unique_symbols": unique_symbols,
            "coverage_pct": (unique_symbols / max(1, len(SYMBOLS))) * 100,
            "nan_close_pct": nan_close_pct,
            "nan_volume_pct": nan_volume_pct,
            "duration_sec": _time.time() - started,
        })


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--full", action="store_true",
        help="Force full backfill from FULL_BACKFILL_START for every symbol.",
    )
    args = parser.parse_args()
    main(full=args.full)
