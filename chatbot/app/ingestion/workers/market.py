"""Market data ingestion — Supabase live_market_data table.

Structured numeric data (OHLCV, signals, forecasts) lives exclusively in
Supabase and is queried via asyncpg.  This worker does NOT push price data
into Qdrant — that would be architecturally wrong (see ARCHITECTURE.md).

Responsibilities:
  1. Validate freshness of live_market_data per ticker.
  2. Report staleness so /v1/health/freshness can surface it.
  3. (Future) call an external PSX data API to backfill missing rows.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger(__name__)

# A ticker is considered stale after this many seconds since last update
STALE_THRESHOLD_SECONDS = 60 * 60 * 8  # 8 hours (market closes at 15:30 PKT)


async def check_freshness(structured_store) -> list[dict[str, Any]]:
    """Return freshness report for all tickers."""
    rows = await structured_store.get_all_latest_prices()
    now = datetime.now(timezone.utc)
    report = []

    seen_tickers = {r["ticker"] for r in rows}
    settings = get_settings()

    for r in rows:
        ticker = r["ticker"]
        raw_date = r.get("date")
        if raw_date:
            try:
                if isinstance(raw_date, str):
                    last_dt = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
                    if last_dt.tzinfo is None:
                        last_dt = last_dt.replace(tzinfo=timezone.utc)
                else:
                    last_dt = datetime.combine(raw_date, datetime.min.time(), tzinfo=timezone.utc)
                staleness = int((now - last_dt).total_seconds())
            except (ValueError, TypeError):
                staleness = None
                last_dt = None
        else:
            staleness = None
            last_dt = None

        report.append({
            "ticker": ticker,
            "last_updated": last_dt.isoformat() if last_dt else None,
            "staleness_seconds": staleness,
            "is_stale": staleness is not None and staleness > STALE_THRESHOLD_SECONDS,
        })

    # Flag tickers in corpus that have no data at all
    for ticker in settings.psx_tickers:
        if ticker not in seen_tickers:
            report.append({
                "ticker": ticker,
                "last_updated": None,
                "staleness_seconds": None,
                "is_stale": True,
            })

    return sorted(report, key=lambda x: x["ticker"])
