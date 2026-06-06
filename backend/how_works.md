# how_works.md — What's done, what runs when, what's in each box

A walkthrough of the FinMate backend post-deployment, from "Cloud Scheduler
fires" to "Supabase has fresh data". Designed to be read top-to-bottom —
each section answers one concrete question about how the system runs.

---

## 1 · What's done so far

Everything below is implemented and committed. Nothing in this section is
"todo".

### Code changes (committed in `bf413dc` and the file-only merge that follows)

| File | What it does |
|---|---|
| `ml_services/forecasting.py` | Cold + **warm** modes. Warm loads cached LSTM, predicts only today's bar. ~30× faster than cold. |
| `ml_services/directional_classifier.py` | Cold + **warm** modes. Warm loads cached ensemble, refreshes only Latest* fields. ~30× faster. Inf/NaN sanitization in `build_features` (was crashing on zero-close symbols). |
| `ml_services/model_cache.py` | Per-symbol artifact persistence — `lstm.pt` and `directional_*.pkl` under `integrations/data/models/{SYM}/`. |
| `ml_services/gcs_sync.py` | Three concerns in one file: upload/download model cache, upload/download `historical_data.json`, upload all output JSONs. CLI subcommands: `upload-models / download-models / upload-historical / download-historical / upload-outputs`. |
| `integrations/scrapers/historical_scraper.py` | Incremental fetch (per-symbol latest+1 → today). 25-symbol checkpointing. Socket + per-symbol timeouts. Executor-leak fix. |
| `integrations/scrapers/news_scraper.py` | 1.2 s throttle between Google News calls + exponential 429 backoff. |
| `Dockerfile` | Python 3.13-slim. Installs requirements.txt. Pre-downloads FinBERT into the image so first sentiment run doesn't need ~440 MB pull. |
| `.dockerignore` | Excludes `.venv/`, `integrations/data/`, credentials, `.git/` etc. — keeps image small (~700 MB). |
| `bin/run_warm_{1..4}_*.sh` | Four warm subtask entrypoints (scrape-hist, scrape-news, ml-fuse, ingest). |
| `bin/run_warm.sh` | Single-container warm fallback. Paused scheduler — kept only for emergencies. |
| `bin/run_cold.sh` | Weekly cold retrain entrypoint. ML modules without `--warm`. |
| `bin/run_live.sh` | Hourly intraday entrypoint. live_scraper → Supabase ingest → upload. |
| `infrastructure.md` | Production cloud topology runbook (Jobs, schedulers, IAM, costs). |
| `warm_mode.md` | How warm/cold modes work locally. |

### Friend's code now in our branch (untouched, just checked-out from `upstream/main`)

| File | What |
|---|---|
| `integrations/tasks.py` | Celery tasks (`morning_full_fetch`, `hourly_refresh`, `run_registry_scraper`) that chain scrapers + ML + ingestion. Used as the *blueprint* for our entrypoint scripts. |
| `integrations/management/commands/load_ml_outputs.py` | Django management command. Reads local JSONs, upserts Supabase. Called once per Cloud Run Job. |
| `core/models.py` + migration | New columns on `MarketDataCache`: `MA20`, `MA50`, `MA200`, `RSI14`, `Volatility20d`, `VolumeRatio`. |
| `integrations/models.py` + migration | `ScrapeRun.status` enum tweak. |
| `config/celery_schedule.py` | Cron schedule for friend's local Celery beat (not used in our cloud architecture). |

### Cold pipeline run (one-time bootstrap, complete)

Ran on the laptop overnight 2026-05-01. Produced:

| Artifact | Count / size | Where it lives |
|---|---|---|
| `historical_data.json` | 327 MB, 2.15 M rows, 726 symbols, 2000-01-01 → 2026-05-01 | local now; will live in `gs://etl_b/` after Phase 4 upload |
| `models/lstm/{SYM}.pt` | 672 files, ~140 MB total | local now; will live in `gs://etl_b/models/lstm/` |
| `models/directional/{SYM}_{1,5,20}d.pkl` | 1,892 files, ~3 GB total | local now; will live in `gs://etl_b/models/directional/` |
| `stocks.json` | 2.3 MB, **672 symbols ranked** | committed to git, will land in `gs://etl_b/outputs/` after first cloud run |
| `forecasting_trend.json` | 4.4 MB, 30-day forward trend per symbol | committed to git |
| `news_sentiment.json` | 36 MB, FinBERT-scored articles | committed to git |
| `directional_signals.json` | 553 KB, 631 symbols × 3 horizons | committed to git |
| `stock_forecasts.json` | 14 MB, 60-day backtest rows | committed to git |
| `best_models.json` | 124 KB, per-symbol MAPE summary | committed to git |
| `daily_ratios.json` | 234 KB, technicals | committed to git |
| `fundamental_ratios.json` | 191 KB, PSX fundamentals | committed to git |

### GCP setup (done)

- GCS bucket `etl_b` created in `us` multi-region (free-tier eligible).
- Lifecycle rule: `models/` prefix auto-deletes after 30 days.
- Service account `etl-b-147@venom-scent-476112.iam.gserviceaccount.com` with **Storage Object Admin** scoped to the bucket.
- Public access prevention enabled.
- Service account JSON key stored at `~/.config/gcloud/finmate-sa.json` (chmod 600, gitignored).
- Connectivity verified — round-trip upload + read + delete on `UBL/lstm.pt`.

---

## 2 · The schedulers

Three (optionally four) **Cloud Scheduler entries**, each triggering one
**Cloud Run Job**. Each Job is a one-shot container — runs to completion,
exits, no idle cost.

```
Cloud Scheduler                        Cloud Run Job                    Wall time
────────────────                       ──────────────                   ────────
finmate-warm-daily        18:30 PKT    →  finmate-warm                  ~7-15 min
  cron "30 13 * * *"      every day                                       (every day)

finmate-cold-weekly       02:00 PKT    →  finmate-cold                  ~7-10 hr
  cron "0 21 * * 6"       Sunday only                                     (weekly)

finmate-live-hourly       10:00-15:00  →  finmate-live                  ~1-3 min
  cron "0 5,6,7,8,9,10    Mon-Fri,                                        (6× per
       * * 1-5"           market hours                                     trading day)

finmate-monthly  (opt)    02:00 PKT    →  finmate-monthly (reuses       ~5 min
  cron "0 21 1 * *"       1st of month     warm image, different             (monthly)
                                           entrypoint)
```

### What each Job does

#### `finmate-warm` — daily refresh

Runs `bin/run_warm.sh`. Six stages:

1. **Download persistent state from GCS** — `models/` (~140 MB LSTM + 3 GB ensembles total, but skipped if local cache matches by size — typically ~0 bytes transferred after the first run) and `historical_data.json` (~327 MB, ~30 sec).
2. **Scrapers (incremental)** — `historical_scraper` fetches today's bars only (per-symbol latest+1→today, ~2 min for 738 symbols), `key_ratios_scraper` recomputes technicals + fetches PSX fundamentals (~20 min if first time, ~5 min subsequent), `news_scraper` pulls today's headlines with 1.2 s throttle (~25-30 min for 738 symbols + general queries).
3. **ML — warm mode** — `forecasting --warm` (~10 sec for 672 symbols), `directional_classifier --warm` (~5 sec), `sentiment` (FinBERT, scales with article count, ~5-15 min).
4. **Fuse** — `stock_health.py` reads everything, writes `stocks.json` (~5 sec for 672 symbols).
5. **Ingest into Supabase** — `python manage.py load_ml_outputs` (friend's command). Reads local JSONs, upserts: `StockSymbol`, `MarketDataCache`, `StockForecast`, `NewsSentiment`, `LiveMarketData`, **appends** `StockSignal`. ~30-60 sec for 672 symbols.
6. **Upload to GCS** — `historical_data.json` (overwrites), `outputs/*.json` (overwrites all 10 outputs).

Total wall: **~45-60 min on first run**, **~10-15 min on subsequent days** (key_ratios doesn't re-fetch unchanged fundamentals; news scraper still needs ~25 min throttled).

#### `finmate-cold` — weekly retrain

Runs `bin/run_cold.sh`. Identical to warm except:

- Step 3 runs `forecasting` and `directional_classifier` **without `--warm`** → full retraining of ~672 LSTMs (~6-7 hr) and ~1,892 ensemble pickles (~1 hr).
- Step 6 also calls `gcs_sync upload-models` to push the freshly retrained models to GCS, so the next warm run picks them up.

Total wall: **~7-10 hr**.

#### `finmate-live` — intraday hourly bars

Runs `bin/run_live.sh`. Three stages:

1. **Live scraper** — `live_scraper.py` pulls today's hourly OHLCV bars from PSX intraday API for all 738 symbols. Skips symbols whose session date is stale.
2. **Ingest** — `python manage.py load_ml_outputs`. Friend's `_load_live_data()` reads `live_data.json`, upserts `LiveMarketData` table, and updates the price fields on `MarketDataCache` (so the website's homepage shows current price and intraday high/low/volume).
3. **Upload** — `live_data.json` to `gs://etl_b/outputs/live_data.json`.

Total wall: **~1-3 min**. Cheap enough to run every hour during market hours.

---

## 3 · What's happening — daily timeline (PKT)

A typical Monday looks like this:

```
00:00–09:29   nothing scheduled (overnight quiet)

10:00         finmate-live  fires            (LiveMarketData updated)
11:00         finmate-live  fires
12:00         finmate-live  fires
13:00         finmate-live  fires
14:00         finmate-live  fires
15:00         finmate-live  fires            (last intraday bar of the day)
15:30         PSX market close (informational)

18:30         finmate-warm  fires            (StockSignal, StockForecast,
              ─ runs the full daily pipeline   MarketDataCache, NewsSentiment
              ─ ~10-15 min                     all refreshed to today's data)
              ─ overwrites GCS outputs/
              ─ overwrites Supabase rows

  Sundays 02:00:
                finmate-cold  fires          (models retrained,
                ─ ~7-10 hr                     Best_MAPE / hit rates updated)
                ─ uploads new models/

  1st of month 02:00 (optional):
                finmate-monthly  fires       (symbols.py refreshed from PSX,
                                              new listings get StockSymbol rows)

23:59         day rolls
```

Saturdays and Sundays the live-hourly cron is disabled (the `1-5` in the
day-of-week field). Sundays still run finmate-warm at 18:30 — the daily
refresh runs even though there's no new market data; it picks up
overnight news sentiment and re-stamps `StockSignal.valid_until`.

---

## 4 · Inside one warm run — chronological

Concrete sequence of what happens between 18:30:00 and the container exit
on a typical Tuesday.

```
18:30:00  Cloud Scheduler hits the Cloud Run Job HTTP trigger
18:30:01  Cloud Run pulls finmate/pipeline:latest from Artifact Registry
18:30:03  Container starts; ENTRYPOINT bin/run_warm.sh kicks off
18:30:04  STAGE 1 — gcs_sync download-models
18:30:07     (1 800 blobs already cached from yesterday's run on the same
              container disk? No — Cloud Run Jobs have ephemeral disks.
              Container starts fresh every time, so all 1 800 blobs
              transfer. 8-thread pool, ~30 sec for 3 GB.)
18:30:37  STAGE 1 — gcs_sync download-historical
18:30:40     (~30 sec to pull 327 MB)
18:31:10  STAGE 2 — historical_scraper
18:31:11     reads historical_data.json, finds latest=2026-05-04 per symbol
18:31:12     for each of 738 symbols, fetches PSX for 2026-05-05
18:33:00     done; merged + dedup + saved (1-day delta added)
18:33:01  STAGE 2 — key_ratios_scraper
18:38:00     done (recomputes technicals; fetches updated fundamentals
              for ~50 symbols whose PSX page changed)
18:38:01  STAGE 2 — news_scraper
              ~25-30 min for 738 symbols at 1.2s throttle plus some 429 backoff
19:08:00     done
19:08:01  STAGE 3 — forecasting --warm
19:08:11     loaded 672 cached LSTMs, predicted today's bar for each, saved
19:08:12  STAGE 3 — directional_classifier --warm
19:08:17     loaded 1 892 cached ensembles, refreshed Latest* per horizon
19:08:18  STAGE 3 — sentiment
19:13:00     ~5 min FinBERT scoring on today's articles
19:13:01  STAGE 4 — stock_health
19:13:06     fused → stocks.json (672 rows)
19:13:07  STAGE 5 — load_ml_outputs (friend's command)
19:13:35     upserts StockSymbol, MarketDataCache, StockForecast (via
              update_or_create), appends StockSignal, dedup-inserts
              NewsSentiment, upserts LiveMarketData (which is empty
              today since live_data.json wasn't written this run)
19:13:36  STAGE 6 — gcs_sync upload-historical
19:14:05     ~30 sec to push 327 MB back
19:14:06  STAGE 6 — gcs_sync upload-outputs
19:14:13     all 10 small outputs uploaded
19:14:14  Container exits, all local files vanish
```

Total: ~44 minutes. Most of that is news scraping (~30 min) — that's the
floor with throttling enabled. Cloud Run charges only for what runs, so
this is ~4 vCPU × 44 min × $0.000018 per vCPU-sec ≈ **$0.05 per warm run**.

---

## 5 · GCS bucket layout (final)

```
gs://etl_b/                              ← bucket
│
├── models/                              ← persistent across runs;
│   ├── lstm/                              cold writes, warm reads
│   │   ├── UBL.pt
│   │   ├── FFC.pt
│   │   └── … (672 files, ~140 MB)
│   └── directional/
│       ├── UBL_1d.pkl
│       ├── UBL_5d.pkl
│       ├── UBL_20d.pkl
│       └── … (1 892 files, ~3 GB)
│
├── historical_data.json                 ← persistent across runs;
│                                          downloaded at start, scrapers
│                                          append today's bars, uploaded
│                                          at end. Grows ~110 KB/day.
│                                          ~327 MB now, ~530 MB in 5 yr.
│
└── outputs/                             ← overwritten every run
    ├── stocks.json                        (672 ranked symbols, fused signal)
    ├── forecasting_trend.json             (30-day forward ARIMA per symbol)
    ├── news_sentiment.json                (FinBERT-scored articles)
    ├── news_data.json                     (raw news articles, pre-sentiment)
    ├── stock_forecasts.json               (60-day backtest, prediction vs actual)
    ├── best_models.json                   (per-symbol MAPE + winner)
    ├── directional_signals.json           (per-symbol, per-horizon hit rates + latest call)
    ├── daily_ratios.json                  (technicals per symbol)
    ├── fundamental_ratios.json            (PSX fundamentals snapshot)
    └── live_data.json                     (intraday hourly bars; only finmate-live writes this)
```

**Lifecycle rule:** objects under `models/` auto-delete after 30 days.
This is purely defensive — daily warm runs never touch `models/`, weekly
cold overwrites the same paths, so models effectively never go stale.
The rule just guarantees no orphaned snapshots if something weird
happens.

`outputs/` and `historical_data.json` have **no lifecycle rule** — they're
overwritten on each run; one copy of each always present.

---

## 6 · Supabase tables and dedup

Friend's `load_ml_outputs` and `_ingest_*()` helpers map our JSONs into
six Supabase tables. Each row of `stocks.json` produces 4 rows across 4
tables; `news_sentiment.json` rows go to one table.

| Supabase table | Source JSON | Mode | Why no duplicates |
|---|---|---|---|
| `StockSymbol` | `stocks.json` + `symbols.py` | upsert by `ticker` | deterministic key |
| `MarketDataCache` | `stocks.json` Ratios.Technicals + LastClose | upsert by `ticker` | one row per ticker, always overwritten |
| `StockForecast` | `stocks.json` Forecast block | upsert by (`ticker`, `forecast_date`, `model_used`) | composite key prevents double-insert per day |
| `StockSignal` | `stocks.json` Health block | **append-only** | every run creates a new row, but each carries `valid_until = next 06:00 PKT`. Website queries the most recent unexpired row → users always see the freshest signal. Multiple signals for the same day are *intentional* (history audit trail, friend's design). |
| `NewsSentiment` | `news_sentiment.json` | dedup by `link` | already-stored URLs skipped |
| `LiveMarketData` | `live_data.json` | upsert by (`ticker`, `date`) | composite key — same hour bar overwrites |

**Net behavior:** every run produces "today's snapshot" in the upsert
tables; `StockSignal` keeps history but only the latest is user-facing
because of `valid_until`. There is **no duplicate-row pollution risk**
on user-facing reads.

---

## 7 · How recovery works if something breaks

| Symptom | Likely cause | Action |
|---|---|---|
| Cloud Run Job ran but Supabase shows yesterday's data | `_ingest_*()` failed silently | Check Cloud Run logs (Console → Cloud Run → Jobs → Executions); friend's `ScrapeRun` table also records `status=FAILED` and the exception message |
| Cloud Run Job timed out before completing | Long news_scraper or a hung PSX request | Re-trigger from Console (the Job is idempotent — scrapers short-circuit dates already fetched, ML reuses cached weights, Supabase upserts overwrite) |
| `forecasting --warm` produced predictions for 19 symbols only | Models not in GCS, or cache out of date | Run `finmate-cold` Job manually; once it uploads new `models/`, next warm run picks them up |
| `historical_data.json` corrupted | Mid-run kill before upload finished | Each run downloads from GCS; the broken local copy doesn't matter. If the GCS copy itself is broken, run `historical_scraper --full` once locally and `gcs_sync upload-historical` to refresh |
| Disk full mid-run | Container disk too small | Increase Cloud Run Job memory (which sets the disk size proportionally); 8 GB → ~60 GB disk |
| Image build fails | Likely a transformers/torch version pin | Test locally with `docker build .`; check Cloud Build logs |

**Manual re-trigger** is always safe — every step is idempotent.

---

## 8 · Cost (real numbers)

Monthly, assuming 30 daily warm runs + 4 cold runs + ~120 live runs:

| Item | Computation | Cost |
|---|---|---|
| Cloud Run Job — finmate-warm | 30 × ~45 min × ~4 vCPU × $0.000018 | ~$1.50 |
| Cloud Run Job — finmate-cold | 4 × ~8 hr × ~4 vCPU × $0.000018 | ~$3.50 |
| Cloud Run Job — finmate-live | 120 × ~3 min × ~1 vCPU × $0.000018 | ~$0.40 |
| GCS storage | 3.5 GB × $0.020/GB-mo | ~$0.07 |
| GCS Class A ops | ~700/mo (writes) | ~$0.04 |
| GCS egress | ~10 GB/mo (Cloud Run downloads ~330 MB/run) | ~$1.20 |
| Cloud Scheduler | 3 jobs free | $0 |
| Artifact Registry | 0.5 GB free, image is ~700 MB | ~$0.05 |
| **Total** | | **~$7-8 / month** |

Cheap-mode option: keep `finmate-cold` running on the laptop instead of
Cloud Run → drops to **~$3/month**.

---

## 9 · Phases — where we are and what's left

| Phase | Description | Status |
|---|---|---|
| 0 | Laptop bootstrap cold run (672 symbols, all artifacts) | ✅ done |
| 1 | Pull friend's `tasks.py` into our branch (file-only, no merge) | ✅ done |
| 2 | Create GCS bucket `etl_b` + service account + lifecycle rule | ✅ done |
| 3 | `gcs_sync.py` extended to all outputs + historical_data | ✅ done |
| 4 | Bootstrap GCS — upload current `models/` + `historical_data.json` from laptop | ⏳ next |
| 5 | `Dockerfile`, `bin/run_*.sh`, `.dockerignore` | ✅ done (just now) |
| 6 | Build + push image: `gcloud builds submit --tag us-central1-docker.pkg.dev/<project>/finmate/pipeline:latest` | ⏳ |
| 7 | Create Cloud Run Job `finmate-warm` (4 GB / 2 vCPU / 60 min) | ⏳ |
| 8 | Create Cloud Run Job `finmate-cold` (8 GB / 4 vCPU / 24 hr) | ⏳ |
| 9 | Create Cloud Run Job `finmate-live` (1 GB / 1 vCPU / 5 min) | ⏳ |
| 10 | Cloud Scheduler entries (3 cron triggers) | ⏳ |
| 11 | Manual trigger of `finmate-warm` once to verify Supabase populates | ⏳ |
| 12 | Cutover — disable any laptop crons; the cloud is now authoritative | ⏳ |

After Phase 12, the laptop is unused for production. Open it only to
push code; Cloud Run does the rest.

---

## 10 · Env vars Cloud Run Jobs need

Set on each Job (Console → Cloud Run → Jobs → edit → Variables & Secrets):

```
GCS_BUCKET                    = etl_b
PYTHONUNBUFFERED              = 1
DJANGO_SETTINGS_MODULE        = config.settings
GOOGLE_APPLICATION_CREDENTIALS = (auto-set when SA is attached, no need
                                  to set this manually)
SUPABASE_URL                  = (Secret Manager reference — friend supplies)
SUPABASE_KEY                  = (Secret Manager reference — friend supplies,
                                  service-role key)
DATABASE_URL                  = (Secret Manager reference — friend supplies,
                                  Supabase Postgres connection string)
HF_HOME                       = /app/.hf-cache  (FinBERT cache from image build)
```

Service account on each Job: `etl-b-147@venom-scent-476112.iam.gserviceaccount.com`.

---

## 11 · Where to find things in the Cloud Console

Project: **`venom-scent-476112`**. Every link below assumes you're
signed in to that project in the Console.

### GCS bucket — see what the pipeline produced

| What you want to inspect | Click here |
|---|---|
| Bucket overview (browse folders) | [console.cloud.google.com/storage/browser/etl_b](https://console.cloud.google.com/storage/browser/etl_b?project=venom-scent-476112) |
| `outputs/` folder — every JSON the latest run produced | [console.cloud.google.com/storage/browser/etl_b/outputs](https://console.cloud.google.com/storage/browser/etl_b/outputs?project=venom-scent-476112) |
| `models/lstm/` — per-symbol LSTM weights | [console.cloud.google.com/storage/browser/etl_b/models/lstm](https://console.cloud.google.com/storage/browser/etl_b/models/lstm?project=venom-scent-476112) |
| `models/directional/` — per-symbol directional ensembles | [console.cloud.google.com/storage/browser/etl_b/models/directional](https://console.cloud.google.com/storage/browser/etl_b/models/directional?project=venom-scent-476112) |
| `historical_data.json` — bucket root, persistent input | bucket overview link above; file is at the root |
| Bucket Permissions — who can read/write | bucket → **Permissions** tab |
| Lifecycle rules — auto-delete config | bucket → **Lifecycle** tab |
| Object versioning, soft delete | bucket → **Protection** tab |

To download any file from the Console: click the file → **Download**.
To preview a JSON in the browser: click → **Authenticated URL** (only works for principals with read access).

### Cloud Run Jobs — see what the schedulers ran

| What | Where |
|---|---|
| All Cloud Run Jobs in the project | [console.cloud.google.com/run/jobs](https://console.cloud.google.com/run/jobs?project=venom-scent-476112) |
| `finmate-warm` Job — daily refresh | filter by name `finmate-warm` on the Jobs page |
| `finmate-cold` Job — weekly retrain | filter by `finmate-cold` |
| `finmate-live` Job — hourly intraday | filter by `finmate-live` |
| Per-Job execution history | click the Job → **Executions** tab. Each execution shows duration, status, and a link to its Cloud Logging entries. |
| Per-execution logs (the stage-by-stage `[HH:MM:SSZ] STAGE: …` lines from `bin/run_*.sh`) | click an execution → **Logs** tab |
| Manual re-trigger | click the Job → **Execute** button (top-right) |
| Edit env vars / SA / memory / timeout | click the Job → **Edit** → save creates a new revision |

### Cloud Scheduler — see and modify the cron triggers

| What | Where |
|---|---|
| All Scheduler jobs | [console.cloud.google.com/cloudscheduler](https://console.cloud.google.com/cloudscheduler?project=venom-scent-476112) |
| `finmate-warm-daily` — `30 13 * * *` (18:30 PKT) | row by name |
| `finmate-cold-weekly` — `0 21 * * 6` (Sunday 02:00 PKT) | row by name |
| `finmate-live-hourly` — `0 5,6,7,8,9,10 * * 1-5` (Mon-Fri 10:00-15:00 PKT) | row by name |
| Per-Scheduler execution history | click a job → **Logs** tab; each fired-trigger event has a link to the downstream Cloud Run execution |
| Force-fire a Scheduler now (test) | click a job → **Force run** button |
| Pause/resume a Scheduler | click a job → **Pause job** / **Resume job** |
| Change a cron expression | click a job → **Edit job** |

### Service Accounts and IAM — who has access

| What | Where |
|---|---|
| All service accounts in project | [console.cloud.google.com/iam-admin/serviceaccounts](https://console.cloud.google.com/iam-admin/serviceaccounts?project=venom-scent-476112) |
| `etl-b-147` SA — used by every Cloud Run Job | row by name; click for keys/permissions/details |
| Active keys for `etl-b-147` | click the SA → **Keys** tab. Don't add new keys casually — each one is a permanent credential. |
| Project-wide IAM roles | [console.cloud.google.com/iam-admin/iam](https://console.cloud.google.com/iam-admin/iam?project=venom-scent-476112) |
| Bucket-scoped IAM (where `etl-b-147` actually has Object Admin) | bucket → **Permissions** tab (NOT the project-level IAM page) |

### Artifact Registry — where the Docker image lives

| What | Where |
|---|---|
| All registries | [console.cloud.google.com/artifacts](https://console.cloud.google.com/artifacts?project=venom-scent-476112) |
| `finmate` repo (Docker, region `us-central1`) | click the repo |
| `pipeline:latest` image | inside the `finmate` repo → click `pipeline` → tags |
| Image size, digest, build history | per-tag detail page |

### Cloud Logging — read every Job's stdout

| What | Where |
|---|---|
| Logs Explorer | [console.cloud.google.com/logs/query](https://console.cloud.google.com/logs/query?project=venom-scent-476112) |
| Just a specific Job's logs (filter query) | `resource.type="cloud_run_job" resource.labels.job_name="finmate-warm"` |
| Last 24 hr of all FinMate jobs | `resource.type="cloud_run_job" resource.labels.job_name=~"finmate-.*"` |
| `STAGE:` markers from the entrypoints | add `textPayload=~"STAGE:"` to the filter |

### Cloud Build — image build logs

| What | Where |
|---|---|
| All builds | [console.cloud.google.com/cloud-build/builds](https://console.cloud.google.com/cloud-build/builds?project=venom-scent-476112) |
| Latest `pipeline:latest` build | most recent row, click for full log |

### Quick "is everything healthy?" checklist

Daily 5-minute health check (visit each link, scan for red):

1. [Cloud Run Jobs page](https://console.cloud.google.com/run/jobs?project=venom-scent-476112) — sort by Last execution. Anything not "Succeeded" in the last 24 hr is a flag.
2. [Cloud Scheduler page](https://console.cloud.google.com/cloudscheduler?project=venom-scent-476112) — Last status column should say "Successfully ran" for the last fire of each entry.
3. [Bucket outputs/](https://console.cloud.google.com/storage/browser/etl_b/outputs?project=venom-scent-476112) — `stocks.json` mtime should be from today's 18:30 PKT run; `live_data.json` mtime should be from the most recent market hour.
4. Friend's Supabase dashboard — most recent `ScrapeRun` row should say `status=SUCCESS`.

If any of those four fail, the answer is in step 1 or 2's logs.

---

## 12 · Glossary

- **Cloud Run Job** — Google's serverless compute primitive for one-shot containers. Triggered by HTTP, runs to completion, exits. Different from Cloud Run *Service* (long-running HTTP server).
- **Cloud Scheduler** — Google's cron-as-a-service. Fires HTTP requests on a schedule.
- **Service account** — non-human GCP identity. Our `finmate-runner` SA holds the role that lets Cloud Run read/write the `etl_b` bucket without anyone signing in.
- **Cold mode (forecasting)** — full retrain of LSTM weights on the whole history. Slow (~6-7 hr for 672 symbols) but produces fresh `Best_MAPE` stats.
- **Warm mode (forecasting)** — load yesterday's trained LSTM, predict today's bar only. Fast (~10 sec for 672 symbols).
- **Friend's tasks.py** — Django/Celery layer that wraps our pipeline + writes outputs into Supabase tables. Contract is the JSON shapes our pipeline produces.
- **Artifact Registry** — Google's Docker registry. Where Cloud Run pulls our image from on each Job invocation.
