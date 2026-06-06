import json
import os
import random
import threading
import time
import concurrent.futures as cf
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from curl_cffi import requests as cffi_requests

from .symbols import SYMBOLS as _ALL_SYMBOLS

_limit = int(os.environ.get("SCRAPER_LIMIT", "0") or 0)
SYMBOLS = _ALL_SYMBOLS[:_limit] if _limit > 0 else _ALL_SYMBOLS

# SCRAPER_HALF=A|B → fetch only an interleaved half of the tickers, so two
# staggered Cloud Run schedules (5 min apart) each stay under PSX's per-IP
# volume rate-limit. Interleaved ([0::2] / [1::2]) keeps each half balanced
# across the alphabet. Unset → full list (local runs, manual triggers).
_half = os.environ.get("SCRAPER_HALF", "").strip().upper()
if _half in ("A", "B"):
    SYMBOLS = SYMBOLS[0::2] if _half == "A" else SYMBOLS[1::2]

# PSX dps.psx.com.pk hard-limits simultaneous TCP+SSL handshakes from
# datacenter IPs (RemoteDisconnected on every new connection above the
# limit). The fix is two-pronged:
#   1. Per-thread requests.Session() — TCP+SSL handshake happens once
#      per worker, then ~134 requests reuse the same connection. Cuts
#      "new-connection load" from 673 → 5 over a run.
#   2. Small random jitter (50-250ms) between requests within a worker
#      so all 5 workers don't fire bursts at the same instant.
# With session reuse, 5 workers cleanly get ~600/673 live bars in
# ~150-200s, leaving the rest to the historical-stub fallback.
MAX_WORKERS = int(os.environ.get("LIVE_SCRAPER_WORKERS", "5"))
RETRIES = 1
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0 Safari/537.36"
)
_thread_local = threading.local()


def _session() -> cffi_requests.Session:
    """Per-thread curl_cffi Session impersonating Chrome124 TLS fingerprint."""
    s = getattr(_thread_local, "session", None)
    if s is None:
        s = cffi_requests.Session(impersonate="chrome124")
        s.headers.update({"Accept": "application/json"})
        _thread_local.session = s
    return s

TZ = ZoneInfo("Asia/Karachi")
BASE_URL = "https://dps.psx.com.pk/timeseries/int"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
OUTPUT_FILE = DATA_DIR / "live_data.json"
STOCKS_FILE = DATA_DIR / "stocks.json"
LAST_BARS_FILE = DATA_DIR / "last_bars.json"


def fetch_today_ticks(symbol: str) -> pd.DataFrame:
    # Jitter 50-250ms before the request — desyncs concurrent workers
    # so PSX never sees N simultaneous handshakes/requests at the
    # same instant.
    time.sleep(random.uniform(0.05, 0.25))
    sess = _session()
    last_exc: Exception | None = None
    for attempt in range(RETRIES + 1):
        try:
            response = sess.get(f"{BASE_URL}/{symbol}", timeout=30)
            response.raise_for_status()
            payload = response.json()
            if payload.get("status") != 1 or not payload.get("data"):
                return pd.DataFrame()

            df = pd.DataFrame(payload["data"], columns=["ts", "Price", "Volume"])
            df["Datetime"] = pd.to_datetime(df["ts"], unit="s", utc=True).dt.tz_convert(TZ)
            return df.set_index("Datetime").sort_index()[["Price", "Volume"]]
        except Exception as exc:
            last_exc = exc
            if attempt < RETRIES:
                # Drop & rebuild the session — the underlying TCP connection
                # was likely killed by PSX. A fresh handshake is what we
                # need to recover.
                _thread_local.session = None
                sess = _session()
                time.sleep(0.5 + random.uniform(0, 0.5))
    raise last_exc  # type: ignore[misc]


def to_hourly_bars(ticks: pd.DataFrame) -> pd.DataFrame:
    ohlc = ticks["Price"].resample("1h").ohlc()
    volume = ticks["Volume"].resample("1h").sum()
    bars = ohlc.join(volume).dropna(subset=["open"])
    bars.columns = ["Open", "High", "Low", "Close", "Volume"]
    bars.index.name = "Date"
    return bars


def load_stocks_meta() -> tuple[dict, dict]:
    """Return ({ticker: LastClose}, {ticker: technicals_dict}).

    Technicals dict shape (sourced from Ratios.Technicals + Ratios.Fundamentals):
        {RSI14, MA20, MA50, MA200, Volatility20d, VolumeRatio, EPS}

    Re-stamped onto every live row so the frontend sees current
    price + current daily-derived technicals without a second query.
    """
    if not STOCKS_FILE.exists():
        return {}, {}
    try:
        rows = json.loads(STOCKS_FILE.read_text())
    except (ValueError, OSError):
        return {}, {}
    last_close = {}
    technicals = {}
    for r in rows:
        sym = r.get("Symbol")
        if not sym:
            continue
        if r.get("LastClose") is not None:
            last_close[sym] = r["LastClose"]
        tech = r.get("Ratios", {}).get("Technicals", {})
        fund = r.get("Ratios", {}).get("Fundamentals", {})
        technicals[sym] = {
            "RSI14": tech.get("RSI14"),
            "MA20": tech.get("MA20"),
            "MA50": tech.get("MA50"),
            "MA200": tech.get("MA200"),
            "Volatility20d": tech.get("Volatility20d"),
            "VolumeRatio": tech.get("VolumeRatio"),
            "EPS": fund.get("EPS"),
        }
    return last_close, technicals


def load_last_bars_map() -> dict:
    """Map of {ticker: {Open, High, Low, Close, Volume, Date}} from
    last_bars.json — extracted by warm-1 from historical_data.json.
    Used as the OHLC stub when the endpoint returns nothing.
    """
    if not LAST_BARS_FILE.exists():
        return {}
    try:
        return json.loads(LAST_BARS_FILE.read_text())
    except (ValueError, OSError):
        return {}


def _enrich(row: dict, prior_close, technicals: dict | None) -> dict:
    """Attach change_pct + technicals to a bar dict."""
    close = row.get("Close")
    if prior_close not in (None, 0) and close is not None:
        row["ChangePct"] = (float(close) - float(prior_close)) / float(prior_close) * 100.0
    else:
        row["ChangePct"] = None
    if technicals:
        row["RSI14"] = technicals.get("RSI14")
        row["MA20"] = technicals.get("MA20")
        row["MA50"] = technicals.get("MA50")
        row["MA200"] = technicals.get("MA200")
        row["Volatility20d"] = technicals.get("Volatility20d")
        row["VolumeRatio"] = technicals.get("VolumeRatio")
        row["EPS"] = technicals.get("EPS")
    return row


def _real_stub_bar(symbol: str, last_bar: dict, technicals: dict | None) -> pd.DataFrame:
    """One-row bar from a prior trading day: real OHLC + real volume,
    timestamped at last_bar's Date so frontend can detect 'not today'.

    change_pct is computed against last_bar.PriorClose (the close from
    the trading day BEFORE this bar) — produces the real day-over-day
    move on the last actual trading session, not 0. PriorClose absent
    (only one historical bar known) → falls back to None.
    """
    row = {
        "Symbol": symbol,
        "Date": last_bar["Date"],
        "Open": last_bar["Open"],
        "High": last_bar["High"],
        "Low": last_bar["Low"],
        "Close": last_bar["Close"],
        "Volume": last_bar.get("Volume", 0),
    }
    return pd.DataFrame([_enrich(row, last_bar.get("PriorClose"), technicals)])


def _flat_stub_bar(symbol: str, last_close: float, current_hour, technicals: dict | None) -> pd.DataFrame:
    """Last-resort flat stub when neither live data nor last_bars
    is available. Open=High=Low=Close=last_close, Volume=0,
    change_pct=0.
    """
    row = {
        "Symbol": symbol,
        "Date": current_hour,
        "Open": last_close,
        "High": last_close,
        "Low": last_close,
        "Close": last_close,
        "Volume": 0,
    }
    # No prior session close — avoid (close - close) / close → misleading 0%.
    return pd.DataFrame([_enrich(row, None, technicals)])


def collect(
    symbol: str,
    last_close_map: dict,
    last_bars_map: dict,
    technicals_map: dict,
    current_hour,
) -> pd.DataFrame:
    """Return a single-row bar for `symbol`, enriched with change_pct
    + daily technicals.

    Resolution order:
      1. Live PSX endpoint — latest hourly bar of today's session.
         change_pct = vs last_bars.Close (yesterday) when available.
      2. last_bars.json — last real trading day's OHLC + volume.
      3. stocks.json LastClose — flat OHLC with Volume=0.
      4. Skip (nothing known).
    """
    last_bar = last_bars_map.get(symbol)
    last_close = last_close_map.get(symbol)
    technicals = technicals_map.get(symbol)
    try:
        ticks = fetch_today_ticks(symbol)
    except Exception as exc:
        print(f"{symbol}: fetch failed: {exc}")
        ticks = pd.DataFrame()

    if not ticks.empty:
        bars = to_hourly_bars(ticks).reset_index()
        bars.insert(0, "Symbol", symbol)
        latest = bars.iloc[[-1]].copy()
        # prior_close: yesterday's close from last_bars; fall back to
        # stocks.json LastClose; final fallback is None (change_pct=NULL).
        prior_close = (last_bar or {}).get("Close") or last_close
        row = latest.iloc[0].to_dict()
        enriched = _enrich(row, prior_close, technicals)
        print(f"{symbol}: live close={enriched['Close']} change_pct={enriched['ChangePct']}")
        return pd.DataFrame([enriched])

    if last_bar is not None:
        print(f"{symbol}: stub from last_bars (close={last_bar['Close']})")
        return _real_stub_bar(symbol, last_bar, technicals)

    if last_close is not None:
        print(f"{symbol}: flat stub @ last_close={last_close}")
        return _flat_stub_bar(symbol, last_close, current_hour, technicals)

    print(f"{symbol}: no source — skipping")
    return pd.DataFrame()


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    now_pkt = datetime.now(TZ)
    today_pkt = now_pkt.date()
    current_hour = now_pkt.replace(minute=0, second=0, microsecond=0)

    last_close_map, technicals_map = load_stocks_meta()
    last_bars_map = load_last_bars_map()
    print(
        f"PKT today: {today_pkt} | current hour: {current_hour} | "
        f"half: {_half or 'ALL'} | tickers: {len(SYMBOLS)} | last_close: {len(last_close_map)} | "
        f"technicals: {sum(1 for v in technicals_map.values() if v.get('RSI14') is not None)} | "
        f"last_bars: {len(last_bars_map)} | workers: {MAX_WORKERS}"
    )

    frames = []
    started = datetime.now(TZ)
    with cf.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        futures = {
            ex.submit(collect, sym, last_close_map, last_bars_map, technicals_map, current_hour): sym
            for sym in SYMBOLS
        }
        for fut in cf.as_completed(futures):
            try:
                bars = fut.result()
            except Exception as exc:
                print(f"{futures[fut]}: worker raised: {exc}")
                continue
            if not bars.empty:
                frames.append(bars)
    elapsed = (datetime.now(TZ) - started).total_seconds()
    print(f"\nfan-out complete in {elapsed:.1f}s")

    if not frames:
        print("no data to write")
        return

    fresh = pd.concat(frames, ignore_index=True)
    fresh = fresh.drop_duplicates(subset=["Symbol"], keep="last")

    # When running as a half (SCRAPER_HALF=A or B), merge with the existing
    # live_data.json so the other half's tickers are preserved.  Without this,
    # each half-run would overwrite the file with only its ~370 tickers,
    # leaving the DB with half the active symbols.  Fresh rows win on conflict.
    if _half and OUTPUT_FILE.exists():
        try:
            existing = pd.read_json(OUTPUT_FILE)
            other_half = existing[~existing["Symbol"].isin(fresh["Symbol"])]
            combined = pd.concat([other_half, fresh], ignore_index=True)
        except Exception as exc:
            print(f"merge with existing skipped ({exc}); writing fresh only")
            combined = fresh
    else:
        combined = fresh

    combined = combined.sort_values("Symbol").reset_index(drop=True)
    combined.to_json(OUTPUT_FILE, orient="records", date_format="iso", indent=2)

    # Cosmetic summary — wrap in try so a stat-glitch doesn't fail
    # the run after the data is already on disk. Mixed Date types
    # (Timestamp from live, ISO string from last_bars.json) tripped
    # pd.to_datetime on the previous run.
    try:
        with_volume = (combined["Volume"] > 0).sum()
        flat_stub = int((combined["Volume"] == 0).sum())
        print(
            f"saved {len(combined)} rows ({with_volume} with volume + "
            f"{flat_stub} flat-stub) across {combined['Symbol'].nunique()} symbols -> {OUTPUT_FILE}"
        )
    except Exception as exc:
        print(f"summary stats failed (non-fatal): {exc}")
        print(f"saved {len(combined)} rows -> {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
