# FinMate pipeline image — used by every Cloud Run Job
# (finmate-warm, finmate-cold, finmate-live, finmate-monthly).
#
# The container has no built-in entrypoint — Cloud Run Jobs override
# the container command per-Job to point at one of bin/run_*.sh.
FROM python:3.13-slim AS base

# Avoid bytecode + ensure stdout/stderr unbuffered (so Cloud Logging
# sees progress in real time, not in batches at exit).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# System deps we need:
#   - build-essential / python3-dev: psycopg2-binary fallback compile, statsmodels
#   - libpq5 / libpq-dev: psycopg2 runtime + headers
#   - git: pip can install psx-data-reader from git if PyPI mirror is stale
#   - curl: optional, occasionally useful for one-off debug from inside Cloud Run
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        python3-dev \
        libpq5 \
        libpq-dev \
        git \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps in their own layer for max cache hits.
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Pre-download the FinBERT model into the image so the first sentiment
# run inside Cloud Run doesn't need to pull ~440 MB from Hugging Face.
# Network egress to HF is more expensive than the (one-time) image-build
# cost. Set HF_HOME so Cloud Run runs find the cached model.
ENV HF_HOME=/app/.hf-cache
RUN python -c "from transformers import AutoTokenizer, AutoModelForSequenceClassification; \
               AutoTokenizer.from_pretrained('ProsusAI/finbert'); \
               AutoModelForSequenceClassification.from_pretrained('ProsusAI/finbert')" \
    || echo "FinBERT pre-download failed (offline build?); will fetch at runtime"

# Now the application code. Everything in .dockerignore stays out.
COPY . /app

# Make entrypoint scripts executable (in case host filesystem stripped the bit).
RUN chmod +x /app/bin/*.sh

# No HEALTHCHECK / no EXPOSE — this is a Cloud Run *Job* image, not a
# Cloud Run *Service* image. It runs to completion and exits.
