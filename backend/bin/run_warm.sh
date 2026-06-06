#!/bin/bash
# bin/run_warm.sh — Daily warm refresh (Cloud Run Job: finmate-warm).
#
# Cron: 18:30 PKT, every day (Mon-Sun).
#
# Pulls the persistent state (models + historical_data) from GCS, runs
# the incremental scrapers + warm-mode ML, ingests the result into
# Supabase, then pushes today's outputs back to GCS.
#
# Idempotent: if the Job is re-triggered the same day, scrapers
# short-circuit (already-fetched dates), ML re-uses cached weights,
# Supabase upserts overwrite. Safe to retry on failure.
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

stage "2. scrapers (incremental — failures are non-fatal so a flaky upstream doesn't block ML)"
# Each scraper failure logs but doesn't abort the pipeline. The ML stage
# uses the most recent on-disk JSONs — a single missed scrape just means
# ML runs against yesterday's data instead of today's.
python -m integrations.scrapers.historical_scraper || echo "  [warn] historical_scraper failed — continuing with stale historical_data.json"
python -m integrations.scrapers.key_ratios_scraper || echo "  [warn] key_ratios_scraper failed — continuing with stale daily_ratios.json"
python -m integrations.scrapers.news_scraper || echo "  [warn] news_scraper failed (likely upstream 503) — continuing with stale news_data.json"

stage "3. ML — warm mode (no retraining)"
python -m ml_services.forecasting --warm
python -m ml_services.directional_classifier --warm
python -m ml_services.sentiment

stage "4. fuse → stocks.json"
python -m ml_services.stock_health

stage "5. ingest into Supabase"
python manage.py load_ml_outputs

stage "6. upload outputs + updated historical to GCS"
python -m ml_services.gcs_sync upload-historical
python -m ml_services.gcs_sync upload-outputs

stage "DONE — finmate-warm complete"
