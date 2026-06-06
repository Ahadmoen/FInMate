#!/bin/bash
# bin/run_api.sh — Cloud Run *Service* entry for the Django REST API.
#
# Unlike the bin/run_*.sh Job scripts (one-shot, run-to-exit), this keeps
# a long-running gunicorn HTTP server alive. Cloud Run injects $PORT
# (8080 by default); gunicorn binds it and serves config.wsgi.
#
# Static files are collected into STATIC_ROOT at build time and served by
# WhiteNoise. We deliberately do NOT run `migrate` here — the database is
# migrated out-of-band, and auto-migrating from this image would clash with
# the differently-named migrations already applied to the prod DB.
set -euo pipefail
cd /app

PORT="${PORT:-8080}"

# Collect static at runtime (not build): settings.py reads DATABASE_URL with
# no default, so manage.py only works once env vars are injected by Cloud Run.
python manage.py collectstatic --noinput || echo "collectstatic skipped (non-fatal)"

exec gunicorn config.wsgi:application \
  --bind "0.0.0.0:${PORT}" \
  --workers "${GUNICORN_WORKERS:-2}" \
  --threads "${GUNICORN_THREADS:-4}" \
  --timeout "${GUNICORN_TIMEOUT:-120}" \
  --access-logfile - \
  --error-logfile -
