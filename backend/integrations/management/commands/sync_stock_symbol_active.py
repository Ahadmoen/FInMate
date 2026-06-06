"""Sync StockSymbol.is_active based on freshness of historical data.

Designed for the monthly Cloud Run Job (`finmate-monthly`). Reads
`integrations/data/historical_data.json` (downloaded by gcs_sync just
before this command runs) and for each StockSymbol in the DB:

  - latest historical Date within STALE_DAYS  → is_active = True
  - latest historical Date older than STALE_DAYS → is_active = False
  - no historical data at all                  → is_active = False

The threshold matches what `forecasting.py`, `directional_classifier.py`,
and `stock_health.py` already use (`STALE_TRAINING_DAYS=30`), so a
ticker that gets filtered out of fresh signal generation also flips to
inactive in the dashboard. MODAM (last traded Apr 2024) → False.

Idempotent. Safe to re-run as often as desired.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from django.core.management.base import BaseCommand

from core.models import StockSymbol


HISTORICAL_FILE = Path(__file__).resolve().parents[2] / "integrations" / "data" / "historical_data.json"
STALE_DAYS = int(os.environ.get("STALE_TRAINING_DAYS", "30"))


class Command(BaseCommand):
    help = "Mark StockSymbol.is_active=False for tickers whose latest historical close is >30d old."

    def handle(self, *args, **options) -> None:
        if not HISTORICAL_FILE.exists():
            self.stdout.write(self.style.ERROR(
                f"missing {HISTORICAL_FILE} — run historical_scraper / gcs_sync first"
            ))
            return

        raw = json.loads(HISTORICAL_FILE.read_text())
        latest_by_ticker: dict[str, str] = {}
        for row in raw:
            sym = row.get("Symbol")
            date = row.get("Date")
            if not sym or not date:
                continue
            if date > latest_by_ticker.get(sym, ""):
                latest_by_ticker[sym] = date

        now = datetime.now(timezone.utc)
        activated, deactivated, unchanged_active, unchanged_inactive = 0, 0, 0, 0
        for sym in StockSymbol.objects.all():
            latest_str = latest_by_ticker.get(sym.ticker)
            if not latest_str:
                should_be_active = False
            else:
                try:
                    latest = datetime.fromisoformat(latest_str.replace("Z", "+00:00"))
                    if latest.tzinfo is None:
                        latest = latest.replace(tzinfo=timezone.utc)
                    age_days = (now - latest).days
                    should_be_active = age_days <= STALE_DAYS
                except Exception:
                    continue

            if sym.is_active == should_be_active:
                if should_be_active:
                    unchanged_active += 1
                else:
                    unchanged_inactive += 1
                continue
            sym.is_active = should_be_active
            sym.save(update_fields=["is_active", "updated_at"])
            if should_be_active:
                activated += 1
            else:
                deactivated += 1

        self.stdout.write(self.style.SUCCESS(
            f"is_active sync: +{activated} activated  -{deactivated} deactivated  "
            f"(unchanged: {unchanged_active} active, {unchanged_inactive} inactive)  "
            f"threshold={STALE_DAYS}d"
        ))
