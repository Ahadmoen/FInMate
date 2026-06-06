#!/bin/bash
# bin/run_news_local.sh — LOCAL news backfill (run from laptop, not Cloud Run).
#
# Use case: Google News rate-limits Cloud Run egress IPs, so warm-2
# in production only gets a fraction of expected news. Your laptop's
# residential IP isn't throttled, so running the same scraper from
# here gets the full ~2000-5000 articles. Result is uploaded to GCS
# and the next Cloud Run warm-3/warm-4 will pick it up.
#
# Default: backfill last 30 days. Override with LOOKBACK_DAYS env var.
#
# Prerequisites (one-time setup):
#   1. Python venv:        source .venv/bin/activate
#   2. Deps installed:     pip install -r requirements.txt
#   3. GCS auth:           gcloud auth application-default login
#                          (creates ~/.config/gcloud/application_default_credentials.json)
#   4. GCS bucket access:  must be a member with read+write on gs://etl_b
#
# Usage:
#   bash bin/run_news_local.sh            # 30-day backfill (default)
#   LOOKBACK_DAYS=7 bash bin/run_news_local.sh   # 7-day instead
set -euo pipefail

cd "$(dirname "$0")/.."

# Activate venv if present.
if [ -d ".venv" ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

export NEWS_RECENT_LOOKBACK_DAYS="${LOOKBACK_DAYS:-30}"

stage() {
  echo
  echo "=========================================================="
  echo "[$(date +%H:%M:%S)] $1"
  echo "=========================================================="
}

stage "0. preflight — verify GCS auth"
if [ ! -f "$HOME/.config/gcloud/application_default_credentials.json" ]; then
  echo "ERROR: GCS Application Default Credentials not found."
  echo "Run this once:  gcloud auth application-default login"
  exit 1
fi
echo "  ✓ GCS auth ready"
echo "  Lookback window: $NEWS_RECENT_LOOKBACK_DAYS days"

stage "1. download existing news + active_symbols from GCS (dedup base)"
python -m ml_services.gcs_sync download-outputs \
  --only=news_data.json,news_sentiment.json,active_symbols.json

stage "2. news_scraper — Google News RSS (last $NEWS_RECENT_LOOKBACK_DAYS days, throttled)"
python -m integrations.scrapers.news_scraper

stage "3. sentiment — FinBERT on the new articles"
python -m ml_services.sentiment

stage "4. upload refreshed news files to GCS"
python -m ml_services.gcs_sync upload-outputs \
  --only=news_data.json,news_sentiment.json

stage "DONE — local news backfill complete"
echo
echo "Next: trigger Cloud Run warm-3 + warm-4 to fuse/ingest:"
echo "  gcloud run jobs execute finmate-warm-3-ml-fuse --region=us-central1 --wait"
echo "  gcloud run jobs execute finmate-warm-4-ingest  --region=us-central1 --wait"
