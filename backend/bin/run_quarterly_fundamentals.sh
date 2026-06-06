#!/bin/bash
# bin/run_quarterly_fundamentals.sh — Cloud Run Job: finmate-quarterly-fundamentals.
#
# Cron: 02:00 PKT on the 1st of each quarter (Jan/Apr/Jul/Oct).
#
# Refreshes fundamental_ratios.json by hitting PSX dps.psx.com.pk/company/
# for every symbol. ~15-25 min wall time at 738 symbols. Standalone job
# because PSX fundamentals only meaningfully change on quarterly filings;
# fetching them daily was wasted bandwidth + pushed warm-1 over its
# task budget.
#
# Daily warm-1 keeps writing daily_ratios.json (technicals are cheap and
# do change every close); this job ONLY writes fundamental_ratios.json.
# Both files end up in gs://etl_b/outputs/ for warm-3 + warm-4 to pick up.
set -euo pipefail
cd /app

stage() {
  echo
  echo "=========================================================="
  echo "[$(date -u +%H:%M:%SZ)] $1"
  echo "=========================================================="
}

stage "1. key_ratios_scraper (FUNDAMENTALS ONLY)"
KEY_RATIOS_TECHNICALS=0 KEY_RATIOS_FUNDAMENTALS=1 \
  python -m integrations.scrapers.key_ratios_scraper

stage "2. upload fundamental_ratios.json to GCS"
python -m ml_services.gcs_sync upload-outputs --only=fundamental_ratios.json

stage "DONE — finmate-quarterly-fundamentals complete"
