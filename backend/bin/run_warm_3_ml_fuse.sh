#!/bin/bash
# bin/run_warm_3_ml_fuse.sh — Cloud Run Job: finmate-warm-3-ml-fuse.
#
# Subtask 3 of 4 in the daily warm chain.
# Cron: 18:30 PKT daily (after both scraper subtasks).
#
# Pulls everything ML needs (models, historical, scrapers' outputs),
# runs warm-mode forecasting + directional. FinBERT sentiment is
# already done by subtask 2 (finmate-warm-2-scrape-news). Runs
# stock_health to fuse everything into stocks.json. Uploads ML +
# fuse outputs to GCS.
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

stage "2. download scrapers' outputs + prior cold-run summaries"
# best_models.json + stock_forecasts.json are required for warm mode
# in forecasting.py — without them, warm falls back to cold (~6 hr).
# directional_signals.json is needed by stock_health to fold into the
# Directional block of stocks.json.
python -m ml_services.gcs_sync download-outputs \
  --only=daily_ratios.json,fundamental_ratios.json,news_sentiment.json,news_data.json,best_models.json,stock_forecasts.json,directional_signals.json

stage "3. ML — warm mode (no retraining)"
python -m ml_services.forecasting --warm
python -m ml_services.directional_classifier --warm

stage "4. fuse → stocks.json"
python -m ml_services.stock_health

stage "5. upload ML + fuse outputs to GCS"
python -m ml_services.gcs_sync upload-outputs \
  --only=stocks.json,forecasting_trend.json,best_models.json,directional_signals.json,stock_forecasts.json

stage "DONE — finmate-warm-3-ml-fuse complete"
