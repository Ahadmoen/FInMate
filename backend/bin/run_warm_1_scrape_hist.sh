#!/bin/bash
# bin/run_warm_1_scrape_hist.sh — Cloud Run Job: finmate-warm-1-scrape-hist.
#
# Subtask 1 of 4 in the daily warm chain.
# Cron: 18:00 PKT daily (parallel with finmate-warm-2-scrape-news).
#
# Pulls historical_data.json from GCS, runs the incremental
# historical_scraper + key_ratios_scraper, uploads the refreshed
# files. Stops here — ML and ingestion are downstream Jobs.
set -euo pipefail
cd /app

stage() {
  echo
  echo "=========================================================="
  echo "[$(date -u +%H:%M:%SZ)] $1"
  echo "=========================================================="
}

stage "0. download active_symbols.json (skip unforecastable tickers)"
python -m ml_services.gcs_sync download-outputs --only=active_symbols.json || true

stage "1. download historical_data.json from GCS"
python -m ml_services.gcs_sync download-historical

stage "2. historical_scraper (incremental, stale-skip enabled)"
python -m integrations.scrapers.historical_scraper

stage "2b. extract last_bars.json (per-ticker last real OHLC for live stubs)"
# Used by finmate-live as the OHLC fallback when PSX intraday endpoint
# returns no data — so live_market_data shows real prior-day OHLC +
# volume instead of a flat last-close stub.
python -m integrations.scrapers.extract_last_bars

stage "3. key_ratios_scraper (TECHNICALS ONLY — fundamentals refreshed quarterly)"
KEY_RATIOS_FUNDAMENTALS=0 python -m integrations.scrapers.key_ratios_scraper

stage "4. upload refreshed JSONs to GCS"
# Only daily_ratios.json + last_bars.json — fundamentals are owned by
# finmate-quarterly-fundamentals.
python -m ml_services.gcs_sync upload-historical
python -m ml_services.gcs_sync upload-outputs --only=daily_ratios.json,last_bars.json

stage "DONE — finmate-warm-1-scrape-hist complete"
