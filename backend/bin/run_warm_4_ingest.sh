#!/bin/bash
# bin/run_warm_4_ingest.sh — Cloud Run Job: finmate-warm-4-ingest.
#
# Subtask 4 of 4 in the daily warm chain.
# Cron: 18:35 PKT daily (after finmate-warm-3-ml-fuse).
#
# Pulls the freshly-refreshed JSONs from GCS into the container's local
# disk (because friend's load_ml_outputs reads from local paths), then
# runs Django's load_ml_outputs management command to upsert all six
# Supabase tables. No ML, no scrapers, no model files needed —
# absolute lightest container in the chain.
set -euo pipefail
cd /app

stage() {
  echo
  echo "=========================================================="
  echo "[$(date -u +%H:%M:%SZ)] $1"
  echo "=========================================================="
}

stage "1. apply pending Django migrations to Supabase"
# Self-healing schema sync — picks up any new core/migrations/00XX_*.py
# committed since the previous run. Idempotent: if DB is already at HEAD,
# this is a fast no-op.
python manage.py migrate --noinput

stage "2. download outputs from GCS to container disk"
# Bulk ingestion reads:
#   stocks.json              (drives StockSymbol/StockTechnicals/StockForecast/StockSignal)
#   news_sentiment.json      (drives NewsSentiment, with 30-day retention prune)
#   forecasting_trend.json   (drives ForecastTrend — 30-day forward curve per ticker, snapshot mode)
#   live_data.json           (only finmate-live writes this; usually absent here)
python -m ml_services.gcs_sync download-outputs \
  --only=stocks.json,news_sentiment.json,forecasting_trend.json

stage "3. bulk ingest into Supabase via tasks._ingest_*"
# Use the BULK helpers from integrations.tasks instead of the
# load_ml_outputs management command. Same logic, same fields, but
# bulk_create (one DB round-trip per table) instead of update_or_create
# per row — drops ingest from ~22 min to ~30-60 sec at 672-symbol scale.
python manage.py shell <<'PY'
from integrations.tasks import (
    _ingest_stocks,
    _ingest_news_sentiment,
    _ingest_live_data,
    _ingest_forecast_trend,
    _sync_symbols,
)
print('=== _sync_symbols (symbols.py -> StockSymbol) ===')
_sync_symbols()
print('=== _ingest_stocks (stocks.json -> 4 tables, snapshot mode) ===')
n = _ingest_stocks()
print(f'  rows: {n}')
print('=== _ingest_forecast_trend (forecasting_trend.json -> ForecastTrend, snapshot mode) ===')
t = _ingest_forecast_trend()
print(f'  trend rows: {t}')
print('=== _ingest_news_sentiment (with 30-day retention prune) ===')
m = _ingest_news_sentiment()
print(f'  new articles inserted: {m}')
print('=== _ingest_live_data (only if live_data.json present) ===')
k = _ingest_live_data()
print(f'  intraday bars: {k}')
PY

stage "4. upload active_symbols.json to GCS (used by all scrapers next run)"
# _ingest_stocks() wrote integrations/data/active_symbols.json with the
# tickers that produced predictions in stocks.json. Push it to GCS so
# the next finmate-live / finmate-warm-1 / finmate-warm-2 run picks it
# up at module load and skips the ~66 unforecastable PSX tickers.
python -m ml_services.gcs_sync upload-outputs --only=active_symbols.json || true

stage "DONE — finmate-warm-4-ingest complete"
