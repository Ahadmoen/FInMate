#!/bin/bash
# bin/run_monthly.sh — Cloud Run Job: finmate-monthly.
#
# Cron: 02:00 PKT on the 1st of each month (21:00 UTC last day → use
#       0 21 28-31 * * with a date guard in scheduler, or simpler:
#       0 21 * * 0 last-day-of-month logic; for FYP just first-of-month
#       at 02:00 PKT = 21:00 UTC on the day before).
#
# Refreshes symbols.py from the live PSX listing so new IPOs / listings
# enter the universe before the next daily warm run picks them up.
# Lightweight: ~30s wall time, hits dps.psx.com.pk once. Writes the
# refreshed symbols.py into the running container's filesystem AND
# back to GCS so subsequent runs can read it. Container restarts
# pull the new symbols.py with the image rebuild on next deploy.
set -euo pipefail
cd /app

stage() {
  echo
  echo "=========================================================="
  echo "[$(date -u +%H:%M:%SZ)] $1"
  echo "=========================================================="
}

stage "1. registry_scraper (refresh symbols.py from live PSX listing)"
python -m integrations.scrapers.registry_scraper

stage "2. upload refreshed symbols.py to GCS (so warm jobs see new symbols)"
# symbols.py lives under integrations/scrapers/ — gcs_sync.py handles
# the upload via the 'sources' bucket prefix. Falls back gracefully
# if upload helper isn't wired for sources yet.
python -m ml_services.gcs_sync upload-symbols 2>/dev/null \
  || echo "  (symbols.py upload helper not configured — symbols.py change persists in image only until next deploy)"

stage "3. download historical_data.json (needed for is_active sync)"
python -m ml_services.gcs_sync download-historical

stage "4. sync StockSymbol.is_active from historical_data freshness"
# Tickers whose last close is > STALE_TRAINING_DAYS old get flipped
# to is_active=False so they disappear from the dashboard. The
# threshold matches forecasting/directional/stock_health rules.
python manage.py sync_stock_symbol_active

stage "DONE — finmate-monthly complete"
