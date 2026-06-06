#!/bin/bash
# bin/run_warm_2_scrape_news.sh — Cloud Run Job: finmate-warm-2-scrape-news.
#
# Subtask 2 of 4 in the daily warm chain.
# Cron: 18:00 PKT daily (parallel with finmate-warm-1-scrape-hist).
#
# News-only path. Doesn't touch models/ or historical_data.json.
# Pulls existing news_data.json (for dedup-by-link) + news_sentiment.json
# (for dedup-by-link in sentiment), runs news_scraper (today/yesterday
# filter), runs sentiment FinBERT, uploads both back.
set -euo pipefail
cd /app

stage() {
  echo
  echo "=========================================================="
  echo "[$(date -u +%H:%M:%SZ)] $1"
  echo "=========================================================="
}

stage "1. download yesterday's news data + sentiment for dedup + active_symbols.json"
python -m ml_services.gcs_sync download-outputs \
  --only=news_data.json,news_sentiment.json,active_symbols.json

stage "2. news_scraper — Google News RSS (today/yesterday only, throttled)"
python -m integrations.scrapers.news_scraper

stage "3. sentiment — FinBERT on the new articles"
python -m ml_services.sentiment

stage "4. upload refreshed news files to GCS"
python -m ml_services.gcs_sync upload-outputs \
  --only=news_data.json,news_sentiment.json

stage "DONE — finmate-warm-2-scrape-news complete"
