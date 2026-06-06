# cloud_link.md — every link you need

Quick-access deep links for the FinMate cloud setup. All links bake in
`?project=venom-scent-476112` so they jump straight into the right project.

---

## GitHub repos

- **Your fork (origin):** [github.com/Ahadmoen/FinMate-BE](https://github.com/Ahadmoen/FinMate-BE)
- **Friend's repo (upstream):** [github.com/Mubashir1920/FinMate-BE](https://github.com/Mubashir1920/FinMate-BE)
- Active branch on both: [`scraper-fixes-forecasting-sentiment`](https://github.com/Mubashir1920/FinMate-BE/tree/scraper-fixes-forecasting-sentiment)
- Latest commit: `2f26800`

---

## GCS bucket — `etl_b`

- **Bucket overview** (browse folders)
  → https://console.cloud.google.com/storage/browser/etl_b?project=venom-scent-476112
- **`outputs/`** — every JSON the latest run produced (overwritten each run)
  → https://console.cloud.google.com/storage/browser/etl_b/outputs?project=venom-scent-476112
- **`models/lstm/`** — per-symbol LSTM weights (672 files, ~134 MB)
  → https://console.cloud.google.com/storage/browser/etl_b/models/lstm?project=venom-scent-476112
- **`models/directional/`** — per-symbol ensembles (1,892 files, ~2.95 GB)
  → https://console.cloud.google.com/storage/browser/etl_b/models/directional?project=venom-scent-476112
- **`historical_data.json`** at the bucket root (327 MB)
  → same bucket overview link above; file is at root
- **Permissions tab** (who has access)
  → https://console.cloud.google.com/storage/browser/_details/etl_b;tab=permissions?project=venom-scent-476112
- **Lifecycle tab** (auto-delete rules)
  → https://console.cloud.google.com/storage/browser/_details/etl_b;tab=lifecycle?project=venom-scent-476112

---

## Cloud Run Jobs

(none created yet — pending friend discussion)

- **All Jobs** in the project
  → https://console.cloud.google.com/run/jobs?project=venom-scent-476112
- **Create a new Job** form
  → https://console.cloud.google.com/run/jobs/create?project=venom-scent-476112

When the three Jobs exist, they'll be at:
- `finmate-warm` (daily refresh)
- `finmate-cold` (weekly retrain)
- `finmate-live` (hourly intraday)

---

## Cloud Scheduler

(none created yet — pending friend discussion)

- **All Schedulers** in the project
  → https://console.cloud.google.com/cloudscheduler?project=venom-scent-476112
- **Create a Scheduler entry**
  → https://console.cloud.google.com/cloudscheduler/jobs/new?project=venom-scent-476112

When the three entries exist:
- `finmate-warm-daily` — `30 13 * * *` UTC = 18:30 PKT daily
- `finmate-cold-weekly` — `0 21 * * 6` UTC = Sunday 02:00 PKT
- `finmate-live-hourly` — `0 5,6,7,8,9,10 * * 1-5` UTC = 10:00-15:00 PKT, Mon-Fri

---

## IAM & Service Accounts

- **Service Accounts list**
  → https://console.cloud.google.com/iam-admin/serviceaccounts?project=venom-scent-476112
- **`etl-b-147` SA** (used by Cloud Run Jobs to access bucket)
  → https://console.cloud.google.com/iam-admin/serviceaccounts/details/etl-b-147@venom-scent-476112.iam.gserviceaccount.com?project=venom-scent-476112
- **Active keys for `etl-b-147`** (Keys tab)
  → same link → click "Keys" tab. Don't add new keys casually.
- **Project IAM** (project-wide roles)
  → https://console.cloud.google.com/iam-admin/iam?project=venom-scent-476112

---

## Artifact Registry — Docker image

- **All registries**
  → https://console.cloud.google.com/artifacts?project=venom-scent-476112
- **`finmate` repo** (Docker, `us-central1`)
  → https://console.cloud.google.com/artifacts/docker/venom-scent-476112/us-central1/finmate?project=venom-scent-476112
- **`pipeline:latest`** image (one tag, with the build digest you pushed)
  → https://console.cloud.google.com/artifacts/docker/venom-scent-476112/us-central1/finmate/pipeline?project=venom-scent-476112

Image tag string for use in Cloud Run Job config:
```
us-central1-docker.pkg.dev/venom-scent-476112/finmate/pipeline:latest
```

---

## Cloud Build — image build history

- **All builds**
  → https://console.cloud.google.com/cloud-build/builds?project=venom-scent-476112
- **Latest pipeline build** (was successful, ~10 min)
  → click the most-recent row on the page above

---

## Cloud Logging — read every Job's stdout

- **Logs Explorer**
  → https://console.cloud.google.com/logs/query?project=venom-scent-476112

Useful filters once Cloud Run Jobs are running:
```
resource.type="cloud_run_job" resource.labels.job_name="finmate-warm"
```
```
resource.type="cloud_run_job" resource.labels.job_name=~"finmate-.*"
textPayload=~"STAGE:"
```

---

## Secret Manager — Supabase credentials

(empty until friend supplies values)

- **Secret Manager list**
  → https://console.cloud.google.com/security/secret-manager?project=venom-scent-476112
- **Create a secret**
  → https://console.cloud.google.com/security/secret-manager/create?project=venom-scent-476112

Secrets to create when friend provides values:
- `supabase-database-url`
- (any other Supabase auth env vars his settings need)

---

## APIs (already enabled)

- **API library**
  → https://console.cloud.google.com/apis/library?project=venom-scent-476112
- Currently enabled: Artifact Registry, Cloud Build, Cloud Run Admin, Cloud Storage

---

## Billing & quotas

- **Billing overview**
  → https://console.cloud.google.com/billing?project=venom-scent-476112
- **Free tier usage**
  → https://console.cloud.google.com/billing/freetrial?project=venom-scent-476112
- **Current spend (this month)**
  → https://console.cloud.google.com/billing/reports?project=venom-scent-476112

Expected cost: ~$3-8/month. Watch for spikes here.

---

## Daily 5-min health check (visit each, scan for red)

1. **Cloud Run Jobs** → all Last execution = "Succeeded"
   https://console.cloud.google.com/run/jobs?project=venom-scent-476112
2. **Cloud Scheduler** → all Last status = "Successfully ran"
   https://console.cloud.google.com/cloudscheduler?project=venom-scent-476112
3. **Bucket `outputs/`** → `stocks.json` mtime = today's 18:30 PKT run
   https://console.cloud.google.com/storage/browser/etl_b/outputs?project=venom-scent-476112
4. **Friend's Supabase dashboard** → most recent `ScrapeRun` row `status=SUCCESS`

If any fail, the answer is in #1 or #2's logs (click the failed job → Executions/Logs tab).

---

## Local files referenced everywhere

- `~/.config/gcloud/finmate-sa.json` — service account JSON key (chmod 600, gitignored)
- `~/.zshrc` — has `GOOGLE_APPLICATION_CREDENTIALS` and `GCS_BUCKET=etl_b` exported
