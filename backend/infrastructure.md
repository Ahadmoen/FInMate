# infrastructure.md — production cloud topology

The end-state of the FinMate cloud setup. Reads as the runbook once
deployment is complete. Read alongside [how_works.md](how_works.md) for
the per-stage timeline and [cloud_link.md](cloud_link.md) for every
Console deep-link.

---

## High-level diagram

```
GitHub: Mubashir1920/FinMate-BE                    Friend's Supabase
   │                                                  │
   │ git push                                         ▲
   ▼                                                  │ Django ORM
                                                      │ via DATABASE_URL
GCP project venom-scent-476112                        │
   │                                                  │
   ├── Artifact Registry: finmate/pipeline:latest ◄── built from source
   │                                                  │
   ├── GCS bucket etl_b/                              │
   │     ├── models/lstm/{SYM}.pt                     │
   │     ├── models/directional/{SYM}_{H}d.pkl        │
   │     ├── historical_data.json                     │
   │     └── outputs/*.json                           │
   │                                                  │
   ├── Secret Manager: database-url                   │
   │                                                  │
   ├── Cloud Run Jobs:                                │
   │     ├── finmate-warm-1-scrape-hist  ┐             │
   │     ├── finmate-warm-2-scrape-news  ├─ chained ──►│
   │     ├── finmate-warm-3-ml-fuse      │             │
   │     ├── finmate-warm-4-ingest       ┘             │
   │     ├── finmate-cold ──────────────────► weekly  ─┘
   │     ├── finmate-live ──────────────────► hourly
   │     └── finmate-warm  ─── (single-container fallback, paused)
   │                                ▲
   └── Cloud Scheduler:              │ HTTP POST
         ├── finmate-warm-1-scrape-hist-daily  18:00 PKT
         ├── finmate-warm-2-scrape-news-daily  18:00 PKT (parallel)
         ├── finmate-warm-3-ml-fuse-daily      18:30 PKT
         ├── finmate-warm-4-ingest-daily       18:35 PKT
         ├── finmate-cold-weekly               Sun 02:00 PKT
         └── finmate-live-hourly               Mon-Fri 10-15 PKT
              (all use finmate-scheduler SA with run.invoker)

Website: reads Supabase tables only — never touches GCS or Cloud Run.
```

---

## Cloud Run Jobs — final config

The daily warm pipeline is **split into 4 sub-tasks** (`finmate-warm-1`
through `-4`) that chain in time. Subtasks 1 and 2 run in parallel,
then 3 waits for both, then 4 waits for 3. The single-container
`finmate-warm` Job is kept as a fallback (its scheduler is paused).

| Resource | warm-1-scrape-hist | warm-2-scrape-news | warm-3-ml-fuse | warm-4-ingest | quarterly-fundamentals | finmate-cold | finmate-live |
|---|---|---|---|---|---|---|---|
| Image | `pipeline:latest` | same | same | same | same | same | same |
| Region | us-central1 | same | same | same | same | same | same |
| Service account | `etl-b-147@…` | same | same | same | same | same | same |
| Memory | 4 Gi | 4 Gi | 8 Gi | 1 Gi | 1 Gi | 8 Gi | 1 Gi |
| CPU | 2 | 2 | 4 | 1 | 1 | 4 | 1 |
| Task timeout | 60 min | 90 min | 90 min | 30 min | 60 min | 24 hr | 5 min |
| Entrypoint | `bin/run_warm_1_scrape_hist.sh` | `bin/run_warm_2_scrape_news.sh` | `bin/run_warm_3_ml_fuse.sh` | `bin/run_warm_4_ingest.sh` | `bin/run_quarterly_fundamentals.sh` | `bin/run_cold.sh` | `bin/run_live.sh` |

Common env vars on every Job:
```
GCS_BUCKET = etl_b
DJANGO_SETTINGS_MODULE = config.settings
PYTHONUNBUFFERED = 1
HF_HOME = /app/.hf-cache
DATABASE_URL = (from Secret Manager: database-url:latest)
```

**Why each Job has the memory/CPU it has:**

- **warm-1-scrape-hist (4 Gi)** — downloads 327 MB historical_data.json
  + writes 1-day delta. RAM-backed disk eats ~500 MB; 4 Gi has 3 Gi
  headroom for pandas merges.
- **warm-2-scrape-news (4 Gi)** — downloads news_sentiment.json, runs
  FinBERT sentiment on the new articles (FinBERT eats ~1.5 Gi during
  inference).
- **warm-3-ml-fuse (8 Gi)** — downloads ~3.4 GB models cache to
  RAM-backed disk; needs the headroom.
- **warm-4-ingest (1 Gi)** — only loads two small JSONs (stocks ~2 MB,
  news_sentiment ~10 MB) and runs Django ORM upserts. Tiny.
- **finmate-cold (8 Gi)** — same model download as warm-3, plus heavy
  LSTM training (~500 MB per concurrent symbol).
- **finmate-live (1 Gi)** — `live_scraper` only, no models, no historical.

---

## Cloud Scheduler — final config

| Scheduler | Cron (UTC) | PKT | Target Job | Notes |
|---|---|---|---|---|
| `finmate-warm-1-scrape-hist-daily` | `0 13 * * *` | **18:00 daily** | finmate-warm-1-scrape-hist | parallel with #2 |
| `finmate-warm-2-scrape-news-daily` | `0 13 * * *` | **18:00 daily** | finmate-warm-2-scrape-news | parallel with #1 |
| `finmate-warm-3-ml-fuse-daily` | `30 13 * * *` | **18:30 daily** | finmate-warm-3-ml-fuse | runs after #1 + #2 |
| `finmate-warm-4-ingest-daily` | `35 13 * * *` | **18:35 daily** | finmate-warm-4-ingest | runs after #3 |
| `finmate-quarterly-fundamentals-quarterly` | `0 21 1 1,4,7,10 *` | **02:00 PKT, 1st of Jan/Apr/Jul/Oct** | finmate-quarterly-fundamentals | refreshes EPS/PE/etc. (PSX fundamentals only change on quarterly filings) |
| `finmate-cold-weekly` | `0 21 * * 6` | **02:00 Sunday** | finmate-cold | weekly retrain |
| `finmate-live-hourly` | `0 5,6,7,8,9,10 * * 1-5` | **10:00–15:00 Mon-Fri** | finmate-live | intraday |
| `finmate-warm-daily` *(paused)* | `30 13 * * *` | — | finmate-warm | fallback only |

OAuth SA on all entries: `finmate-scheduler@…` (has `roles/run.invoker`
on every Job).

The 30-min gap between `warm-1`/`warm-2` (18:00) and `warm-3` (18:30)
gives the scrapers time to finish before the ML/fuse Job pulls their
outputs from GCS. The 5-min gap between `warm-3` and `warm-4` gives
fuse time to upload `stocks.json` before ingest pulls it.

Each Scheduler fires an HTTP POST to:
```
https://us-central1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/venom-scent-476112/jobs/<JOB>:run
```
…with OIDC token signed by the `finmate-scheduler` service account,
which has `roles/run.invoker` on the target Job.

---

## IAM — who can do what

| Principal | Role on bucket | Role on secret | Role on Cloud Run Jobs |
|---|---|---|---|
| `etl-b-147@…` (job runtime SA) | Storage Object Admin | Secret Accessor (`database-url`) | — |
| `finmate-scheduler@…` (scheduler invoker SA) | — | — | run.invoker on warm/cold/live |
| Project Owners | inherited | inherited | inherited |
| `allUsers` | **denied** | denied | denied |

---

## GCS bucket layout (final)

```
gs://etl_b/
├── models/                              persistent — cold writes, warm reads
│   ├── lstm/{SYM}.pt                    672 files, ~134 MB
│   └── directional/{SYM}_{H}d.pkl       1 892 files, ~2.95 GB
├── historical_data.json                 ~327 MB, persistent input cache
└── outputs/                             overwritten every run
    ├── stocks.json                      2.3 MB
    ├── forecasting_trend.json           4.4 MB
    ├── news_sentiment.json              ~10–15 MB after 30-day prune
    ├── news_data.json                   33 MB
    ├── stock_forecasts.json             14 MB
    ├── best_models.json                 124 KB
    ├── directional_signals.json         553 KB
    ├── daily_ratios.json                234 KB
    ├── fundamental_ratios.json          191 KB
    └── live_data.json                   varies (intraday)
```

**Lifecycle rules**

- `models/` — auto-delete objects older than 30 days. Cold weekly
  overwrites the same paths so this only kicks in if a snapshot ever gets
  orphaned.
- `outputs/` — no rule (always overwritten by next run).
- `historical_data.json` — no rule (always overwritten by next run).

**Public access prevention** is on. Only `etl-b-147@…` can read/write.

---

## Supabase tables — final schema

| Table | Mode | Schema additions vs initial |
|---|---|---|
| `stock_symbol` | upsert by ticker | (initial) |
| `market_data_cache` | upsert by ticker | + ma20/50/200, rsi14, volatility20d, volume_ratio (0002) + eps (0005) |
| `stock_forecast` | upsert by (ticker, date, model) | (initial) |
| `stock_signal` | **snapshot** (delete-by-ticker, then insert) | + horizon (0003) + dominant_sentiment + contributions (0004) |
| `news_sentiment` | dedup by link, **30-day retention** | (initial) |
| `live_market_data` | upsert by (ticker, date), **drop pre-today on each live run** | (initial) |
| `scrape_run` | append (audit log) | + status enum tweak (integrations 0002) |

Migrations applied to Supabase:

- `core.0001_initial`
- `core.0002_marketdatacache_ma20_marketdatacache_ma200_and_more`
- `core.0003_stocksignal_horizon`
- `core.0004_stocksignal_contributions_and_more`
- `core.0005_marketdatacache_eps`
- `integrations.0001_initial`
- `integrations.0002_alter_scraperun_status`

Verify on the laptop:
```bash
DATABASE_URL=… python manage.py showmigrations core integrations
```

All should show `[X]`.

---

## Daily timeline (PKT)

```
00:00–09:29   nothing scheduled
10:00–15:00   finmate-live fires every hour (Mon-Fri only)
15:30         PSX market close

18:00         finmate-warm-1-scrape-hist  →  fires
              finmate-warm-2-scrape-news  →  fires (parallel)
                ↓  both run independently for ~25-30 min
                ↓  both upload their outputs to GCS

18:30         finmate-warm-3-ml-fuse  →  fires
                ↓  pulls models + scrapers' outputs
                ↓  warm-mode forecasting + directional + stock_health
                ↓  uploads stocks.json + 4 sibling outputs
                ↓  ~5-10 min wall time

18:35         finmate-warm-4-ingest  →  fires
                ↓  downloads stocks.json + news_sentiment.json
                ↓  runs python manage.py load_ml_outputs
                ↓  Supabase refreshed (snapshot mode + 30-day retention)
                ↓  ~1-2 min wall time

  Sunday 02:00  finmate-cold fires (weekly retrain)
                → ~7–10 hr wall time
                → models/* rewritten with fresh weights
                → outputs refreshed identically
                → Supabase ingested at the end (in-process, friend's
                  load_ml_outputs runs inside the cold container)
```

**End-to-end warm latency: ~35-45 min total**, with most of it being
the parallel scrapers. After 18:35 PKT, Supabase shows fresh data.

Every step is idempotent. Re-running any subtask produces the same
Supabase state (snapshot mode for stock_signal; upserts everywhere
else; 30-day retention on news prunes old rows; pre-today live bars
get pruned each live run).

---

## Bootstrapping the GCS bucket (one-time, already done)

```bash
# from laptop, after a successful local cold run:
.venv/bin/python -m ml_services.gcs_sync upload-models      # ~3.4 GB
.venv/bin/python -m ml_services.gcs_sync upload-historical  # ~327 MB
.venv/bin/python -m ml_services.gcs_sync upload-outputs     # ~91 MB
```

Already done on 2026-05-02. Bucket has ~3.5 GB total. Free tier covers
5 GB.

After this, the laptop is no longer required for production. Cloud Run
Jobs download fresh on each invocation, modify, and re-upload.

---

## Health-check routine (5 min daily)

1. **Cloud Run Jobs page** ([link](https://console.cloud.google.com/run/jobs?project=venom-scent-476112)) — sort by Last execution. Anything not "Succeeded" within the last 24 hr is a flag.
2. **Cloud Scheduler page** ([link](https://console.cloud.google.com/cloudscheduler?project=venom-scent-476112)) — Last status column should say "Successfully ran".
3. **Bucket `outputs/`** ([link](https://console.cloud.google.com/storage/browser/etl_b/outputs?project=venom-scent-476112)) — `stocks.json` mtime should be ≤24 hr old; `live_data.json` mtime ≤1 hr during market.
4. **Friend's Supabase dashboard** — most recent `ScrapeRun` row should be `status=SUCCESS`.

Failure path: click into the failing Job → Executions tab → most recent execution → Logs tab. Look for the `[HH:MM:SSZ] STAGE: …` markers from `bin/run_*.sh`.

---

## Recovery cookbook

| Symptom | Fix |
|---|---|
| Cloud Run Job "OOM killed" or "signal terminated" | Bump memory in Cloud Run Job config (already at 8 Gi for warm/cold; if needed go higher) |
| Cloud Run Job timed out | Either runtime issue (check logs for stuck stage) or genuinely needed more time (bump task-timeout) |
| `forecasting --warm` produced predictions for too few symbols | Trigger `finmate-cold` manually to refresh `models/` |
| Supabase shows yesterday's data | Check `Cloud Run Jobs → finmate-warm → Executions` — most recent should be Succeeded; if Failed, read its logs and retry from Console |
| GCS quota exceeded (Class A ops or storage) | Check the lifecycle rule still active on `models/` |
| Image build broken | `gcloud builds submit ...` from laptop with `--config=cloudbuild.yaml` if needed |
| Schema drift (new pipeline field, old DB) | Apply migration manually: `DATABASE_URL=… python manage.py migrate` |

---

## Cost (estimated monthly)

| Item | Estimate |
|---|---|
| Cloud Run — finmate-warm × 30 (~10 min, 2 vCPU, 8 GiB) | ~$2.00 |
| Cloud Run — finmate-cold × 4 (~8 hr, 4 vCPU, 8 GiB) | ~$3.50 |
| Cloud Run — finmate-live × 120 (~3 min, 1 vCPU, 1 GiB) | ~$0.40 |
| GCS storage (3.5 GB) | ~$0.07 |
| GCS Class A ops (~700/mo writes) | ~$0.04 |
| GCS egress (~10 GB/mo, downloads from Cloud Run) | ~$1.20 |
| Cloud Scheduler (3 jobs) | $0 (free tier) |
| Artifact Registry (~1 GB image stored) | ~$0.10 |
| **Total** | **~$7-8 / month** |

Cheap-mode option: keep weekly cold on laptop instead of Cloud Run →
drops to ~$3-4/month.

---

## Cutover from laptop

Once the first daily warm execution succeeds and Supabase reflects fresh
data, the laptop is no longer required. Concretely:

- No `caffeinate` running on laptop
- No `scripts/run_full_cold.sh` cron on laptop
- No local Celery beat invoking `morning_full_fetch`
- Models, JSONs, and pipeline outputs all live in cloud

The laptop only role: editing code + `git push`. Cloud Run picks up the
new image on the next `gcloud builds submit` (or set up Cloud Build
triggers on push if you want full continuous deployment).
