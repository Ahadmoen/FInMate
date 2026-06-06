#!/bin/bash
# bin/run_alerts.sh — Cloud Run Job entry for alert dispatch.
#
# Cloud Scheduler triggers the Cloud Run Job 3 times a day (09:00 /
# 12:00 / 18:40 PKT, Mon-Fri) passing the window as the first arg:
#   gcloud run jobs execute finmate-alerts-dispatch \
#     --region=us-central1 --args=PRE_MARKET
#
# The job calls `manage.py dispatch_alerts <window>` which runs all 3
# sub-tasks (top pick → 2 min → digest → 3 min → position alerts)
# sequentially in one process.
set -euo pipefail
cd /app

WINDOW="${1:-${ALERT_WINDOW:-}}"
if [ -z "$WINDOW" ]; then
  echo "ERROR: window arg required (PRE_MARKET / MID_SESSION / POST_MARKET)"
  exit 2
fi

stage() {
  echo
  echo "=========================================================="
  echo "[$(date -u +%H:%M:%SZ)] $1"
  echo "=========================================================="
}

stage "alerts.dispatch_alerts $WINDOW"
exec python manage.py dispatch_alerts "$WINDOW" ${EXTRA_ALERT_ARGS:-}
