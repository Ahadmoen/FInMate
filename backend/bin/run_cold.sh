#!/bin/bash
# bin/run_cold.sh — Weekly cold retrain (Cloud Run Job: finmate-cold).
#
# Cron: 02:00 PKT every Sunday.
#
# Same as warm but ML modules retrain from scratch:
#   - forecasting: full ARIMA walk-forward + LSTM training (~6-7 hr)
#   - directional_classifier: full ensemble training (~1 hr)
# Total wall time: ~7-10 hr.
#
# Uploads new model artifacts to GCS at the end so the next warm run
# picks them up. Otherwise identical to run_warm.sh.
set -euo pipefail

cd /app

stage() {
  echo
  echo "=========================================================="
  echo "[$(date -u +%H:%M:%SZ)] $1"
  echo "=========================================================="
}

stage "1. download persistent state from GCS"
python -m ml_services.gcs_sync download-models
python -m ml_services.gcs_sync download-historical

stage "2. scrapers (incremental — failures are non-fatal so a flaky upstream doesn't block retraining)"
# Each scraper failure logs but doesn't abort the pipeline. The ML stage
# uses the most recent on-disk JSONs — a single missed scrape just means
# the model retrains against yesterday's data instead of today's.
python -m integrations.scrapers.historical_scraper || echo "  [warn] historical_scraper failed — continuing with stale historical_data.json"
python -m integrations.scrapers.key_ratios_scraper || echo "  [warn] key_ratios_scraper failed — continuing with stale daily_ratios.json"
python -m integrations.scrapers.news_scraper || echo "  [warn] news_scraper failed (likely upstream 503) — continuing with stale news_data.json"

stage "3. ML — COLD mode (full retrain)"
python -m ml_services.forecasting
python -m ml_services.directional_classifier
python -m ml_services.sentiment

stage "4. fuse → stocks.json"
python -m ml_services.stock_health

stage "5. ingest into Supabase"
python manage.py load_ml_outputs

stage "6. upload models + outputs + historical to GCS"
python -m ml_services.gcs_sync upload-models
python -m ml_services.gcs_sync upload-historical
python -m ml_services.gcs_sync upload-outputs

stage "DONE — finmate-cold complete"
