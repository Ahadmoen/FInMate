# FinMate — Full System Report

## What, Why, and How — Data → ML → Cloud → Notifications

---

## 1. Data Collection — Where the Numbers Come From

### 1.1 Historical OHLCV Data
**Source:** `https://dps.psx.com.pk/timeseries/int/{symbol}` (PSX internal API)
**File:** `historical_data.json`
**What it contains:** Daily Open, High, Low, Close, Volume per symbol going back years
**How:** `historical_scraper.py` fetches each of the 464 active symbols one by one (no bulk endpoint exists). Per-IP rate limit: ~150 requests per run from GCP IPs. Month-by-month batch with pause between batches to avoid throttling.
**When:** Once daily via Cloud Run Job `finmate-warm` (warm-1 step) at ~5:35 PM PKT, after PSX market closes at 3:30 PM.

### 1.2 Live / Intraday Data
**Source:** Same PSX API: `https://dps.psx.com.pk/timeseries/int/{symbol}`
**File:** `live_data.json`
**What it contains:** Intraday tick data → resampled to 1-hour OHLCV bars
**How:** `live_scraper.py` runs with `curl_cffi` (Chrome TLS fingerprint impersonation) to stay under PSX rate limits. Two jobs (A and B) run staggered every 20 minutes during market hours — each fetches half the symbol list (interleaved odd/even indices) then merges back into a single 464-row file.
**Limitation:** GCP datacenter IPs are rate-limited by PSX to ~98–150 live fetches per half per run. Remaining ~80–100 tickers fall back to a stub using the real last-trading-day close from `last_bars.json` (not a fake flat bar).
**When:** Every 20 min during market hours via `finmate-live-a` and `finmate-live-b` Cloud Run Jobs.

### 1.3 News Data
**Source:** Google News RSS feed via `psx-data-reader` library (PSX-tagged headlines)
**File:** `news_data.json`
**What it contains:** Headlines, descriptions, dates, linked symbols, market/industry tags
**How:** `news_scraper.py` pulls headlines per ticker, plus macro/industry articles tagged as `GENERAL` with a `Market` field. Articles are kept up to 30 days.
**When:** Daily as part of warm pipeline.

### 1.4 Fundamentals (EPS, PE, Market Cap)
**Source:** PSX company page: `https://dps.psx.com.pk/company/{symbol}`
**File:** `fundamental_ratios.json`
**How:** `key_ratios_scraper.py` scrapes each company page. Cloud IPs are blocked by PSX for this endpoint, so this runs locally on Mac (Mac IP not rate-limited) then uploaded to GCS.
**Guard:** If ALL Snapshots come back empty (cloud IP blocked), the scraper keeps the existing file rather than overwriting with blanks — preserving last known EPS/PE.
**When:** Quarterly (manually triggered cold run), or warm skip via `KEY_RATIOS_FUNDAMENTALS=0`.

---

## 2. ML Models — What Each One Does

### 2.1 Forecasting Model — ARIMA + LSTM
**File:** `ml_services/forecasting.py`
**Purpose:** Predict next-day (and 30-day trend) closing price from historical OHLCV

#### ARIMA
- Order: (5, 1, 0) — 5 autoregressive lags, 1 differencing, 0 moving average
- Refitted every 7 walk-forward days during backtesting (cheap, 1–3s per symbol)
- Used for 30-day trend forecasts (multi-step) because ARIMA doesn't accumulate error the way recursive LSTM does on long horizons
- Stateless: no stored weights — refits from scratch each warm run

#### LSTM
- Architecture: 2-layer bidirectional-style LSTM, hidden size 64, dropout 0.2
- Lookback window: 60 days (uses the prior 60 days to predict day 61)
- Features fed in: Close, Volume (normalized)
- Training: up to 100 epochs with early stopping (patience=10), batch size 64, Adam optimizer LR=0.005
- Cold mode: full retrain from scratch, saves weights to `data/models/{SYM}/lstm.pt`
- Warm mode: loads cached weights, predicts only the most recent day (seconds instead of hours)
- Fallback: if no cached LSTM exists for a symbol in warm mode, falls back to cold (full retrain for that symbol only)

#### Which model wins?
- 60-day walk-forward backtest compares ARIMA vs LSTM on MAPE (Mean Absolute Percentage Error)
- Lower MAPE = winner. Result saved to `best_models.json`
- Trend forecast always uses ARIMA (better for multi-step future horizons)

#### Output:
`stock_forecasts.json` — `PredictedPrice`, `Direction` (UP/DOWN/STABLE), `MAPE`, `Best_Model` per symbol

---

### 2.2 News Sentiment Model — FinBERT (fallback: VADER)
**File:** `ml_services/sentiment.py`
**Purpose:** Score news headlines as positive/negative/neutral for each ticker

#### FinBERT (primary)
- Model: `ProsusAI/finbert` — BERT fine-tuned on 10,000 financial news sentences from Reuters and Bloomberg
- Outputs 3-class probability: positive, negative, neutral
- Compound score = `positive_prob - negative_prob` → range [-1, 1]
- Batch size: 16 articles per GPU/CPU pass
- Max token length: 256 (headlines truncated if longer)
- Pre-downloaded into Docker image at build time (440MB) so Cloud Run doesn't fetch from HuggingFace at runtime

#### VADER (fallback)
- Used when FinBERT fails to load (no network, minimal env, or forced via `SENTIMENT_BACKEND=vader`)
- Augmented with 30 finance-specific lexicon overrides (e.g., "fraud" = -3.5, "surge" = +2.5)
- Standard VADER compound score in [-1, 1]

#### Buckets:
| Score range | Label |
|---|---|
| [-1.0, -0.6) | VERY_BAD |
| [-0.6, -0.2) | BAD |
| [-0.2, +0.2) | NEUTRAL |
| [+0.2, +0.6) | GOOD |
| [+0.6, +1.0] | EXCELLENT |

#### How news gets assigned to stocks:
Three-bucket blending in `stock_health.py`:
- **Direct** (weight 1.0): article explicitly mentions the ticker symbol
- **Industry** (weight 0.4): article tagged as the same industry/sector (e.g., Cement) but not ticker-specific
- **Macro** (weight 0.2): article tagged `Market=Macro` (USD/PKR rate, IMF, petrol price) — bleeds into every ticker
- Only articles from the **last 7 days** feed into the prediction signal. Older articles stay in DB for UI history but don't affect buy/sell decisions.

**Output:** `news_sentiment.json` — per-article compound score + label

---

### 2.3 Technical Indicators — Computed, Not Learned
**File:** `ml_services/key_ratios_scraper.py` + `ml_services/fusion.py`
**Purpose:** Measure current price momentum, trend, and volume relative to history

These are not ML models — they are deterministic formulas computed from `historical_data.json`:

| Indicator | Formula | What it means |
|---|---|---|
| RSI14 | 14-day Relative Strength Index | < 30 = oversold (buy signal), > 70 = overbought (sell signal) |
| MA20 | 20-day moving average of close | Short-term trend |
| MA50 | 50-day moving average | Medium-term trend |
| MA200 | 200-day moving average | Long-term trend |
| PriceVsMA50Pct | (close - MA50) / MA50 × 100 | How far above/below 50d trend |
| PriceVsMA200Pct | (close - MA200) / MA200 × 100 | How far above/below 200d trend |
| Volatility20d | std(daily_returns, 20d) × √252 | Annualized 20-day volatility |
| VolumeRatio | today_volume / 20d_avg_volume | Is today's volume unusual? |
| EPS | Earnings Per Share | From PSX company page (quarterly) |

**Technical Score for fusion (range -1 to +1):**
```
score += clamp(PriceVsMA50Pct / 25, -0.4, +0.4)
score += clamp(PriceVsMA200Pct / 50, -0.4, +0.4)
if RSI14 < 30: score += 0.2   # oversold → upward pressure
if RSI14 > 70: score -= 0.2   # overbought → downward pressure
score = clamp(score, -1, +1)
```

**Output:** `daily_ratios.json` — technicals per symbol, written daily by warm-2

---

### 2.4 Directional Classifier — Signal Classifier
**File:** `ml_services/directional_classifier.py`
**Purpose:** Independently predict whether price will go UP or DOWN over 1, 5, and 20 day horizons

This is a **separate, standalone classifier** — it does NOT use ARIMA/LSTM outputs. It works entirely from price + volume history.

#### Why a separate classifier?
The ARIMA/LSTM forecasters predict a *price level* (regression). Converting a price level to UP/DOWN loses directional accuracy. A classifier trained directly on UP/DOWN labels using a loss function that rewards directional correctness does better.

#### Features (14 features per day, all lookback-only — no future leakage):
| Feature | What it captures |
|---|---|
| ret_1d, ret_3d, ret_5d, ret_10d, ret_20d, ret_60d | Returns over multiple lookback windows |
| ma20_z, ma50_z, ma200_z | Z-score: how far price is from each moving average (in std devs) |
| rsi14 | Momentum oscillator |
| vol10, vol20 | 10-day and 20-day realized volatility |
| vol_ratio | Volume relative to 20-day average |
| vol_z | Volume z-score vs 20-day distribution |
| macd_norm | MACD-like signal (12d MA - 26d MA) / close |

#### Model — Soft-Vote Ensemble of 3 classifiers:
The probability is the **average** of all three models' UP probability:

```
final_prob = (GBM_prob + RF_prob + LR_prob) / 3
```

**1. GradientBoostingClassifier (GBM)**
- 120 estimators, max_depth=3, learning_rate=0.05, subsample=0.85
- Captures non-linear interactions between features
- Shrinkage (low lr + high n_estimators) prevents overfitting on noisy financial data

**2. RandomForestClassifier (RF)**
- 200 trees, max_depth=8, min_samples_leaf=15
- Decorrelated trees via random feature subsets
- min_samples_leaf=15 forces generalization (no split on fewer than 15 points)

**3. LogisticRegression (LR)**
- C=1.0 (L2 regularized), max_iter=1000
- Linear baseline — pulls the ensemble toward simpler decisions when GBM/RF overfit

All features are StandardScaler-normalized before fitting (mean=0, std=1) because LR is sensitive to scale.

#### Why ensemble instead of one model?
Each model type makes different kinds of errors. GBM captures complex patterns; RF is robust to outliers; LR provides a regularizing linear anchor. Averaging reduces variance of the final probability estimate.

#### High-confidence gating:
Only calls with |prob - 0.5| ≥ 0.10 (the `HIGH_CONF_DELTA`) are labeled HIGH confidence:
- prob ≥ 0.60 → UP, HIGH confidence
- prob ≤ 0.40 → DOWN, HIGH confidence  
- Otherwise → same direction but LOW confidence

This is intentional: we'd rather make fewer, more accurate calls than many uncertain ones. The high-confidence subset typically achieves 65–75% directional accuracy in backtest vs ~52% for all calls.

#### Three horizons: 1d, 5d, 20d
The classifier is trained separately for each horizon. The label for a given training row is:
```
y = 1 if close[t + horizon] > close[t] else 0
```

The `_pick_primary_horizon` function in `stock_health.py` selects the best horizon per symbol:
- Prefers the horizon with highest `HighConfHitRate` where coverage ≥ 20% (avoids 100% hit-rate on 1 sample)
- Falls back to overall hit rate if no horizon clears the coverage bar

#### Output: `directional_signals.json`
Per symbol: LatestDirection (UP/DOWN), LatestConfidence (HIGH/LOW), LatestProbability, HighConfHitRate, OverallHitRate, HighConfCoverage — per horizon (1d, 5d, 20d)

---

## 3. Fusion — How the Signals Are Combined

**File:** `ml_services/fusion.py` + `ml_services/stock_health.py`
**Purpose:** Combine forecast score + news sentiment score + technical score into one health score

### Step 1: Normalize all components to [-1, +1]

| Component | Raw value | Normalization |
|---|---|---|
| Forecast | Predicted % change | clamp(expected_pct / 3.0, -1, +1) — so ±3% maps to ±1 |
| Sentiment | Blended avg news score | Already in [-1, +1] from FinBERT |
| Technicals | PriceVsMA + RSI formula | Already computed as score in [-1, +1] |

### Step 2: Dynamic quality-based weighting (per stock, per run)

Each component gets a **quality score** [0, 1] reflecting how trustworthy its signal is for THIS symbol right now:

**Forecast quality:**
```
quality = max(0, 1 - MAPE / 0.20)
```
MAPE = 0% → quality 1.0. MAPE = 20%+ → quality 0. An inaccurate forecaster gets less weight.

**Sentiment quality:**
```
coverage = min(article_count / 30, 1.0)     # 30+ articles = full
recency  = min(recent_7d_count / 5, 1.0)    # 5+ recent = full
decisive = abs(avg_sentiment_score)
quality  = 0.40×coverage + 0.40×recency + 0.20×decisive
```
A ticker with no news coverage gets low sentiment quality → news weight shrinks.

**Technical quality:**
```
quality = 0.30 (base — have any technicals)
        + 0.30 if MA50 computed (needs 50 days of history)
        + 0.30 if MA200 computed (needs 200 days)
        + 0.10 if RSI < 30 or RSI > 70 (decisive territory)
```
A newly-listed stock with 30 days of history gets low technical quality.

**Final weights (with floor of 0.10 so every component has a voice):**
```
weight_i = max(quality_i, 0.10)
weight_i = weight_i / sum(all weights)   # normalize to sum = 1
```

**Default fallback weights** (when all quality = 0): Forecast 40%, Sentiment 40%, Technicals 20%

### Step 3: Divergence damping (forecast sanity check)

If the forecast score is extreme (|score| ≥ 0.5) but the average of the other two signals points the opposite way:
```
disagreement = min(|forecast - others_avg|, 2.0) / 2.0   # 0..1
damping_factor = 1.0 - 0.40 × disagreement               # max 40% reduction
forecast_used = forecast × damping_factor
```
This stops a very bullish ARIMA from overruling clearly negative news + technicals reality.

### Step 4: Weighted sum = Health Score

```
Health.Score = w_forecast × forecast_used
             + w_sentiment × sentiment_score
             + w_technical × technical_score
```

Health label buckets: `[-1,-0.6)` = VERY_BAD, `[-0.6,-0.2)` = BAD, `[-0.2,+0.2)` = NEUTRAL, `[+0.2,+0.6)` = GOOD, `[+0.6,+1.0]` = EXCELLENT

### Step 5: Suggestion (BUY/HOLD/SELL)

The suggestion engine blends two scores:
```
fc_signed = clamp(expected_pct / 3.0, -1, +1) × fc_confidence
blended   = 0.5 × Health.Score + 0.5 × fc_signed
```
`fc_confidence = max(0, 1 - MAPE)` — accurate model = more voice in the suggestion.

**Decision rules:**
| Condition | Action |
|---|---|
| blended ≥ 0.40 AND direction aligned AND confidence ≥ 90% | STRONG_BUY |
| blended ≥ 0.15 AND direction=UP AND not contradicting | BUY |
| blended ≤ -0.40 AND aligned AND confidence ≥ 90% | STRONG_SELL |
| blended ≤ -0.15 AND direction=DOWN AND not contradicting | SELL |
| signals contradict each other | HOLD |
| otherwise | HOLD |

**News veto:** If action=BUY but avg sentiment ≤ -0.30 → downgrade to HOLD ("bearish news overrides")
**Directional classifier veto:** If action=BUY but directional classifier says DOWN with HIGH confidence and ≥55% historical hit rate → downgrade to HOLD

**Output:** `stocks.json` — one row per symbol with Symbol, Name, Industry, LastClose, Forecast block, News block, Ratios block, Directional block, Health block, Suggestion block

---

## 4. Why Deployed on Cloud

The pipeline cannot run on a laptop 24/7. Specifically:

| Requirement | Why cloud solves it |
|---|---|
| Daily OHLCV backfill after 3:30 PM PKT | Cloud Run Job triggered by scheduler — runs exactly at 5:35 PM PKT regardless of whether anyone's laptop is on |
| 20-min live data during market hours | Cloud Run Jobs can be scheduled on short intervals; impossible to maintain on a laptop reliably |
| LSTM training for 464 symbols takes 2+ hours | Cloud VM (e2-standard-4, 4 vCPU / 16 GB RAM) does it once in cold run; warm run is seconds |
| Stock data must be in Supabase (PostgreSQL) for the frontend to query | Needs an always-on connection to upload after every scraper run |
| Mobile app users expect current data without manually refreshing | Data must be pushed to DB on a schedule, not pulled ad-hoc |
| Team members can't share a laptop | Cloud infra is shared, accessible, auditable |

---

## 5. How Deployed on Cloud (Google Cloud Platform)

### Architecture
```
Cloud Scheduler → Cloud Run Jobs → GCS bucket (data files) ↔ Supabase (PostgreSQL)
                                        ↕
                                   Compute Engine VM (MLflow tracking server)
```

### Key GCP Services

**Cloud Run Jobs** — serverless containers that run to completion and exit. No always-on server, pay per second.
- `finmate-cold` — full retrain (LSTM + directional classifier), run once or when sklearn models break
- `finmate-warm` — daily pipeline: historical backfill → technicals → news sentiment → ARIMA predict → ML warm predict → fuse → upload to Supabase
- `finmate-live-a` / `finmate-live-b` — live data scraper, two halves, every 20 min
- `finmate-monthly` — monthly symbols refresh from PSX registry

**Cloud Scheduler** — cron jobs that trigger the Cloud Run Jobs via HTTP POST to the Jobs API. Scheduler service account has `roles/run.developer` to invoke jobs.

**GCS (Google Cloud Storage)** — `finmate-data` bucket. Scrapers download their input JSON files at start, upload output JSON files at end. The warm run's `run_live.sh` script:
1. Downloads `historical_data.json`, `live_data.json`, `stocks.json`, etc. from GCS
2. Runs the pipeline steps (scrapers → ML → fusion)
3. Uploads updated files back to GCS
4. Calls Django management command to push data from JSON files into Supabase tables

**Artifact Registry** — stores Docker images. Cloud Build builds the image from `Dockerfile` and pushes to `us-central1-docker.pkg.dev/finmate-*/finmate-be/pipeline:latest`. All Cloud Run Jobs use this same image.

**Secret Manager** — stores `SUPABASE_URL`, `SUPABASE_KEY`, `DATABASE_URL`, `GEMINI_API_KEY`, etc. Injected as environment variables into Cloud Run Jobs at runtime — never baked into the image.

**Compute Engine VM** (`e2-standard-4`) — runs the MLflow tracking server (experiment logging for model metrics) and the Django/DRF API server that the mobile app calls.

### Deployment Steps (when code changes)
```bash
# 1. Build and push new image
gcloud builds submit --tag us-central1-docker.pkg.dev/PROJECT/finmate-be/pipeline:latest .

# 2. Update job to use new image
gcloud run jobs update finmate-warm --image=us-central1-docker.pkg.dev/PROJECT/finmate-be/pipeline:latest

# 3. (Optional) Run immediately to verify
gcloud run jobs execute finmate-warm
```

### Cold Run vs Warm Run

| | Cold | Warm |
|---|---|---|
| When | First deploy, after sklearn version change, model drift | Every day at 5:35 PM PKT |
| LSTM | Full retrain (2–4 hours for all 464 symbols) | Load cached weights, predict latest day only (seconds) |
| Directional Classifier | Full train + backtest | Load cached ensemble, refresh latest probability only |
| Key Ratios | Technicals + Fundamentals | Technicals only (`KEY_RATIOS_FUNDAMENTALS=0`) |
| Model storage | Saves `.pt` (LSTM) + `.pkl` (classifier) to GCS | Loads from GCS |

---

## 6. How Notifications Work

**File:** `alerts/services.py`

Three notification types are sent at three market windows per day:

| Window | Time (PKT) | What's sent |
|---|---|---|
| PRE_MARKET | Before 9 AM | Outlook for the day |
| MID_SESSION | ~12 PM | Update during trading |
| POST_MARKET | After 3:30 PM | Recap after close |

### Workflow A — Top Pick
1. Query DB for all `STRONG_BUY` signals with `suggestion_confidence = HIGH`
2. Sort by `blended_score` descending → take #1 (the highest-confidence strong buy)
3. Call Gemini API (`summarizer.summarize_top_pick`) to write a 2-3 sentence human-readable summary
4. For every user who opted into this window:
   - Write `Alert` + `AlertDetail` + `Notification` rows to DB
   - Send email via SendGrid/SMTP (`formatters.build_top_pick_email`)
   - Send push notification to each user's registered device tokens (Firebase FCM via `push.send_push_notification`)
   - Write `AlertLog` row recording sent/failed/skipped for each channel

### Workflow A — Digest
1. Same STRONG_BUY signals, but #2 through #21 (top pick excluded, capped at 20)
2. Summarize the group in one email showing all tickers
3. Send to all opted-in users as a single digest alert

### Workflow B — Position Alerts (personalized)
1. Query DB for all `SELL` or `STRONG_SELL` signals
2. Find every user's `PortfolioHolding` that matches those tickers
3. For each user × ticker pair:
   - Compute their personal P&L: `(current_price - avg_buy_price) × quantity`
   - Call Gemini to write a personalized summary mentioning their holding
   - Send email with their specific P&L numbers
   - Send push notification
4. Cache live data and news per ticker (multiple users holding same stock → fetch once)

### Channels
- **In-app:** Always written to `Notification` table — the mobile app reads these
- **Email:** SendGrid/SMTP, only if user has `email_enabled=True` and has an email address
- **Push (FCM):** Firebase Cloud Messaging, only if user has registered device tokens

### User preferences control everything
`NotificationPreference` model has: `pre_market`, `mid_session`, `post_market` (boolean toggles), `email_enabled`, `in_app_enabled`
Users only receive alerts for windows they've opted into.

---

## 7. End-to-End Prediction Flow — How One Prediction Is Made

For symbol `SYS` on a given warm run:

```
Step 1 — historical_data.json already has SYS close prices (updated today by historical_scraper)

Step 2 — ARIMA:
  → Fits ARIMA(5,1,0) on the last ~2 years of SYS closes
  → Predicts close for tomorrow: e.g., 152.3

Step 3 — LSTM:
  → Loads cached lstm.pt for SYS from GCS
  → Feeds the last 60 days of [close, volume] as input sequence
  → Predicts close: e.g., 150.8

Step 4 — best_models.json says ARIMA won for SYS (lower MAPE: 4.2% vs 5.8%)
  → PredictedPrice = 152.3, MAPE = 0.042, Confidence = 1 - 0.042 = 0.958

Step 5 — Forecast score normalization:
  → LastClose = 149.5, PredictedPrice = 152.3
  → expected_pct = (152.3 - 149.5) / 149.5 × 100 = +1.88%
  → forecast_norm = clamp(1.88 / 3.0, -1, +1) = +0.627

Step 6 — News sentiment (last 7 days):
  → 3 direct SYS articles: avg score = +0.28
  → Cement industry articles: avg score = +0.15
  → Macro (IMF/USD): avg score = -0.05
  → Blended = (1.0×0.28 + 0.4×0.15 + 0.2×(-0.05)) / (1.0+0.4+0.2) = +0.214

Step 7 — Technicals:
  → Price vs MA50: +3.2% → score += clamp(3.2/25, -0.4, +0.4) = +0.128
  → Price vs MA200: +8.5% → score += clamp(8.5/50, -0.4, +0.4) = +0.170
  → RSI14: 58 → no extreme adjustment
  → technical_norm = +0.298

Step 8 — Quality scores:
  → Forecast quality = max(0, 1 - 0.042/0.20) = 0.79
  → Sentiment quality = 0.40×(3/30) + 0.40×(3/5) + 0.20×0.214 = 0.04+0.24+0.043 = 0.323
  → Technical quality = 0.30 + 0.30 (MA50) + 0.30 (MA200) = 0.90

Step 9 — Normalize weights:
  → raw: [0.79, 0.323, 0.90] → with floor 0.10: [0.79, 0.323, 0.90]
  → total = 2.013
  → weights: Forecast=39.2%, Sentiment=16.1%, Technicals=44.7%

Step 10 — Divergence damping check:
  → Forecast=+0.627 (extreme, > 0.5)
  → Other avg = (0.214 + 0.298) / 2 = +0.256 (same direction)
  → No damping applied (both positive)

Step 11 — Health Score:
  → 0.392×0.627 + 0.161×0.214 + 0.447×0.298
  → = 0.246 + 0.034 + 0.133 = +0.413
  → Label = GOOD

Step 12 — Directional Classifier:
  → 5d horizon model loaded (best horizon for SYS)
  → 14 features computed for today
  → GBM says 0.68, RF says 0.61, LR says 0.64 → avg = 0.643
  → 0.643 > 0.60 → UP, HIGH confidence
  → HighConfHitRate for SYS 5d = 0.71 (71% accurate historically)

Step 13 — Suggestion:
  → fc_signed = clamp(1.88/3.0, -1, +1) × 0.958 = 0.627 × 0.958 = 0.601
  → blended = 0.5×0.413 + 0.5×0.601 = +0.507
  → effective_dir = UP (expected_pct > 0.30)
  → blended ≥ 0.40 AND direction aligned AND confidence ≥ 90% → STRONG_BUY, HIGH
  → Directional classifier agrees (UP, HIGH, 71%) → confirms HIGH confidence

Step 14 — Stock written to stocks.json:
  {
    "Symbol": "SYS",
    "Health": { "Score": 0.413, "Label": "GOOD", "Weights": {...} },
    "Forecast": { "PredictedPrice": 152.3, "MAPE": 0.042 },
    "Directional": { "Primary": { "LatestDirection": "UP", "HighConfHitRate": 0.71 } },
    "Suggestion": { "Action": "STRONG_BUY", "Confidence": "HIGH" }
  }

Step 15 — Warm-4 uploads stocks.json to Supabase:
  Django management command reads stocks.json → upserts StockSignal table row for SYS
  Mobile app fetches from /api/v1/stocks/SYS/ → sees STRONG_BUY

Step 16 — Notification dispatch (POST_MARKET window):
  SYS is #1 STRONG_BUY by blended_score
  Gemini writes: "SYS shows strong buy signal at 149.5 PKR with 1.9% upside forecast.
   Technicals confirm: price above both MA50 and MA200, RSI healthy at 58."
  Email sent to opted-in users. Push notification sent to registered phones.
```

---

## 8. Summary Table — All Models at a Glance

| Model | Type | Input | Output | Where |
|---|---|---|---|---|
| ARIMA(5,1,0) | Statistical time-series | Historical closes | Next-day + 30-day price | `forecasting.py` |
| LSTM (2-layer, hidden=64) | Deep learning | 60-day OHLCV window | Next-day price | `forecasting.py` |
| FinBERT (`ProsusAI/finbert`) | Pre-trained transformer | Headline + description text | Sentiment score [-1,1] | `sentiment.py` |
| VADER + finance lexicon | Rule-based NLP | Text | Sentiment score [-1,1] | `sentiment.py` (fallback) |
| Technical indicators | Deterministic formulas | Historical OHLCV | RSI, MA20/50/200, volatility | `key_ratios_scraper.py` |
| Directional ensemble (GBM + RF + LR) | Classification | 14 price+volume features | UP/DOWN probability | `directional_classifier.py` |
| Fusion engine | Weighted sum | Forecast score + sentiment + technicals | Health score + label | `fusion.py` |
| Suggestion engine | Rule-based | Health + forecast + directional | BUY/HOLD/SELL + reason | `stock_health.py` |
