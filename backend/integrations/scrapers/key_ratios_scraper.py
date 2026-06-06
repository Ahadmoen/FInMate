"""Key ratios per symbol — daily technicals from historical OHLCV +
best-effort fundamentals scrape from PSX dps company page.

Outputs:
  integrations/data/daily_ratios.json       — current technical indicators
  integrations/data/fundamental_ratios.json — fundamentals (P/E, EPS, …)

Quarterly / annual ratios from financial reports require PDF extraction
(PSX hosts them as PDFs on the announcements page). Stub
`fetch_report_ratios` is left as the extension point.
"""
import json
import math
import os
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup

from .symbols import SYMBOLS as _ALL_SYMBOLS

_limit = int(os.environ.get("SCRAPER_LIMIT", "0") or 0)
SYMBOLS = _ALL_SYMBOLS[:_limit] if _limit > 0 else _ALL_SYMBOLS

# Technicals are CHEAP (computed locally from historical_data.json) and
# meaningful daily — they reflect today's close. Fundamentals are
# EXPENSIVE (738 PSX HTTP calls, ~15-25 min wall time) and only
# meaningfully change on quarterly filings. Two env gates so daily
# warm-1 can skip fundamentals and a quarterly Job can skip technicals.
INCLUDE_TECHNICALS = os.environ.get("KEY_RATIOS_TECHNICALS", "1") != "0"
INCLUDE_FUNDAMENTALS = os.environ.get("KEY_RATIOS_FUNDAMENTALS", "1") != "0"

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
HISTORICAL_FILE = DATA_DIR / "historical_data.json"
DAILY_OUTPUT = DATA_DIR / "daily_ratios.json"
FUNDAMENTAL_OUTPUT = DATA_DIR / "fundamental_ratios.json"

PSX_COMPANY_URL = "https://dps.psx.com.pk/company/{}"
USER_AGENT = "Mozilla/5.0 (compatible; FinMate-BE/1.0)"
REQUEST_TIMEOUT = 20


# ---------- Technical indicators (computed from price history) ----------

def _rsi(closes: pd.Series, period: int = 14) -> float:
    delta = closes.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)
    val = rsi.iloc[-1]
    return float(val) if not pd.isna(val) else float("nan")


def _safe(value) -> float | None:
    if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
        return None
    return round(float(value), 4)


def compute_technicals(df: pd.DataFrame) -> dict:
    df = df.sort_values("Date").reset_index(drop=True)
    closes = df["Close"].astype(float)
    volume = df["Volume"].astype(float) if "Volume" in df else pd.Series([], dtype=float)
    if len(closes) < 20:
        return {}

    last_close = float(closes.iloc[-1])
    ma20 = closes.rolling(20).mean().iloc[-1]
    ma50 = closes.rolling(50).mean().iloc[-1] if len(closes) >= 50 else float("nan")
    ma200 = closes.rolling(200).mean().iloc[-1] if len(closes) >= 200 else float("nan")
    rsi14 = _rsi(closes, 14)
    vol20 = closes.pct_change().rolling(20).std().iloc[-1]
    annualized_vol = vol20 * np.sqrt(252) if not pd.isna(vol20) else float("nan")

    if len(volume) >= 20:
        vol_ratio = volume.iloc[-1] / max(volume.rolling(20).mean().iloc[-1], 1e-9)
    else:
        vol_ratio = float("nan")

    return {
        "Close": _safe(last_close),
        "MA20": _safe(ma20),
        "MA50": _safe(ma50),
        "MA200": _safe(ma200),
        "RSI14": _safe(rsi14),
        "Volatility20d": _safe(annualized_vol),
        "VolumeRatio": _safe(vol_ratio),
        "PriceVsMA50Pct": _safe((last_close - ma50) / ma50 * 100) if not pd.isna(ma50) else None,
        "PriceVsMA200Pct": _safe((last_close - ma200) / ma200 * 100) if not pd.isna(ma200) else None,
    }


# ---------- Fundamentals (best-effort from PSX dps company page) --------

def _parse_kv_pairs(soup: BeautifulSoup) -> dict:
    """Pull label-value pairs from the assorted layouts PSX uses on the
    company page. Returns lowercase keys for easy lookup."""
    pairs: dict = {}
    for row in soup.select("tr"):
        cells = [c.get_text(" ", strip=True) for c in row.select("th, td")]
        if len(cells) >= 2:
            pairs[cells[0].lower()] = cells[1]
    for item in soup.select(".stats_value, .stats_data, [data-key]"):
        label = item.get("data-key") or item.find_previous(class_="stats_label")
        if isinstance(label, str):
            pairs[label.lower()] = item.get_text(" ", strip=True)
    return pairs


def _to_float(text: str) -> float | None:
    if not text:
        return None
    cleaned = text.replace(",", "").replace("PKR", "").replace("Rs", "").strip()
    cleaned = cleaned.split()[0] if cleaned else cleaned
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def fetch_company_fundamentals(symbol: str) -> dict:
    """Best-effort fetch of P/E, EPS, dividend yield, market cap from the
    PSX dps company page. Returns empty dict on any failure."""
    url = PSX_COMPANY_URL.format(symbol)
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
    except Exception as exc:
        print(f"  {symbol}: fundamentals fetch failed: {exc}")
        return {}

    soup = BeautifulSoup(response.text, "html.parser")
    kv = _parse_kv_pairs(soup)

    def get(*keys: str) -> float | None:
        for k in keys:
            for label, value in kv.items():
                if k in label:
                    parsed = _to_float(value)
                    if parsed is not None:
                        return parsed
        return None

    return {
        "PE": get("p/e", "p / e", "price to earning"),
        "EPS": get("eps", "earnings per share"),
        "DividendYield": get("dividend yield", "div yield"),
        "MarketCap": get("market cap", "market capitalization"),
        "BookValue": get("book value"),
        "FaceValue": get("face value"),
    }


def fetch_report_ratios(symbol: str) -> list:
    """Stub for quarterly/annual ratios from financial reports.

    PSX publishes annual reports + quarterly statements as PDFs at
    https://dps.psx.com.pk/announcements. Production extraction needs
    a PDF parser (pdfplumber / pdfminer.six) plus per-report layout
    handling. Returns [] until that is wired in.
    """
    return []


# ---------- Driver ------------------------------------------------------

def main() -> None:
    import time as _time
    from ml_services import mlflow_utils
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not HISTORICAL_FILE.exists():
        print(f"missing {HISTORICAL_FILE} — run historical_scraper first")
        return

    raw = json.loads(HISTORICAL_FILE.read_text())
    df = pd.DataFrame(raw)
    if df.empty:
        print("historical_data.json is empty")
        return
    df["Date"] = pd.to_datetime(df["Date"])

    daily_rows = []
    fundamental_rows = []
    available = set(df["Symbol"].unique())
    started = _time.time()

    print(f"INCLUDE_TECHNICALS={INCLUDE_TECHNICALS}  INCLUDE_FUNDAMENTALS={INCLUDE_FUNDAMENTALS}")

    scraper_tag = "key_ratios_technicals" if INCLUDE_TECHNICALS and not INCLUDE_FUNDAMENTALS \
        else ("key_ratios_fundamentals" if INCLUDE_FUNDAMENTALS and not INCLUDE_TECHNICALS else "key_ratios_both")

    with mlflow_utils.run("data_quality_v2", run_name=f"{scraper_tag}_{int(started)}",
                          tags={"scraper": scraper_tag, "kind": "scraper_health"}):
        for symbol in SYMBOLS:
            if INCLUDE_TECHNICALS:
                record = {"Symbol": symbol, "Technicals": {}, "Updated": pd.Timestamp.now("UTC").isoformat()}
                if symbol in available:
                    record["Technicals"] = compute_technicals(df[df["Symbol"] == symbol])
                if record["Technicals"]:
                    daily_rows.append(record)
                    print(f"{symbol}: technicals OK")
                else:
                    print(f"{symbol}: skipped technicals (insufficient history)")

            if INCLUDE_FUNDAMENTALS:
                funds = fetch_company_fundamentals(symbol)
                report_rows = fetch_report_ratios(symbol)
                fundamental_rows.append({
                    "Symbol": symbol,
                    "Snapshot": funds,
                    "Reports": report_rows,
                    "Updated": pd.Timestamp.now("UTC").isoformat(),
                })

        if INCLUDE_TECHNICALS:
            DAILY_OUTPUT.write_text(json.dumps(daily_rows, indent=2, default=str))
            print(f"\nwrote {len(daily_rows)} symbols -> {DAILY_OUTPUT}")
        if INCLUDE_FUNDAMENTALS:
            non_empty = sum(1 for r in fundamental_rows if any(r.get("Snapshot", {}).values()))
            if non_empty == 0 and FUNDAMENTAL_OUTPUT.exists():
                # PSX company pages returned empty Snapshots for every symbol
                # (cloud IP blocked). Keep the existing file rather than
                # overwriting it with blank data — EPS/PE from the last
                # successful quarterly run is far better than all-null.
                print(f"fundamentals: all Snapshots empty (cloud IP likely blocked) — "
                      f"keeping existing {FUNDAMENTAL_OUTPUT.name} to preserve EPS")
            else:
                FUNDAMENTAL_OUTPUT.write_text(json.dumps(fundamental_rows, indent=2, default=str))
                print(f"wrote {len(fundamental_rows)} symbols ({non_empty} with data) -> {FUNDAMENTAL_OUTPUT}")

        # Coverage stats: % of SYMBOLS we produced a record for.
        fundamentals_with_data = sum(1 for r in fundamental_rows if r.get("Snapshot")) if INCLUDE_FUNDAMENTALS else 0
        mlflow_utils.log_params({
            "scraper": scraper_tag,
            "symbols_attempted": len(SYMBOLS),
            "include_technicals": int(INCLUDE_TECHNICALS),
            "include_fundamentals": int(INCLUDE_FUNDAMENTALS),
        })
        mlflow_utils.log_metrics({
            "technicals_rows": len(daily_rows),
            "fundamentals_rows": len(fundamental_rows),
            "fundamentals_with_data": fundamentals_with_data,
            "technicals_coverage_pct": (len(daily_rows) / max(1, len(SYMBOLS))) * 100 if INCLUDE_TECHNICALS else 0.0,
            "fundamentals_coverage_pct": (fundamentals_with_data / max(1, len(SYMBOLS))) * 100 if INCLUDE_FUNDAMENTALS else 0.0,
            "duration_sec": _time.time() - started,
        })


if __name__ == "__main__":
    main()
