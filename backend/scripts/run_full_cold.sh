#!/bin/bash
# Full cold pipeline run — for the initial 738-symbol training pass.
# Each stage is idempotent; if one fails the rest abort so you can fix
# and resume from the failing stage.
set -euo pipefail
cd "$(dirname "$0")/.."

export PYTHONUNBUFFERED=1
LOG_DIR=integrations/data/pipeline_logs
mkdir -p "$LOG_DIR"
TS=$(date -u +%Y%m%dT%H%M%SZ)

stage() {
  local name=$1
  shift
  echo
  echo "=========================================================="
  echo "[$(date -u +%H:%M:%SZ)] STAGE: $name"
  echo "=========================================================="
  "$@" 2>&1 | tee -a "$LOG_DIR/${TS}_${name}.log"
  echo "[$(date -u +%H:%M:%SZ)] STAGE $name done"
}

stage 1_historical    .venv/bin/python -m integrations.scrapers.historical_scraper
stage 2_key_ratios    .venv/bin/python -m integrations.scrapers.key_ratios_scraper
stage 3_news          .venv/bin/python -m integrations.scrapers.news_scraper
stage 4_sentiment     .venv/bin/python -m ml_services.sentiment
stage 5_forecasting   .venv/bin/python -m ml_services.forecasting
stage 6_directional   .venv/bin/python -m ml_services.directional_classifier
stage 7_stock_health  .venv/bin/python -m ml_services.stock_health

echo
echo "=========================================================="
echo "[$(date -u +%H:%M:%SZ)] PIPELINE COMPLETE"
echo "=========================================================="
df -h /Users/ahadmoeen | tail -1
ls -lh integrations/data/stocks.json
