#!/bin/bash
# bin/run_live.sh — Hourly intraday refresh (Cloud Run Job: finmate-live).
#
# Cron: every hour 10:00-15:00 PKT, Mon-Fri (= 5,6,7,8,9,10 UTC).
#
# Lightweight job: only the live_scraper + Supabase ingestion of
# live_data.json. No models needed. No historical_data.json needed.
# Wall time: ~1-3 minutes.
set -euo pipefail

cd /app

stage() {
  echo
  echo "[$(date -u +%H:%M:%SZ)] $1"
}

stage "1a. download filter + fallback files"
# active_symbols.json : trims SYMBOLS to the ~673 forecasted tickers.
# stocks.json         : LastClose for last-resort flat stub.
# last_bars.json      : per-ticker last real OHLC + volume for the
#                       primary stub (refreshed daily by warm-1).
python -m ml_services.gcs_sync download-outputs \
  --only=active_symbols.json,stocks.json,last_bars.json,live_data.json || true

stage "1. live scraper (snapshot mode — one row per ticker per run)"
python -m integrations.scrapers.live_scraper

stage "2. ingest live_data.json into Supabase (snapshot mode)"
# Use the BULK helper directly. We do NOT call manage.py load_ml_outputs
# here because that command auto-ingests every JSON it finds on disk —
# and we just downloaded stocks.json for the LastClose fallback, which
# would trigger a slow per-row re-ingest of StockSymbol / StockForecast /
# StockSignal and push past the 300s task timeout. _ingest_live_data
# wipes live_market_data and bulk_inserts ~673 rows in <5 sec.
python manage.py shell <<'PY'
from integrations.tasks import _ingest_live_data
n = _ingest_live_data()
print(f'  rows snapshot-inserted: {n}')
PY

stage "3. upload live_data.json to GCS outputs/"
python -m ml_services.gcs_sync upload-outputs

stage "DONE — finmate-live complete"
