# cloud_api_deployment.md — FinMate backend API on Google Cloud

How the **Django REST API** is deployed on Google Cloud, how the
**frontend (Expo / React Native)** talks to it, and every cloud resource
involved. Companion to [`cloud_link.md`](cloud_link.md) (which covers the
ETL/ML pipeline Jobs).

> Project: **`venom-scent-476112`** (number `1028659051797`) · Region: **`us-central1`**

---

## 1. TL;DR

| Thing | Value |
|---|---|
| **Live API base URL** | `https://finmate-api-rc4z2jb2kq-uc.a.run.app/api/v1/` |
| Cloud Run **Service** | `finmate-api` (`us-central1`) |
| Container **image** | `us-central1-docker.pkg.dev/venom-scent-476112/finmate/api:latest` |
| Container **command** | `/app/bin/run_api.sh` (collectstatic → gunicorn) |
| **Frontend setting** | `EXPO_PUBLIC_API_BASE_URL` in `FinMate-FE/.env` |
| Auth | JWT (SimpleJWT) — `POST /api/v1/login/` → `Authorization: Bearer <token>` |

The Service is **always available** (Cloud Run keeps it live, scales to
zero when idle). You never "start" it manually.

---

## 2. How the frontend uses the API

The Expo app reads **one** environment variable; every screen's service
file ([`src/services/*.ts`](../FinMate-FE/src/services/)) uses it:

```env
# FinMate-FE/.env
EXPO_PUBLIC_API_BASE_URL=https://finmate-api-rc4z2jb2kq-uc.a.run.app/api/v1
```

Each service falls back to a local URL only when that var is unset:

```ts
const API_BASE =
  process.env.EXPO_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ??
  (metroHost ? `http://${metroHost}:3100/api/v1` : "http://localhost:3100/api/v1");
```

### Apply a change to the URL
Expo bakes `EXPO_PUBLIC_*` vars at startup, so after editing `.env`:

```bash
cd FinMate-FE
npx expo start -c     # -c clears the cache so the new URL takes effect
```

### Production build (EAS / .apk)
`.env` is **not** read at EAS build time. Put the URL in the build
profile so the installed app uses the cloud, not localhost:

```jsonc
// FinMate-FE/eas.json
{
  "build": {
    "production": {
      "env": { "EXPO_PUBLIC_API_BASE_URL": "https://finmate-api-rc4z2jb2kq-uc.a.run.app/api/v1" }
    }
  }
}
```

### Auth flow
1. `POST /api/v1/login/` with `{ "email": "...", "password": "..." }`
   → returns `{ "access": "<jwt>", "refresh": "<jwt>" }`.
2. Send `Authorization: Bearer <access>` on every protected request.
3. Most endpoints return **401** without a valid token (expected).

### Key endpoints (prefix `/api/v1/`)
| Path | Purpose |
|---|---|
| `login/` | Obtain JWT tokens |
| `users/` , `users/device-tokens/` | Profile, prefs, Expo push-token registration |
| `portfolio/` | Holdings & analytics |
| `dashboard/` , `insights/` | Dashboard cards, insights |
| `news/feed/` , `news/filters/` , `news/sentiment-index/` , `news/search/` | News + sentiment |
| `alerts/` | Alert prefs & logs |
| `chatbot/ask/` , `chatbot/sessions/` , `chat/sessions/...` | Chatbot (⚠️ RAG brain is a stub — see §7) |

### Notes for the native app
- The API is **HTTPS** — required for Android release builds (cleartext
  `http://` is blocked in production).
- **CORS does not apply** to native apps (browser-only). A web frontend
  would need its origin added via the `CORS_EXTRA_ORIGINS` env var.

---

## 3. Where it lives in the cloud

### 3a. Image — Artifact Registry
```
us-central1-docker.pkg.dev/venom-scent-476112/finmate/api:latest
```
Built from this repo's working tree (`Dockerfile`, `COPY . /app`). This is
a **separate** tag from the pipeline Jobs' image (`finmate/pipeline:latest`),
so rebuilding the API never affects the scrapers/ML/alert Jobs.

Console: https://console.cloud.google.com/artifacts/docker/venom-scent-476112/us-central1/finmate?project=venom-scent-476112

### 3b. Service — Cloud Run
| Setting | Value |
|---|---|
| Name / region | `finmate-api` / `us-central1` |
| Command | `/app/bin/run_api.sh` (no args) |
| Port | `8080` |
| Resources | **4 GiB / 2 vCPU** (image carries torch/transformers) |
| Scaling | min `0` (scale-to-zero) · max `3` |
| Access | `--allow-unauthenticated` (JWT guards the endpoints) |
| Runtime SA | `1028659051797-compute@developer.gserviceaccount.com` |

Console: https://console.cloud.google.com/run/detail/us-central1/finmate-api?project=venom-scent-476112

### 3c. Secrets — Secret Manager
Injected as **env vars sourced from secrets** (values never appear in the
service spec):

| Env var | Secret |
|---|---|
| `DATABASE_URL` | `api-database-url` |
| `SECRET_KEY` | `api-secret-key` |
| `REDIS_URL` | `api-redis-url` |

Non-secret config set as plain env vars: `ALLOWED_HOSTS=.run.app,localhost,127.0.0.1`,
`DEBUG=False`, `PYTHONPATH=/app`.

The runtime SA has `roles/secretmanager.secretAccessor` on each secret.
Console: https://console.cloud.google.com/security/secret-manager?project=venom-scent-476112

### 3d. Settings the API reads (`config/settings.py`)
Fully 12-factor via `django-environ`. The `.env` file is optional in the
cloud — vars come from the environment. Cloud-relevant knobs:
- `ALLOWED_HOSTS`, `DEBUG`, `DATABASE_URL`, `REDIS_URL`, `SECRET_KEY`
- `CORS_EXTRA_ORIGINS` (comma-sep) — extra browser origins
- `CSRF_TRUSTED_ORIGINS` — defaults to `https://*.run.app`

---

## 4. Build & deploy (reproducible)

From the **FinMate-BE** repo root:

```bash
# 1. Build + push the image (Cloud Build; no local Docker needed)
gcloud builds submit \
  --tag us-central1-docker.pkg.dev/venom-scent-476112/finmate/api:latest .

# 2. Deploy / update the service
gcloud run deploy finmate-api \
  --image us-central1-docker.pkg.dev/venom-scent-476112/finmate/api:latest \
  --region us-central1 \
  --command /app/bin/run_api.sh \
  --port 8080 \
  --allow-unauthenticated \
  --service-account 1028659051797-compute@developer.gserviceaccount.com \
  --set-secrets "DATABASE_URL=api-database-url:latest,SECRET_KEY=api-secret-key:latest,REDIS_URL=api-redis-url:latest" \
  --set-env-vars "^@^ALLOWED_HOSTS=.run.app,localhost,127.0.0.1@DEBUG=False@PYTHONPATH=/app" \
  --memory 4Gi --cpu 2 --timeout 300 --min-instances 0 --max-instances 3
```

### Creating/rotating a secret
```bash
printf '%s' "<value>" | gcloud secrets create api-database-url --data-file=- --replication-policy=automatic
printf '%s' "<value>" | gcloud secrets versions add  api-database-url --data-file=-
gcloud secrets add-iam-policy-binding api-database-url \
  --member="serviceAccount:1028659051797-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

### Supporting files in this repo
- [`bin/run_api.sh`](bin/run_api.sh) — Service entrypoint: `collectstatic` then gunicorn on `$PORT`.
- [`.gcloudignore`](.gcloudignore) — controls Cloud Build upload (ensures untracked files like `run_api.sh` are uploaded; keeps `.git`/`.venv`/secrets out).
- `gunicorn` in [`requirements.txt`](requirements.txt).
- `CORS_EXTRA_ORIGINS` / `CSRF_TRUSTED_ORIGINS` handling in [`config/settings.py`](config/settings.py).

---

## 5. The other cloud deployments (Jobs)

The API Service is independent of the ETL/ML/alert **Cloud Run Jobs**,
which share the `finmate/pipeline:latest` image:

| Job | Role |
|---|---|
| `finmate-warm` (+ `-1..-4` steps) | Daily scrape → ML → ingest |
| `finmate-cold` | Weekly retrain |
| `finmate-live` | Intraday refresh |
| `finmate-monthly` | Monthly fundamentals |
| `finmate-alerts-dispatch` | Alert dispatch (`bin/run_alerts.sh` → `manage.py dispatch_alerts <window>`) |

Console: https://console.cloud.google.com/run/jobs?project=venom-scent-476112

---

## 6. Troubleshooting

| Symptom | Meaning / fix |
|---|---|
| Browser at `/` → **"Not Found"** | Normal — no root route; the API lives under `/api/v1/`. Server is healthy. |
| `401 {"detail":"Authentication credentials were not provided."}` | Expected — endpoint needs a JWT. Log in first. |
| Endpoint **500 only in a browser** (JSON client fine) | Static-files manifest missing — ensure the Service runs `bin/run_api.sh` (it runs `collectstatic`). |
| Container won't start, `ModuleNotFoundError: No module named 'config'` | App code shadowed/missing. Don't mount a secret at `/app/.env` (it hides `/app`); keep `PYTHONPATH=/app`. |
| Files missing from image | A `.gcloudignore` must exist, or `gcloud` drops untracked files on upload. |

Logs:
```bash
gcloud logging read 'resource.type="cloud_run_revision" resource.labels.service_name="finmate-api"' \
  --limit 50 --freshness 10m --format="value(timestamp, textPayload)"
```

---

## 7. Known gaps

- **Chatbot RAG is a stub.** `ml_services/chatbot_rag.py` `ask()` returns
  `"Chatbot not yet configured."` The endpoints work, but answers are not
  real until the LangChain/LLM RAG is implemented (no LLM packages in
  `requirements.txt` yet).
- **Django admin** (`/admin/`) loads, but a superuser must be created
  (`manage.py createsuperuser` against the prod DB) before you can log in.
