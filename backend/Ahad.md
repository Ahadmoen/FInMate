# Ahad.md — FinMate-BE FYP Viva Defense Document

A depth-first walkthrough of the entire FinMate-BE pipeline written for an
oral examination defense. Scope: the data scrapers, the ML stack, model
selection logic, suggestion synthesis, and cloud deployment topology — with
exact file:line refs and the kind of "why this number?" answers a viva
panel asks.

---

## Table of contents

1. [System overview](#1-system-overview)
2. [Scrapers — sources and mechanics](#2-scrapers--sources-and-mechanics)
3. [Forecasting — LSTM vs. ARIMA bake-off](#3-forecasting--lstm-vs-arima-bake-off)
4. [Directional classifier — GBM + RF + LR ensemble](#4-directional-classifier--gbm--rf--lr-ensemble)
5. [Sentiment — FinBERT with VADER fallback](#5-sentiment--finbert-with-vader-fallback)
6. [Fusion — weighted Health score](#6-fusion--weighted-health-score)
7. [Suggestion — final BUY / HOLD / SELL](#7-suggestion--final-buy--hold--sell)
8. [Cloud deployment — GCP topology](#8-cloud-deployment--gcp-topology)
9. [Viva-style Q&A](#9-viva-style-qa)

---

## 1. System overview

FinMate-BE serves a stock-recommendation website for the **Pakistan Stock
Exchange (PSX)** — 738 active tickers. Each ticker gets:

- A daily ML-driven recommendation (`STRONG_BUY` / `BUY` / `HOLD` / `SELL` / `STRONG_SELL`)
- A 1-day price prediction (LSTM or ARIMA, whichever wins the per-symbol bake-off)
- A 30-day forward trend curve (multi-step ARIMA)
- A directional confidence check at 1d / 5d / 20d horizons (GBM+RF+LR ensemble)
- News sentiment (FinBERT) over the last 30 days
- Hourly intraday "current price + change_pct + technicals" snapshot during market hours

Data flows in two cadences:

- **Daily warm chain** at 18:00–18:35 PKT: scrape new bars + news → run cached ML → fuse → push to Supabase.
- **Hourly live chain** Mon–Fri 10:00–15:00 PKT: pull intraday quotes → snapshot replace `live_market_data`.

Plus weekly **cold** retrain on Sundays (full per-ticker LSTM + directional
re-fit) and quarterly fundamentals scrape on the 1st of each quarter.

Languages: **Python 3.13**, **Django 4.2** ORM (only — no views for ML, just
the management commands and Celery tasks that hit the DB).

---

## 2. Scrapers — sources and mechanics

All five scrapers live in [integrations/scrapers/](integrations/scrapers/).
Their `SYMBOLS` list is sourced from `symbols.py` (738 tickers) and
intersected at module load with `active_symbols.json` if present
([integrations/scrapers/symbols.py:741-770](integrations/scrapers/symbols.py#L741-L770))
— this trims to ~673 forecastable tickers for downstream scrapers.

### 2.1 historical_scraper.py — daily OHLCV

- **Source:** the unofficial `psx` PyPI library wrapping
  `dps.psx.com.pk/historical/eod`. Imported as
  `from psx import stocks` ([integrations/scrapers/historical_scraper.py:32](integrations/scrapers/historical_scraper.py#L32))
  and called per-ticker as `stocks(symbol, start, end)` returning a pandas
  DataFrame with `Open / High / Low / Close / Volume`.
- **Incremental mode:** reads existing `historical_data.json` (327 MB),
  finds latest date per ticker, fetches `(latest+1, today)`. First-time /
  cold mode fetches `(2017-01-01, today)`.
- **Per-symbol timeout:** `concurrent.futures.ThreadPoolExecutor(max_workers=1)`
  used purely for **timeout enforcement** (not parallelism). Critical detail:
  we do **not** use `with` block — its `__exit__` blocks on the leaked
  thread. We `shutdown(wait=False, cancel_futures=True)` instead, accepting
  a bounded thread leak ([integrations/scrapers/historical_scraper.py:71-92](integrations/scrapers/historical_scraper.py#L71-L92)).
- **Stale-symbol skip:** any ticker whose latest bar is >30 days old
  in warm mode is skipped — saves the `psx` library's slow month-by-month
  iteration on delisted tickers.
- **Checkpointing:** every 25 symbols, the in-progress dict is written to
  disk so a crash resumes mid-fetch.

### 2.2 news_scraper.py — Google News RSS

- **Source:** `https://news.google.com/rss/search?q={query}&hl=en-PK&gl=PK&ceid=PK:en`
  — Google News' free RSS endpoint, geo-anchored to Pakistan.
- **Per-ticker query:** built from the ticker's company name + aliases
  (e.g. `"Habib Bank Limited" OR "HBL"`).
- **Throttling:** 1.2s sleep + jitter between requests; exponential
  backoff (5 / 10 / 20 / 40 s) on HTTP 429 / 503. Datacenter IPs (Cloud Run)
  occasionally trigger 503; we patiently retry.
- **Recency filter:** keeps articles from last 2 days only — keeps the
  per-run news_data.json bounded; older articles are merged from previous
  runs and pruned to 30 days at ingest time.
- **Output:** `news_data.json` (parsed RSS rows) → fed to sentiment.py.

### 2.3 live_scraper.py — intraday hourly bars

- **Source:** `https://dps.psx.com.pk/timeseries/int/{symbol}` — PSX's
  intraday tick endpoint, returns `[ts, Price, Volume]` rows for the
  current trading session.
- **Concurrency:** `ThreadPoolExecutor(max_workers=5)` — 20 trips PSX's
  per-IP rate limit (RemoteDisconnected on every TCP handshake), 10
  occasionally trips it; 5 is the empirical safe ceiling
  ([integrations/scrapers/live_scraper.py:26-37](integrations/scrapers/live_scraper.py#L26-L37)).
- **Per-thread `requests.Session()`:** TCP+SSL handshake happens once
  per worker, then ~134 requests reuse the keep-alive connection. Cuts
  PSX's perceived load from "673 new connections" to "5 long-lived"
  ([integrations/scrapers/live_scraper.py:43-60](integrations/scrapers/live_scraper.py#L43-L60)).
- **50–250ms jitter** before each request desynchronises the workers.
- **3-tier fallback** when no data:
  1. Live ticks → resample to hourly OHLC, take latest bar.
  2. `last_bars.json` → real prior-day OHLC + Volume + PriorClose for change_pct.
  3. `stocks.json` LastClose → flat O=H=L=C stub, Volume=0 (last-resort).
- **Snapshot mode:** `_ingest_live_data()` wipes `live_market_data` and
  writes 673 fresh rows each hourly run.

### 2.4 key_ratios_scraper.py — technicals + fundamentals

- **Technicals** (computed locally from `historical_data.json`): MA20 / MA50 /
  MA200, RSI14 (Wilder's), 20-day annualised volatility, volume ratio
  (vs 20-day MA). Re-runs daily inside warm-1.
- **Fundamentals** (scraped from PSX company pages
  `https://dps.psx.com.pk/company/{symbol}`): P/E, EPS, Dividend Yield,
  Market Cap, Book Value, Face Value via BeautifulSoup table parsing.
- **Split:** Daily warm-1 sets `KEY_RATIOS_FUNDAMENTALS=0` env var → only
  technicals run. The quarterly job sets `KEY_RATIOS_TECHNICALS=0` →
  only fundamentals run. PSX reports quarterly so daily fundamental
  scrapes were 15-25 min of wasted work.

### 2.5 extract_last_bars.py — auxiliary

Reads `historical_data.json`, takes the last 2 bars per ticker, emits
`last_bars.json` as `{ticker: {Open, High, Low, Close, Volume, Date,
PriorClose}}`. Used by the live scraper as the OHLC fallback when
intraday returns nothing.

---

## 3. Forecasting — LSTM vs. ARIMA bake-off

[ml_services/forecasting.py](ml_services/forecasting.py) — produces
two artifacts: `stocks.json`'s `Forecast` block (1-day winner) and
`forecasting_trend.json` (30-day forward curve).

### 3.1 LSTM architecture

| Param | Value | Why |
|---|---|---|
| Class | `StockLSTM(nn.Module)` ([forecasting.py:69-84](ml_services/forecasting.py#L69-L84)) | Standard PyTorch nn.Module |
| Input features | 4: `close`, `volume`, `ret1`, `ret5` | Price + flow + short-momentum features |
| Hidden size | 64 | Empirical balance of capacity vs. overfit |
| Layers | 2 | Stacked LSTM — first layer extracts short-term, second smooths |
| Dropout | 0.2 between layers | Regularises the recurrent state |
| Lookback window | 60 trading days | ~3 calendar months of history per training sample |
| Optimizer | Adam, lr=0.005 | Adaptive — handles non-stationary financial time series better than SGD |
| Loss | MSELoss | Predicts a continuous next-day return scalar |
| Train/val split | 85/15, **chronological** (no shuffle) | Prevents future-leak; respects time order |
| Max epochs | 100 |  |
| Early stopping | patience=10 on val loss | Stops when val loss hasn't improved for 10 epochs |
| Batch size | 64 |  |
| Output | one scalar = predicted next-day return | Multiplied with last close → predicted price |

### 3.2 ARIMA model

- **Order:** `(5, 1, 0)` — AR(5), one differencing, no MA term
  ([forecasting.py:50](ml_services/forecasting.py#L50)).
- **Why p=5?** PSX intraday autocorrelation typically vanishes within a
  trading week; p=5 captures the previous week's momentum.
- **Why d=1?** Daily closes are I(1) — non-stationary in level but
  stationary in first differences (returns).
- **Why q=0?** PSX volatility is dominated by autoregressive shocks
  (Pakistani retail flow); MA terms add noise without lifting MAPE in
  our backtests.
- **Refit cadence:** every 7 days during walk-forward backtest
  (`ARIMA_REFIT_INTERVAL = 7`) — refitting daily would be too expensive
  for 738 tickers; weekly is the sweet spot.

### 3.3 The bake-off — how "best" is selected

For each ticker, both models run on a **60-day walk-forward backtest**
([forecasting.py:48](ml_services/forecasting.py#L48)) — predict day T+1
from history T, compare to actual T+1 close, slide forward.

- **MAPE formula:** `Σ |actual - pred| / |actual| / count` over the 60-day
  window, computed only on non-zero actuals
  ([forecasting.py:252-256](ml_services/forecasting.py#L252-L256)).
- **Why MAPE not RMSE?** RMSE is dollar-denominated → biases toward
  expensive tickers (LUCK at PKR 408 vs SILK at PKR 1.5). MAPE is
  scale-free → comparable across the universe.
- **Winner:** `best_model = "ARIMA" if arima_mape <= lstm_mape else "LSTM"`
  ([forecasting.py:328-331](ml_services/forecasting.py#L328-L331)).
- **Confidence reported:** `1 - MAPE` — so 96.8% confidence ≈ 3.2% backtest error.
- Selection persists per-ticker in `best_models.json`. Warm runs reuse
  the cold-trained selection without re-running the bake-off (saves
  ~6 hours).

### 3.4 Trend forecast — 30-day forward curve

- **Always ARIMA** (no LSTM trend) — LSTM error compounds aggressively
  on multi-step output (each step's error feeds the next).
- **`statsmodels.ARIMA.forecast(steps=30)`** gives the raw mean curve.
- **Direction labeling per day_ahead** (UP/DOWN/STABLE): cumulative %
  change vs. anchor (today's last close), with a horizon-scaled
  threshold so day 30's prediction needs more conviction than day 1's
  to be labeled non-STABLE
  ([forecasting.py:381-383](ml_services/forecasting.py#L381-L383)).
- Output: 30 rows per ticker → 672 × 30 ≈ 20,160 rows in
  `forecast_trend` table (snapshot mode — replaced daily).

---

## 4. Directional classifier — GBM + RF + LR ensemble

[ml_services/directional_classifier.py](ml_services/directional_classifier.py)
— a **separate** binary classifier (UP=1 / DOWN=0) trained per
(ticker × horizon). Three horizons: 1d, 5d, 20d.

### 4.1 Why a separate classifier?

The forecasting model predicts magnitude (price). This classifier
predicts **direction only** — a simpler binary problem on which we
can require high confidence before acting. Decoupling lets us veto a
borderline forecast when the directional ensemble disagrees.

### 4.2 Feature engineering (lines 63-94)

22 features computed from OHLCV:

- **Multi-horizon returns:** ret_1d, ret_3d, ret_5d, ret_10d, ret_20d, ret_60d
- **MA z-scores:** `(close - MA_n) / std_n` for n ∈ {20, 50, 200}
- **RSI14** (Wilder's smoothing)
- **Volatility:** 10d and 20d rolling std of returns
- **Volume signals:** volume_ratio (vs 20-day MA, clipped 0–5),
  volume z-score (clipped ±5)
- **MACD-like:** `(EMA12 - EMA26) / close`

All standardised with `sklearn.preprocessing.StandardScaler` fit on the
train split only ([directional_classifier.py:159](ml_services/directional_classifier.py#L159)).

### 4.3 The three models

| Model | Hyperparams | Strength |
|---|---|---|
| `GradientBoostingClassifier` | n_estimators=120, max_depth=3, learning_rate=0.05, subsample=0.85 | Captures nonlinear feature interactions |
| `RandomForestClassifier` | n_estimators=200, max_depth=8, min_samples_leaf=15, n_jobs=-1 | Robust to noise + multicollinearity |
| `LogisticRegression` | C=1.0, max_iter=1000 | Linear baseline; calibrates probabilities |

### 4.4 Voting + high-confidence gate

- **Soft voting:** average of three `predict_proba()[:, 1]`
  ([directional_classifier.py:115-119](ml_services/directional_classifier.py#L115-L119)).
- **High-confidence rule:** `|prob - 0.5| >= 0.15` → confidence = HIGH
  ([directional_classifier.py:50](ml_services/directional_classifier.py#L50)).
  In other words: only when ≥65% probability for UP or ≤35% for DOWN do
  we publish a confident call. Below threshold we still emit
  UP/DOWN but flag confidence = LOW.
- Output: `LatestDirection`, `LatestConfidence`, `LatestProbability`,
  plus cold-mode backtest stats (`OverallHitRate`, `HighConfHitRate`).

### 4.5 Per-(ticker, horizon) caching

Each combination gets its own ensemble + scaler at
`integrations/data/models/{SYM}/directional_{1,5,20}d.pkl`. 672 × 3 =
~2,016 small pickles, cached in GCS and downloaded on warm runs.

---

## 5. Sentiment — FinBERT with VADER fallback

[ml_services/sentiment.py](ml_services/sentiment.py)

### 5.1 FinBERT (primary)

- **HuggingFace model:** `ProsusAI/finbert`
  ([sentiment.py:30](ml_services/sentiment.py#L30)) — a BERT-base
  fine-tuned by Prosus on financial news headlines.
- **3-class output:** positive / negative / neutral probabilities.
- **Score mapping:** `compound = prob_positive - prob_negative` ∈ [-1, 1]
  ([sentiment.py:122-124](ml_services/sentiment.py#L122-L124)).
- **Tokenization:** max_length=256, truncation enabled. Headlines are short.
- **Batching:** groups of 16 headlines per forward pass.

### 5.2 VADER fallback

- **Trigger:** FinBERT load fails (no network in container, missing
  weights) OR `SENTIMENT_BACKEND=vader` env var explicitly set
  ([sentiment.py:102-111](ml_services/sentiment.py#L102-L111)).
- **Lexicon overlay:** finance-specific words injected into VADER's
  default lexicon — `downgrade: -3.0`, `fraud: -3.5`, `upgrade: 2.5`,
  `profit: 2.0`, etc. ([sentiment.py:44-57](ml_services/sentiment.py#L44-L57)).
- **Same compound score format** so downstream code is backend-agnostic.

### 5.3 Label bucketing (5-class)

| Compound score | Label |
|---|---|
| [-1.0, -0.6) | VERY_BAD |
| [-0.6, -0.2) | BAD |
| [-0.2, 0.2] | NEUTRAL |
| (0.2, 0.6] | GOOD |
| (0.6, 1.0] | EXCELLENT |

Per-ticker aggregation: average compound across the last 30 days of
articles, with recency weighting (recent articles count more).

---

## 6. Fusion — weighted Health score

[ml_services/fusion.py](ml_services/fusion.py) and
[ml_services/stock_health.py](ml_services/stock_health.py).

### 6.1 Three components

| Component | Source | Range |
|---|---|---|
| `Forecast` | Forecast direction × confidence (1 - MAPE) | [-1, 1] |
| `Sentiment` | Average FinBERT compound, recency-weighted | [-1, 1] |
| `Technicals` | RSI/MA/volume composite signal | [-1, 1] |

### 6.2 Quality-driven dynamic weights

Each component reports a **quality score** ∈ [0, 1]. Weights are
normalised from quality, with a floor of 10% per component
([fusion.py:122-131](ml_services/fusion.py#L122-L131)).

| Component | Quality formula | Why |
|---|---|---|
| Forecast quality | `max(0, 1 - MAPE / 0.20)` ([fusion.py:81-85](ml_services/fusion.py#L81-L85)) | MAPE ≤ 0% → 1.0; MAPE ≥ 20% → 0. Bad forecasts shouldn't dominate. |
| Sentiment quality | weighted blend of `coverage = articles/30`, `recency = recent_7d/5`, `decisiveness = |avg_score|` ([fusion.py:88-101](ml_services/fusion.py#L88-L101)) | A ticker with 0 articles in 30 days gets ~0 sentiment weight |
| Technical quality | 0.30 base + 0.30 if MA50 known + 0.30 if MA200 known + 0.10 if RSI in decisive zone (>70 or <30) ([fusion.py:104-117](ml_services/fusion.py#L104-L117)) | Young tickers without MA200 history can't carry full weight |

**Default weights** when all qualities tie: Forecast 40 / Sentiment 40 /
Technicals 20 ([fusion.py:22-31](ml_services/fusion.py#L22-L31)).

### 6.3 Divergence damping

If `|forecast_score| ≥ 0.5` and the other two components point opposite,
forecast is damped by up to 40% based on the disagreement magnitude
([fusion.py:134-147](ml_services/fusion.py#L134-L147)). Prevents a
bullish ARIMA anomaly from overruling consistent bearish news + technicals.

### 6.4 Final Health score + label

`Health.Score = Σ (weight × component)`, clamped to [-1, 1]. Same 5-class
label bucketing as sentiment (VERY_BAD … EXCELLENT) keyed off Score.

Also reported in `stocks.json` for diagnostics:

- `Components` — raw per-component scores (used + raw)
- `Quality` — per-component quality
- `Weights` — final normalised weights actually applied
- `Contributions` — % of final |Score| each component drove (e.g.
  `{Forecast: 69.76, Sentiment: 15.41, Technicals: 14.83}`)
- `PrimaryDriver` — which component had max contribution

---

## 7. Suggestion — final BUY / HOLD / SELL

[ml_services/stock_health.py:242-413](ml_services/stock_health.py#L242-L413)

This is where Health.Score, the forecast, and the directional classifier
combine into the value users actually see.

### 7.1 Three derived metrics

| Metric | Formula | Interpretation |
|---|---|---|
| `ForecastSignedScore` | `clip(expected_pct / 3.0, -1, 1) × forecast_confidence` ([stock_health.py:270](ml_services/stock_health.py#L270)) | A ±3% predicted move scaled to ±1, then weighted by forecast confidence |
| `BlendedScore` | `0.5 × Health.Score + 0.5 × ForecastSignedScore` ([stock_health.py:275](ml_services/stock_health.py#L275)) | Equal blend of fused-quality view and forecast-only view |
| `SignalStrength` | `max(|Health.Score|, |ForecastSignedScore|)` ([stock_health.py:276](ml_services/stock_health.py#L276)) | "How loud is the loudest signal?" |

### 7.2 Decision thresholds

```
if blended >= 0.40 and aligned UP and forecast_conf >= 0.90 → STRONG_BUY
elif blended >=  0.15 and effective_dir = UP and no contradiction → BUY
elif blended <= -0.40 and aligned DOWN and forecast_conf >= 0.90 → STRONG_SELL
elif blended <= -0.15 and effective_dir = DOWN and no contradiction → SELL
else → HOLD
```

### 7.3 Directional classifier modifier

If the directional classifier's `HighConfHitRate ≥ 55%` and its current
prediction has confidence=HIGH, two adjustments fire:

- **Veto:** if direction disagrees with the action, downgrade BUY/SELL → HOLD.
- **Upgrade:** if direction agrees, the action keeps and `Suggestion.Confidence`
  is upgraded to HIGH.

This is the role of `Suggestion.DirectionalCheck.Horizon` — which of
the 1d / 5d / 20d horizons backed the call.

### 7.4 News veto

A final guard ([stock_health.py:320-327](ml_services/stock_health.py#L320-L327)):

- BUY / STRONG_BUY downgraded to HOLD if average sentiment ≤ -0.30
- SELL / STRONG_SELL downgraded to HOLD if average sentiment ≥ +0.30

Even when the math says BUY, if recent news is decisively negative we
back off — protects against ML latency on breaking events (a fraud
allegation will hit news before it shows in price).

### 7.5 What the user sees

The `stocks.json` row for one ticker:

```json
{
  "Symbol": "HBL",
  "LastClose": 282.87,
  "Forecast": {"Model": "LSTM", "Direction": "UP", "Confidence": 0.968,
               "MAPE": 0.032, "PredictedPrice": 285.12, "ExpectedChangePct": 0.79},
  "Health": {"Score": 0.42, "Label": "GOOD", "Contributions": {...},
             "Weights": {...}, "PrimaryDriver": "Forecast"},
  "Suggestion": {"Action": "BUY", "Confidence": "HIGH",
                 "BlendedScore": 0.41, "ForecastSignedScore": 0.39,
                 "SignalStrength": 0.42,
                 "DirectionalCheck": {"Horizon": 5, "Direction": "UP", "Confidence": "HIGH"}}
}
```

Frontend renders the **`Suggestion.Action`** as the primary call, with
`Suggestion.Confidence` as the badge.

---

## 8. Cloud deployment — GCP topology

Project: `venom-scent-476112`. Region: `us-central1`.

### 8.1 Components

| Service | Purpose |
|---|---|
| **Artifact Registry** | Holds `pipeline:latest` Docker image |
| **GCS bucket `etl_b`** | Models, JSONs, pipeline outputs |
| **Cloud Run Jobs** | All compute (warm × 4, cold, live, quarterly) |
| **Cloud Scheduler** | Cron triggers for all jobs |
| **Secret Manager** | Holds Supabase `DATABASE_URL` |
| **Supabase (Postgres)** | Frontend's data plane |

### 8.2 GCS layout

```
gs://etl_b/
  ├── historical_data.json                  (327 MB, daily-incremental)
  ├── models/
  │     ├── lstm/{SYMBOL}.pt                (PyTorch state_dicts, ~5 KB each)
  │     └── directional/{SYMBOL}_{1,5,20}d.pkl  (sklearn pickles)
  └── outputs/
        ├── stocks.json                     (2.2 MB — the master)
        ├── forecasting_trend.json          (4.5 MB — 30-day curves)
        ├── news_sentiment.json
        ├── news_data.json
        ├── stock_forecasts.json
        ├── best_models.json
        ├── directional_signals.json
        ├── daily_ratios.json
        ├── fundamental_ratios.json
        ├── live_data.json
        ├── active_symbols.json             (filter for unforecastable)
        └── last_bars.json                  (live-stub OHLC fallback)
```

Lifecycle rule: `models/` cleaned of objects > 14 days old to control
storage cost.

### 8.3 Cloud Run Jobs

| Job | Cron (UTC) | PKT time | CPU/RAM | Timeout | Purpose |
|---|---|---|---|---|---|
| `finmate-warm-1-scrape-hist` | `0 13 * * *` | 18:00 daily | 2 / 4 GiB | 60 min | Historical + technicals scrape |
| `finmate-warm-2-scrape-news` | `0 13 * * *` | 18:00 daily (parallel with warm-1) | 2 / 4 GiB | 90 min | Google News + FinBERT |
| `finmate-warm-3-ml-fuse` | `30 13 * * *` | 18:30 daily | 4 / 8 GiB | 90 min | Warm forecasting + fusion |
| `finmate-warm-4-ingest` | `35 13 * * *` | 18:35 daily | 1 / 1 GiB | 30 min | Migrate + Supabase bulk-ingest |
| `finmate-cold` | `0 21 * * 6` | Sunday 02:00 PKT | 4 / 8 GiB | 24 hours | Full retrain (LSTM + directional) |
| `finmate-live` | `0 5,6,7,8,9,10 * * 1-5` | Mon-Fri 10:00–15:00 PKT | 1 / 1 GiB | 5 min | Hourly intraday snapshot |
| `finmate-quarterly-fundamentals` | `0 21 1 1,4,7,10 *` | 1st of Jan/Apr/Jul/Oct, 02:00 PKT | 1 / 1 GiB | 60 min | EPS / P/E / DivYield refresh |

### 8.4 Warm chain (the critical path)

```
finmate-warm-1-scrape-hist  ┐
finmate-warm-2-scrape-news  ├─ parallel at 18:00 PKT
                            │
                            ▼ (both finish by 18:25)
finmate-warm-3-ml-fuse  at 18:30 PKT
                            │
                            ▼ (finish by 18:34)
finmate-warm-4-ingest   at 18:35 PKT
                            │
                            ▼
                   Supabase up-to-date
```

Each subtask reads its inputs from GCS and writes its outputs back to
GCS — so a failed warm-3 doesn't lose warm-1's scraping work. warm-4
also auto-applies pending Django migrations before ingesting (self-
healing on schema drift, [bin/run_warm_4_ingest.sh](bin/run_warm_4_ingest.sh)).

### 8.5 Image build

```
gcloud builds submit \
  --tag us-central1-docker.pkg.dev/venom-scent-476112/finmate/pipeline:latest \
  --project=venom-scent-476112 --timeout=3600
```

Single image serves all jobs — only the entrypoint script (`bin/run_*.sh`)
differs. Today's image is **v22**; 22 rebuilds since the cloud cutover.

### 8.6 Cost (steady state)

| Item | Estimate / month |
|---|---|
| Cloud Run — warm × 30 (~10 min, 2 vCPU, 8 GiB) | $2.00 |
| Cloud Run — cold × 4 (~8 hr, 4 vCPU, 8 GiB) | $3.50 |
| Cloud Run — live × 120 (~3 min, 1 vCPU, 1 GiB) | $0.40 |
| GCS storage (3.5 GB) | $0.07 |
| GCS Class A ops (~700 writes / month) | $0.04 |
| GCS egress (~10 GB / month) | $1.20 |
| Cloud Scheduler (8 jobs) | $0 (free tier ≤ 3; over by 5 = $1) |
| Artifact Registry (1 GB image) | $0.10 |
| **Total** | **~$8 / month** |

---

## 9. Viva-style Q&A

### Q1. Why two forecasting models? Why not pick one and tune it?

LSTM is excellent at capturing nonlinear short-term patterns when given
enough history, but on PSX many tickers have only ~2 years of data —
not enough for LSTM to outperform classical statistics. ARIMA(5,1,0)
is a well-understood baseline that beats LSTM on the small-data
tickers. Per-symbol bake-off lets us pick the right tool ticker by
ticker rather than imposing one assumption.

### Q2. Why MAPE for the bake-off?

MAPE is scale-free. RMSE on PSX would punish high-priced tickers
(LUCK at 408 PKR) much more than penny stocks (SILK at 1.5 PKR), even
when both have the same percentage error. We need a metric that's
comparable across the universe to pick a single winner.

### Q3. The directional classifier predicts the same direction as the
forecasting model. Isn't it redundant?

No — they answer different questions. Forecasting predicts a *price* (a
regression problem) — getting the direction right is incidental. The
directional classifier predicts only *direction* (a classification
problem) — much easier to optimise, much easier to require high
confidence on. Decoupling lets us veto a borderline forecast when the
directional ensemble disagrees, without conflating "I'm 70% sure it
goes up" with "I predict price 285.12".

### Q4. Why not LightGBM / XGBoost / Transformer?

LightGBM/XGBoost would likely give comparable accuracy to GBM at
faster training, but the marginal gain is small versus the
complexity of adding a non-stdlib dependency to ~700 per-ticker
pickles. Transformers would need 10× more data per ticker than PSX
provides. Our ensemble gives three orthogonal perspectives (boosted
trees, bagged trees, linear) for ~12s training time per (ticker,
horizon) — pragmatic for the data regime.

### Q5. How do you handle non-stationarity? Stocks fundamentally drift.

ARIMA differences once (`d=1`) — operates on returns, not levels.
LSTM trains on standardised features (`StandardScaler` fit on train
set only — not the full series, no leak). Walk-forward backtest
re-fits ARIMA every 7 days and re-evaluates the bake-off, so the
selected model adapts to regime change. A weekly cold retrain
re-fits everything from scratch.

### Q6. Why 60 days of LSTM lookback specifically?

Three months ≈ one quarter of trading. Longer windows (180 days)
forced the LSTM to "learn" PSX's pattern of holiday clustering that
doesn't transfer. Shorter windows (20 days) lost most of the
structural signal. 60 was the sweet spot in our hyperparameter
sweep.

### Q7. FinBERT was trained on US earnings transcripts. How well does
it transfer to Pakistani news?

It's imperfect — Pakistani financial vocabulary (e.g. "circular debt",
"super tax", "rupee liquidity") isn't in its training distribution.
We mitigate by:
1. Using FinBERT only for the 3-class probability (positive/negative/neutral).
2. The compound score then aggregates over 30 days of articles, so a
   single mis-tokenized headline can't move the needle.
3. VADER + finance-lexicon overlay is the fallback for environments
   where FinBERT can't load.

A future improvement would be fine-tuning FinBERT on a labelled
PSX news corpus, but we don't have one.

### Q8. The fusion weights are 40/40/20. How did you pick those?

The static defaults are heuristic (forecast and sentiment are roughly
co-equal predictive sources, technicals are confirmatory not
predictive). But the *applied* weights are dynamic — derived from
per-component quality scores at run time. A ticker with 0 articles
and a 25% MAPE forecast will get its sentiment dropped to the floor
(10%), forecast dropped from 40% toward 10%, and technicals will
pick up the residual.

### Q9. Why snapshot mode for `live_market_data` instead of accumulating
intraday history?

The frontend shows "current price + change_pct + last technicals"
on the stock detail page — single-row-per-ticker. Accumulating
hourly bars would be 6 × 673 × 22 trading days = ~89k rows / month
just for chart history nobody queries (the chart is on
`forecast_trend` and `historical_data.json`). Snapshot keeps DB at a
constant ~673 rows. If we ever need intraday charting we add a
separate `intraday_history` table — keeps concerns clean.

### Q10. What stops PSX from rate-limiting your Cloud Run live scraper?

Nothing technically — they did, repeatedly. Three stacked mitigations:
1. **Per-thread `requests.Session()`** — TCP+SSL handshake reuse cuts
   our perceived load from 673 new connections to 5 long-lived ones.
2. **5 worker concurrency** + 50–250 ms jitter — desyncs the workers
   so PSX never sees N simultaneous handshakes.
3. **Three-tier fallback** in the scraper — when PSX *does* drop us
   anyway, we fall back to the last-real-bar OHLC from
   `last_bars.json` instead of writing a zero. The frontend always
   sees a complete dataset.

### Q11. How would you scale this to NASDAQ (8000+ tickers)?

Three changes:
1. **Sharding**: split `SYMBOLS` into N shards, run N parallel
   Cloud Run Job tasks (Cloud Run Jobs supports `--parallelism`).
2. **A real broker API** instead of scraping (Polygon, IEX) — pay for
   licensed data, eliminates rate-limit risk.
3. **Component pipeline**: Pub/Sub between scrape → ML → ingest,
   so the ML doesn't block on the slowest scraper. Today's
   sequential warm-1..4 chain works because PSX is small enough.

### Q12. Walk me through the data flow for a single recommendation.

1. **18:00 PKT, warm-1**: PSX historical scraper fetches today's bar
   for HBL → appended to `historical_data.json`. Technicals
   recomputed from full series → MA20/50/200, RSI14, etc.
2. **18:00 PKT, warm-2 in parallel**: Google News scrapes "Habib
   Bank Limited" — finds 3 articles. FinBERT scores them: +0.62,
   -0.10, +0.45 → average +0.32 → label GOOD.
3. **18:30 PKT, warm-3**: forecasting.py loads cached LSTM for HBL,
   predicts next-day return = +0.79%. ARIMA also runs, MAPE
   compared on backtest — LSTM wins. directional_classifier.py
   predicts `5d direction = UP, prob = 0.71` → confidence HIGH.
4. **fusion.py** combines: forecast_score = 0.79% × confidence 0.97
   = +0.63 weighted; sentiment_score = +0.32; technical_score = +0.18.
   Quality-weighted dynamic weights applied → Health.Score = 0.42 →
   Label = GOOD.
5. **stock_health.py** computes BlendedScore = 0.41,
   ForecastSignedScore = 0.39, SignalStrength = 0.42. Threshold
   matches BUY. Directional classifier's UP at HIGH confidence on
   5d horizon agrees → upgrade Suggestion.Confidence to HIGH.
6. **18:35 PKT, warm-4**: `manage.py migrate` (no-op), then
   `_ingest_stocks()` upserts the row in `stock_signal`,
   `stock_forecast`, `stock_technicals`. ~30 seconds.
7. **Frontend** queries `GET /api/core/signals/HBL/` →
   `{signal: "BUY", confidence: 0.42, suggestion_confidence: "HIGH",
   blended_score: 0.41, ...}`.

End-to-end: ~35 minutes from scrape kick-off to user-visible call,
fully unattended, every day at 18:00 PKT.

---

## Repository pointers

- ML modules: [ml_services/](ml_services/)
- Scrapers: [integrations/scrapers/](integrations/scrapers/)
- Cloud entrypoints: [bin/](bin/)
- Django models: [core/models.py](core/models.py)
- Migrations: [core/migrations/](core/migrations/)
- Cloud topology: [infrastructure.md](infrastructure.md)
- Schema cleanup history: [post_deployment_change.md](post_deployment_change.md)

Push: `origin = github.com:Ahadmoen/FinMate-BE`
+ `upstream = github.com:Mubashir1920/FinMate-BE`,
both on branch `scraper-fixes-forecasting-sentiment`.
