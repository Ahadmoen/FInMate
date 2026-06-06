# FinMate — AI-Powered PSX Stock Platform

**Final Year Project** — Pakistan Stock Exchange (PSX) stock forecasting, portfolio management, and smart alert platform.

| Module | Stack | Folder |
|---|---|---|
| Mobile App (Frontend) | React Native + Expo | `frontend/` |
| Backend API + ML Pipeline | Django + scikit-learn + PyTorch | `backend/` |
| AI Chatbot | FastAPI + RAG + FinBERT | `chatbot/` |

---

## Repository Structure

```
FInMate_FYP/
├── backend/              Django API + ML pipeline (Cloud Run Jobs)
│   ├── integrations/     Scrapers (PSX live, historical, news)
│   ├── ml_services/      LSTM, ARIMA, directional classifier, FinBERT, fusion
│   ├── alerts/           Notification workflows (email + push)
│   ├── dashboard/        Supabase DB sync (warm pipeline)
│   ├── portfolio/        Portfolio & holdings models
│   ├── users/            Auth, device tokens, notification prefs
│   ├── bin/              Cloud Run Job entrypoint scripts
│   ├── Dockerfile        Image used by ALL Cloud Run Jobs
│   └── requirements.txt
│
├── frontend/             React Native + Expo mobile app
│   ├── src/
│   │   ├── screens/      All app screens
│   │   ├── components/   Shared UI components
│   │   ├── services/     API calls
│   │   └── utils/        Portfolio metrics, formatting helpers
│   ├── app.json          Expo config (bundleIdentifier, scheme)
│   └── eas.json          EAS Build config (production/preview profiles)
│
├── chatbot/              FastAPI RAG chatbot (deployed on VM)
│   ├── app/
│   │   ├── api/          /chat/ + /query/ endpoints
│   │   ├── retrieval/    QueryRouter, StructuredStore, VectorStore
│   │   └── generation/   LLM (Gemini) + schemas
│   └── Dockerfile
│
└── README.md             ← you are here
```

---

## Team

| Member | Responsibility |
|---|---|
| **Mubashir** | Frontend — full React Native / Expo app |
| **Wasif** | Backend API — Django REST endpoints, serializers, auth |
| **Ahad** | ML pipeline — scrapers, LSTM/ARIMA, classifier, cloud infra, chatbot |

---

## How the System Works (Overview)

```
PSX API ──→ historical_scraper ──→ historical_data.json
PSX API ──→ live_scraper       ──→ live_data.json          ─┐
Google News ─→ news_scraper    ──→ news_data.json            │
                                                             │
                        ML Pipeline (Cloud Run)              │
                ┌───────────────────────────────┐           │
                │ LSTM + ARIMA → stock_forecasts │           │
                │ FinBERT → news_sentiment       │           │
                │ Technicals (RSI, MA, vol)      │           │
                │ Directional classifier         │           │
                │ Fusion → stocks.json           │           │
                └───────────────────────────────┘           │
                               │                             │
                        Supabase (PostgreSQL) ←──────────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
         Django API       Chatbot API      Notification
         (VM port 8000)   (VM port 8001)   Celery worker
              │                │
         React Native     Mobile /chat
         mobile app       screen
```

---

## Backend — Django + ML Pipeline

### Local Setup

```bash
cd backend

# Python 3.13 recommended (matches Docker image)
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Copy environment template and fill in values
cp .env.example .env   # set SUPABASE_URL, SUPABASE_KEY, DATABASE_URL, GEMINI_API_KEY

# Run migrations
python manage.py migrate

# Start Django dev server
python manage.py runserver
```

### Environment Variables (required)

| Variable | Where to get it |
|---|---|
| `DATABASE_URL` | Supabase → Project Settings → Database → Connection string |
| `SUPABASE_URL` | Supabase → Project Settings → API → Project URL |
| `SUPABASE_KEY` | Supabase → Project Settings → API → anon/service key |
| `GEMINI_API_KEY` | Google AI Studio → Create API key |
| `GCS_BUCKET_NAME` | GCP Console → Cloud Storage → your bucket name |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to service account JSON (local only) |
| `SECRET_KEY` | Django secret key (any long random string) |
| `DEBUG` | `True` for local, `False` in production |

### Running the ML Pipeline Locally

Each pipeline step is a standalone Python script you can run manually:

```bash
cd backend

# 1. Fetch historical OHLCV from PSX
python -m integrations.scrapers.historical_scraper

# 2. Compute technicals (RSI, MA, volatility) — no PSX calls, uses historical_data.json
python -m integrations.scrapers.key_ratios_scraper   # set KEY_RATIOS_FUNDAMENTALS=0 to skip slow fundamentals

# 3. Scrape news and score sentiment
python -m integrations.scrapers.news_scraper
python -m ml_services.sentiment

# 4. Train LSTM + ARIMA forecasting models (cold = full retrain, takes 2+ hours)
python -m ml_services.forecasting
# Warm mode (uses cached LSTM weights, seconds per symbol):
python -m ml_services.forecasting --warm

# 5. Train directional classifier (cold)
python -m ml_services.directional_classifier
# Warm mode:
python -m ml_services.directional_classifier --warm

# 6. Fuse all signals into stocks.json
python -m ml_services.stock_health

# 7. Push stocks.json → Supabase
python manage.py sync_stocks
```

### Pipeline Modes: Cold vs Warm

| | Cold Run | Warm Run |
|---|---|---|
| **When** | First deploy, sklearn version change, model drift | Every day at ~5:35 PM PKT |
| **LSTM** | Full retrain (~2–4 hours for all symbols) | Load cached `.pt` weights, predict latest only (seconds) |
| **Directional Classifier** | Full train + 60-day backtest | Load cached `.pkl`, refresh latest probability |
| **Duration** | 4–6 hours | 15–25 minutes |
| **Model storage** | Saves to `data/models/{SYM}/lstm.pt` + `.pkl` | Loads from GCS |

---

## Frontend — React Native + Expo

### Local Setup

```bash
cd frontend

# Install dependencies
npm install

# Start Expo dev server (shows QR code for Expo Go)
npx expo start

# Or start for specific platform:
npx expo start --ios
npx expo start --android
```

### Environment

Create `frontend/.env`:
```
EXPO_PUBLIC_API_URL=http://YOUR_VM_IP:8000
EXPO_PUBLIC_CHATBOT_URL=http://YOUR_VM_IP:8001
```
For production, replace with your domain/IP. The VM's external IP is found in GCP Console → Compute Engine → VM instances.

### Building the App (EAS Build — for real device / App Store)

EAS Build compiles the native app binary in Expo's cloud — no Mac/Xcode needed for Android, Xcode required locally only for iOS submission.

#### Prerequisites
```bash
npm install -g eas-cli
eas login   # login with your Expo account
```

#### Android APK (for testing on device)
```bash
cd frontend
eas build --platform android --profile preview
```
This produces an `.apk` that you can install directly on any Android phone. Download link is shown in your Expo dashboard after ~5–15 minutes.

#### Android AAB (for Google Play submission)
```bash
eas build --platform android --profile production
```
Produces an `.aab` for Play Store upload. Requires a keystore (EAS creates and manages one for you on first build).

#### iOS (for TestFlight / App Store)
```bash
eas build --platform ios --profile production
```
Requires an Apple Developer account ($99/year). EAS handles code signing automatically if you give it your Apple credentials.

#### eas.json profiles explained
```json
{
  "build": {
    "preview": {
      "android": { "buildType": "apk" }   // installable APK for testing
    },
    "production": {
      "android": { "buildType": "app-bundle" },  // Play Store
      "ios": {}                                   // App Store
    }
  }
}
```

#### OTA Updates (no app store re-submit)
For JS-only changes (screens, logic, styles — NOT native modules):
```bash
cd frontend
eas update --branch production --message "fix: stock card layout"
```
Users get the update next time they open the app. No Play Store / App Store review needed.

---

## Chatbot — FastAPI RAG

### Local Setup

```bash
cd chatbot

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Copy and fill env
cp .env.example .env

# Start server
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

### Chatbot Environment Variables

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Same Supabase PostgreSQL URL as backend |
| `GEMINI_API_KEY` | Gemini 1.5 Flash for response generation |
| `REDIS_URL` | Redis for conversation cache (optional, `redis://localhost:6379`) |

---

## Cloud Infrastructure — Google Cloud Platform

### Architecture

```
Cloud Scheduler ──→ Cloud Run Jobs ──→ GCS Bucket (data JSON files)
                                              │
                                       Supabase (PostgreSQL)
                                              │
                                       Compute Engine VM
                                       ├── Django API  (:8000)
                                       ├── Chatbot API (:8001)
                                       ├── Celery worker (alerts)
                                       └── Redis        (:6379)
```

### GCP Services Used

| Service | What for |
|---|---|
| **Cloud Run Jobs** | ML pipeline steps — run to completion, pay per second, no always-on server |
| **Cloud Scheduler** | Cron triggers for each job (daily warm, 20-min live scraper) |
| **Cloud Storage (GCS)** | Stores JSON data files between pipeline steps |
| **Artifact Registry** | Docker image registry (`finmate-be/pipeline:latest`) |
| **Cloud Build** | Builds Docker image from `backend/Dockerfile` on push |
| **Secret Manager** | Stores all secrets, injected as env vars into Jobs at runtime |
| **Compute Engine** | `e2-standard-4` VM for Django API + chatbot + Celery + Redis |
| **Supabase** | Managed PostgreSQL — the source of truth for the mobile app |

### Cloud Run Jobs Schedule

| Job | Schedule (PKT) | What it does |
|---|---|---|
| `finmate-warm` | 5:35 PM daily (Mon–Fri) | Full warm pipeline: historical → technicals → news → ML predict → fuse → Supabase |
| `finmate-live-a` | Every 20 min, 9AM–3:30PM | Live scraper, half A (even-indexed symbols) |
| `finmate-live-b` | Every 20 min, 9:10AM–3:30PM | Live scraper, half B (odd-indexed symbols, staggered 10 min) |
| `finmate-cold` | Manual | Full retrain (LSTM + classifier). Run only when needed. |
| `finmate-monthly` | 1st of each month | Refresh symbol list from PSX registry |

### Deploying a Code Change to Cloud

```bash
cd backend

# 1. Build new Docker image and push to Artifact Registry
gcloud builds submit \
  --tag us-central1-docker.pkg.dev/YOUR_PROJECT/finmate-be/pipeline:latest \
  .

# 2. Update Cloud Run Jobs to use the new image
gcloud run jobs update finmate-warm \
  --image=us-central1-docker.pkg.dev/YOUR_PROJECT/finmate-be/pipeline:latest \
  --region=us-central1

gcloud run jobs update finmate-live-a \
  --image=us-central1-docker.pkg.dev/YOUR_PROJECT/finmate-be/pipeline:latest \
  --region=us-central1

gcloud run jobs update finmate-live-b \
  --image=us-central1-docker.pkg.dev/YOUR_PROJECT/finmate-be/pipeline:latest \
  --region=us-central1

# 3. (Optional) Trigger warm run immediately to verify
gcloud run jobs execute finmate-warm --region=us-central1

# 4. Watch logs
gcloud run jobs executions logs --job finmate-warm --region=us-central1
```

### Deploying Chatbot or Django API Changes to VM

The VM runs the app directly (not containerized). SSH in and pull:

```bash
# SSH into VM
gcloud compute ssh finmate-vm --zone=us-central1-a

# On the VM:
cd /home/finmate/finmate-chatbot
git pull origin main
sudo systemctl restart finmate-chatbot   # or: pkill uvicorn && ./start.sh

cd /home/finmate/FinMate-BE
git pull origin main
sudo systemctl restart finmate-backend
```

### Checking Job Logs (Cloud Console)

1. Go to [Cloud Run → Jobs](https://console.cloud.google.com/run/jobs)
2. Click the job → Executions tab → click an execution → Logs
3. Or use CLI: `gcloud run jobs executions logs --job=finmate-warm --region=us-central1`

### Adding / Changing Secrets

```bash
# Create a new secret
echo -n "my-secret-value" | gcloud secrets create MY_SECRET_NAME --data-file=-

# Update an existing secret
echo -n "new-value" | gcloud secrets versions add MY_SECRET_NAME --data-file=-

# Grant Cloud Run Job access to a secret
gcloud secrets add-iam-policy-binding MY_SECRET_NAME \
  --member="serviceAccount:YOUR_SA@YOUR_PROJECT.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

---

## Data Files (what each JSON contains)

All files live in `backend/integrations/data/` locally and in GCS on cloud.

| File | Written by | Contains |
|---|---|---|
| `historical_data.json` | `historical_scraper.py` | Daily OHLCV for all symbols (multi-year) |
| `live_data.json` | `live_scraper.py` | Latest hourly bar per symbol (today) |
| `news_data.json` | `news_scraper.py` | Raw PSX news articles |
| `news_sentiment.json` | `ml_services/sentiment.py` | News + FinBERT scores per article |
| `daily_ratios.json` | `key_ratios_scraper.py` | RSI14, MA20/50/200, volatility per symbol |
| `fundamental_ratios.json` | `key_ratios_scraper.py` | EPS, PE, dividend yield per symbol |
| `stock_forecasts.json` | `ml_services/forecasting.py` | ARIMA/LSTM predicted price per symbol |
| `best_models.json` | `ml_services/forecasting.py` | Which model (ARIMA/LSTM) won per symbol + MAPE |
| `directional_signals.json` | `ml_services/directional_classifier.py` | UP/DOWN signal per symbol × horizon |
| `stocks.json` | `ml_services/stock_health.py` | Fused health score + BUY/HOLD/SELL per symbol |
| `last_bars.json` | `dashboard/db_cache.py` (warm-1) | Last real OHLCV bar per symbol (stub source) |

---

## ML Models Summary

| Model | Type | Input | Output |
|---|---|---|---|
| **ARIMA(5,1,0)** | Statistical | Historical closes | 1-day + 30-day price forecast |
| **LSTM** (2-layer, hidden=64, lookback=60d) | Deep learning | 60-day OHLCV window | Next-day price |
| **FinBERT** (`ProsusAI/finbert`) | Pre-trained transformer | Headline text | Sentiment score [-1, 1] |
| **Directional Ensemble** (GBM + RF + LR) | Classification | 14 price+volume features | UP/DOWN probability per horizon |
| **Fusion engine** | Weighted sum | Forecast + sentiment + technicals | Health score + BUY/HOLD/SELL |

### How the Signal Is Made

1. **Forecast score**: `clamp(expected_price_change_pct / 3.0, -1, +1)` — a 3% move maps to ±1
2. **Sentiment score**: blended avg of direct news + industry news (0.4×) + macro news (0.2×), last 7 days only
3. **Technical score**: price vs MA50/MA200 + RSI adjustment, range [-1, +1]
4. **Dynamic weights**: per-stock quality scores (MAPE → forecast quality, article count/recency → sentiment quality, history length → technical quality) — accurate components get more weight
5. **Fusion**: weighted sum of the three scores → Health Score → Label (VERY_BAD to EXCELLENT)
6. **Suggestion**: blended score = 0.5×Health + 0.5×forecast-signed → BUY/HOLD/SELL thresholds
7. **Veto**: bearish news overrides BUY; directional classifier disagreement overrides BUY/SELL

---

## Notification System

Three windows per day: **PRE_MARKET**, **MID_SESSION**, **POST_MARKET**

| Workflow | Trigger | What's sent |
|---|---|---|
| **Top Pick** | Each window | #1 STRONG_BUY by blended score → Gemini summary → email + push |
| **Digest** | 2 min after top pick | #2–21 STRONG_BUYs in one email |
| **Position Alerts** | Each window | Personalized SELL/STRONG_SELL alert for each user's holdings |

Channels: **In-app** (always) · **Email** (if opted in) · **Push (FCM)** (if device registered)

User preferences control: `pre_market`, `mid_session`, `post_market` toggles + `email_enabled`, `in_app_enabled`

---

## Common Issues & Fixes

### Live scraper only fetching ~150 out of 464 symbols
PSX rate-limits GCP datacenter IPs to ~150 requests per IP per window. Not solvable from code — the remaining symbols fall back to real last-trading-day bars from `last_bars.json`.

### warm-3 sklearn pickle error (`_loss` module / `multi_class` attribute)
Caused by training models with sklearn 1.3.x and loading with 1.5+. Fix: run a cold job to retrain all models, then pin `scikit-learn==X.X.X` in `requirements.txt` to match.

### EPS/PE disappeared from live data
`key_ratios_scraper` ran from cloud IP → PSX blocked fundamentals page → all Snapshots empty → `fundamental_ratios.json` overwritten with nulls. Fix: run `key_ratios_scraper.py` locally (Mac IP works), upload result to GCS, re-run warm-3.

### Redis bgsave error blocking chatbot writes
```bash
redis-cli CONFIG SET stop-writes-on-bgsave-error no
redis-cli CONFIG SET save ""
```

### VM disk 100% full
```bash
docker system prune -f   # frees old Docker layers, typically 5–10 GB
```

### finmate-live-b running wrong command
If a Cloud Run job runs an unexpected command (leftover `--args` override):
```bash
gcloud run jobs update finmate-live-b --command="/app/bin/run_live.sh" --args="" --region=us-central1
```

---

## Local Development Without Cloud

You can run the full pipeline on your laptop — no GCP needed:

1. All scrapers write to `backend/integrations/data/` (local files)
2. Use a local PostgreSQL or point `DATABASE_URL` at Supabase directly
3. Skip GCS steps — all ML steps read/write from the local `data/` folder
4. Run `python manage.py runserver` for the API
5. In Expo, point `EXPO_PUBLIC_API_URL=http://localhost:8000`
6. Use Expo Go app (scan QR) for instant preview without building

The only things that won't work locally: Cloud Run Job scheduling and remote GCS sync. Everything else is identical.

---

## Secrets Management

**Never commit:**
- `.env` files
- Firebase Admin SDK JSON (`*adminsdk*.json`)
- GCP service account keys (`*-sa.json`)
- Any file matching `*service*account*.json`

**For local dev:** keep secrets in `.env` (gitignored).

**For cloud:** all secrets are in **GCP Secret Manager** and injected as environment variables into Cloud Run Jobs at runtime. No secrets are baked into the Docker image.

To rotate a secret: update the version in Secret Manager, then re-execute the relevant Cloud Run Job.
