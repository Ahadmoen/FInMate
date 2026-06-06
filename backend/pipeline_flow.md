# Pipeline Flow — Scrape → Score → Fuse → Ingest

End-to-end walkthrough of how a number ends up in `stocks.json` and then
in Supabase. Read this together with:

- [`infrastructure.md`](infrastructure.md) — production cloud topology (Jobs, schedulers, IAM, costs)
- [`how_works.md`](how_works.md) — daily timeline, recovery cookbook, where to find things in Console
- [`warm_mode.md`](warm_mode.md) — cold-vs-warm modes for ML modules
- [`cloud_link.md`](cloud_link.md) — every GCP Console deep-link in one place
- [`table_schemas_info.md`](table_schemas_info.md) — column-by-column reference for every JSON

---

## TL;DR

```
                        ┌─────────────────────┐
                        │  registry_scraper   │   monthly  →  symbols.py (738 tickers)
                        └──────────┬──────────┘
                                   │
       ┌───────────────────────────┼───────────────────────────────────┐
       │                           │                                   │
       ▼                           ▼                                   ▼
   historical_              news_scraper                       live_scraper
   scraper                  (Google News, throttled)           (PSX intraday)
    │                          │                                       │
    ▼                          ▼                                       ▼
   historical_data.json    news_data.json                       live_data.json
       │                       │
       ├───→ key_ratios_scraper                                         │
       │       │                                                        │
       │       ▼                                                        │
       │     daily_ratios.json + fundamental_ratios.json                │
       │                                                                │
       ├───→ ml_services.forecasting   (cold: train LSTM + ARIMA        │
       │       │                        warm: load cached LSTM, predict│
       │       ▼                        only today's bar)               │
       │     stock_forecasts.json + best_models.json + forecasting_trend.json
       │                                                                │
       ├───→ ml_services.directional_classifier (cold: train ensemble; │
       │       │                                  warm: load cached)   │
       │       ▼                                                        │
       │     directional_signals.json                                   │
       │                                                                │
       └───→ ml_services.sentiment    (FinBERT, with VADER fallback)   │
               │                                                        │
               ▼                                                        │
             news_sentiment.json                                        │
                                                                        │
                                ↓
                  ml_services.stock_health
                  computes per-component QUALITY scores,
                  applies divergence DAMPING on forecast,
                  derives DYNAMIC WEIGHTS, fuses → Health + Suggestion.
                                ↓
                  integrations/data/stocks.json (672 ranked symbols)
                                ↓
                  python manage.py load_ml_outputs          ← friend's code
                                ↓
                  Supabase tables (StockSymbol, MarketDataCache,
                  StockForecast, StockSignal, NewsSentiment, LiveMarketData)
                                ↓
                            Website
```

**Where each piece runs in production:**

```
  Cloud Scheduler (cron)              Cloud Run Job          GCS bucket etl_b
  ──────────────────────              ─────────────          ────────────────
  finmate-warm-daily   18:30 PKT  →   bin/run_warm.sh        models/  +
  finmate-cold-weekly  Sun 02:00  →   bin/run_cold.sh        outputs/  +
  finmate-live-hourly  10:00–15:00 →  bin/run_live.sh        historical_data.json
```

Each Cloud Run Job container does the **whole** pipeline end-to-end:
download from GCS → scrape → ML → fuse → ingest to Supabase via friend's
`load_ml_outputs` → upload back to GCS → exit. Friend's website only
reads Supabase, never GCS directly.

Locally the pipeline is also runnable as plain Python modules — each
reads the previous one's JSON from `integrations/data/`. That's the
fallback path for development and the path the laptop bootstrap used to
populate GCS the first time.

---

## Stage 1 — Symbol registry

**Module:** [`integrations/scrapers/registry_scraper.py`](integrations/scrapers/registry_scraper.py)
**Cadence:** monthly
**Reads:** `https://dps.psx.com.pk/symbols` (the official PSX listing).
**Writes:** [`integrations/scrapers/symbols.py`](integrations/scrapers/symbols.py).

**What it does**
1. Fetches every PSX-listed equity (currently 738).
2. Preserves the **20 hand-curated entries** (CURATED set in
   `registry_scraper.py`) verbatim — those have hand-tuned aliases and
   keywords.
3. Re-derives every non-curated entry from the listing on each run:
   `name`, `industry` (from PSX `sectorName`), and a clean keyword pool
   (industry tokens + the full company name; **no name fragments and no
   abbreviation noise** — the user explicitly asked for that).
4. Rebuilds `GLOBAL_KEYWORDS` and `GENERAL_QUERIES` from a curated
   baseline plus one set per non-curated PSX sector.

**Why it matters:** every downstream module iterates `SYMBOLS` from this
file. The monthly run keeps the universe up to date with new listings
without losing the curated metadata.

---

## Stage 2 — Raw data scraping

Three independent scrapers, all driven by `SYMBOLS` from Stage 1. Each
honors `SCRAPER_LIMIT=N` for dev runs.

### 2a. Historical OHLCV

**Module:** [`integrations/scrapers/historical_scraper.py`](integrations/scrapers/historical_scraper.py)
**Cadence:** daily, after market close (PKT).
**Reads:** PSX historical endpoint via the local `psx` package.
**Writes:** `integrations/data/historical_data.json`.

**Incremental by default:** for each symbol the scraper looks up the
latest date already in `historical_data.json` and fetches only
`(latest + 1 day) → today`. Symbols that are already up to date are
skipped; symbols with no existing data get a full backfill from
`FULL_BACKFILL_START` (2000-01-01). Pass `--full` to force a full
re-backfill for every symbol. Merged with the existing file on
`(Symbol, Date)`.

### 2b. Intraday hourly bars

**Module:** [`integrations/scrapers/live_scraper.py`](integrations/scrapers/live_scraper.py)
**Cadence:** hourly during market hours (PKT).
**Reads:** `https://dps.psx.com.pk/timeseries/int/{SYMBOL}`.
**Writes:** `integrations/data/live_data.json`.

Resamples the day's tick stream to 1-hour OHLCV bars; skips a symbol if
its session date is stale (i.e. delisted or halted).

### 2c. News

**Module:** [`integrations/scrapers/news_scraper.py`](integrations/scrapers/news_scraper.py)
**Cadence:** daily.
**Reads:** Google News RSS — per-symbol queries (`name OR ticker OR alias`)
plus the macro queries in `GENERAL_QUERIES`.
**Writes:** `integrations/data/news_data.json`.

Deduped on `(Symbol, Link)`. Each article carries the keyword pool that
matched its title + description, plus the publisher.

### 2d. Key ratios (technicals + fundamentals)

**Module:** [`integrations/scrapers/key_ratios_scraper.py`](integrations/scrapers/key_ratios_scraper.py)
**Cadence:** daily, **after** the historical scrape.
**Reads:** `historical_data.json` (computes technicals) +
`https://dps.psx.com.pk/company/{SYMBOL}` (best-effort fundamentals).
**Writes:** `daily_ratios.json` (technicals) + `fundamental_ratios.json`
(snapshot fundamentals; `Reports[]` left empty pending PDF extraction
from PSX annual / quarterly filings).

Technicals: `MA20`, `MA50`, `MA200`, `RSI14`, 20-day annualized
volatility, volume vs 20-day avg, price-vs-MA50 % and price-vs-MA200 %.

---

## Stage 3 — ML pipeline

### 3a. Forecasting

**Module:** [`ml_services/forecasting.py`](ml_services/forecasting.py)
**Reads:** `historical_data.json`.
**Writes:** `stock_forecasts.json` + `best_models.json` + `forecasting_trend.json`.
**Cache:** per-symbol LSTM weights at `integrations/data/models/{SYM}/lstm.pt`
(written in cold mode, loaded in warm mode — see [`warm_mode.md`](warm_mode.md)).

**Two modes:**

- **Cold** (`python -m ml_services.forecasting`) — full retrain. Trains a
  fresh LSTM per symbol, runs the 60-day backtest, picks best model.
  ~30-40 sec per symbol; ~6-7 hr for 672 symbols. Used weekly.
- **Warm** (`--warm`) — loads the cached LSTM, predicts only today's
  bar, appends one row to `stock_forecasts.json`. ~0.5 sec per symbol;
  ~10 sec for 672 symbols. Used daily.

For each symbol with at least `MIN_HISTORY` (≈ 180) closes:

**Backtest — 60-day walk-forward, 1-step-ahead per day:**

1. Split history into train (everything before the last 60 closes) and
   test (the last 60).
2. **ARIMA(5,1,0)** is fit on train, then walk forward 1 step at a time
   over the test slice — refit every `ARIMA_REFIT_INTERVAL=7` days,
   appending the *actual* close (not the prediction) to history each
   step.
3. **LSTM** is a 2-layer network (64 hidden, dropout 0.2, lookback 60)
   trained on a 4-feature input: `(close, volume, 1d return, 5d return)`,
   z-normalized per symbol. Trained once on train data with an 85/15
   chronological train/val split, early stopping (`patience=10`) on
   val loss. Walk-forward predictions use a sliding window over the
   actual previous values.
4. Both models' MAPE computed against the 60-day test closes.
5. Lower-MAPE model becomes `Best_Model`; per-day `Forecasting_Best` /
   `Direction_Best` are written alongside the per-model columns.
6. Per-symbol summary appended to `best_models.json`.

**Trend forecast — 30 business days from the latest close:**

1. Refit ARIMA on the *full* history (no holdout) and forecast
   `FUTURE_HORIZON=30` business days ahead.
2. Output rows go to `forecasting_trend.json` with `PredictedClose`,
   `Direction` (vs the previous predicted close), `DaysAhead`, and
   `BasedOnLastClose`.
3. ARIMA is used regardless of which model won the backtest —
   autoregressive LSTM accumulates error too fast over 30 days. ARIMA
   itself decays toward the long-run mean past day ~10, so treat the
   first week as the strong signal and the back half as directional bias.

### 3a-bis. Directional classifier

**Module:** [`ml_services/directional_classifier.py`](ml_services/directional_classifier.py)
**Reads:** `historical_data.json`.
**Writes:** `directional_signals.json`.
**Cache:** per-(symbol, horizon) ensemble + scaler at
`integrations/data/models/{SYM}/directional_{1,5,20}d.pkl`.

**Two modes** (mirrors forecasting):

- **Cold** — trains the GBM + RF + LR ensemble per (symbol, horizon).
  ~5-8 sec per symbol; ~1 hr for 631 qualifying symbols. Refreshes
  hit-rate stats. Used weekly.
- **Warm** (`--warm`) — loads cached ensemble, refreshes only the
  `LatestProbability` / `LatestDirection` / `LatestConfidence` fields.
  Hit-rate stats preserved from the last cold run.
  ~0.1 sec per symbol; ~5 sec for 631. Used daily.

A separate, purpose-built model whose loss function rewards directional
accuracy (binary classification) instead of magnitude (regression).
Trained per symbol at three horizons (1, 5, 20 days).

**Pipeline:**
1. Build 15 lookback-only features per day: multi-lag returns
   (1, 3, 5, 10, 20, 60 days), MA20/50/200 z-scores, RSI14, 10/20-day
   volatility, volume ratio + z-score, MACD-norm.
2. Drop the first 200 rows (MA200 warmup) and the last `BACKTEST_DAYS +
   horizon` rows (held out for evaluation).
3. Train an ensemble — `GradientBoostingClassifier` + `RandomForest` +
   `LogisticRegression` — and average the three predicted probabilities.
4. Walk-forward evaluate on the held-out 60 days. Report:
   - **Overall hit rate** — accuracy on every test day.
   - **High-confidence hit rate** — accuracy on days where
     `|p − 0.5| ≥ 0.10` (i.e. the classifier was decisive).
   - **High-confidence coverage** — fraction of test days that were decisive.
5. Predict today's class probability for the live signal.

**Honest accuracy ranges (60-day backtest, 631 PSX symbols, 2026-05-02 cold run):**

| Horizon | Aggregate overall | Aggregate high-conf | Coverage |
|---------|-------------------|--------------------|--------|
| 1d      | ~50–55 %          | ~50 %              | ~10 %    |
| 5d      | ~48–50 %          | ~52 %              | ~12 %    |
| 20d     | ~50–55 %          | ~55 %              | ~30 %    |

Best per-symbol high-conf hit rates regularly exceed 80 % at low
coverage — those are the (symbol, horizon) pairs where Suggestion can
lean confidently. The classifier is not a magic oracle on aggregate,
but the long tail of high-trust rows is what makes it useful.

`stock_health.py` picks the best-trust horizon per symbol (highest
`HighConfHitRate` at ≥ 20 % coverage) as the `Directional.Primary` and
uses it to confirm or veto Suggestion calls — see Stage 4d.

### 3b. Sentiment

**Module:** [`ml_services/sentiment.py`](ml_services/sentiment.py)
**Reads:** `news_data.json`.
**Writes:** `news_sentiment.json`.

Default backend: **FinBERT** (`ProsusAI/finbert`) — a BERT model
fine-tuned on financial news. It returns three class probabilities;
we collapse them into a continuous compound score with
`compound = pos_prob − neg_prob` (range `[-1, 1]`), then bucket into
`VERY_BAD / BAD / NEUTRAL / GOOD / EXCELLENT`. Each output row carries
`SentimentScore`, `Sentiment`, and `SentimentBackend` so downstream
consumers know which model produced the score.

If FinBERT can't be loaded (no network, model not on disk), the module
falls back automatically to VADER + a small finance-specific lexicon
overlay so the pipeline still runs in offline / minimal environments.
Set `SENTIMENT_BACKEND=vader` to force the fallback even when FinBERT
is available — useful for fast local testing.

---

## Stage 4 — Fusion (the adaptive part)

This is the heart of the system. Implemented in
[`ml_services/fusion.py`](ml_services/fusion.py); driven from
[`ml_services/stock_health.py`](ml_services/stock_health.py).

For every symbol we have three component scores in `[-1, 1]`:

| Component  | Source                                                                                                           |
| ---------- | ---------------------------------------------------------------------------------------------------------------- |
| Forecast   | `(predicted_price - last_close) / last_close * 100`, clipped to `±5 %` then rescaled to `±1`.                    |
| Sentiment  | Mean `SentimentScore` of every article for the symbol.                                                           |
| Technicals | `technical_score_from()` — combines price-vs-MA50 / price-vs-MA200 with RSI extremes, clipped to `[-1, 1]`.      |

### 4a. Per-component **Quality** (drives the weights)

Each component also carries a quality score in `[0, 1]` reflecting how
much we trust *this signal for this symbol right now*. This is the key
to the per-stock dynamic-weighting behavior.

| Component  | Quality formula                                                                                          |
| ---------- | -------------------------------------------------------------------------------------------------------- |
| Forecast   | `clip(1 - MAPE / 0.20, 0, 1)`. MAPE 0 % → 1.0; MAPE ≥ 20 % → 0.                                          |
| Sentiment  | `0.4·min(articles/30, 1) + 0.4·min(recent7d/5, 1) + 0.2·|avg_score|`.                                    |
| Technicals | `0.3 (base) + 0.3·has_MA50 + 0.3·has_MA200 + 0.1·(RSI < 30 or > 70)`.                                    |

Sparse news? Sentiment quality drops. No 200-day history? Technical
quality drops. Sloppy backtest? Forecast quality drops.

### 4b. Dynamic weight derivation

```
weight_i = max(quality_i, 0.10)        # 10% floor — never silent
weights  = weight_i / sum(weight_j)    # normalize to sum = 1
```

The floor (`WEIGHT_FLOOR = 0.10`) means even a low-quality signal still
votes. Without it, a symbol with zero news would have `Sentiment` weight
of 0 and the system couldn't course-correct if news suddenly arrived.

### 4c. Forecast divergence damping

Triggers only when:

```
|forecast_score| ≥ 0.5            (forecast is taking a strong stance)
AND  forecast_score · ((sentiment + technicals)/2) < 0   (opposite signs)
```

Disagreement strength is `min(|forecast - other_avg|, 2.0) / 2.0`,
clipped to `[0, 1]`. The damping factor is

```
factor = 1 - 0.40 · disagreement      ∈ [0.60, 1.0]
```

i.e. up to a 40 % proportional cut. The damped forecast then enters the
weighted sum. Both the raw and damped values are surfaced in
`Health.ComponentsRaw` and `Health.Components`.

This is the reality-check guard the user asked for: a wildly bullish
ARIMA can't override clearly negative news + technicals, and vice versa.

### 4d-i. Directional classifier as Suggestion modifier

After the fusion produces a `Health` block, `stock_health._make_suggestion`
pulls in the directional classifier's `Primary` horizon for the symbol
and uses it to either:

- **Upgrade** Suggestion confidence to HIGH when the classifier's live
  call is also HIGH-confidence AND its historical hit rate ≥ 55 % AND
  it agrees with the action's direction.
- **Veto** a BUY/SELL down to HOLD when the classifier disagrees with
  the action AND meets the same trust bar.

The full snapshot of the classifier signal used (`Direction`,
`Confidence`, `HitRate`, `Horizon`) is preserved in
`Suggestion.DirectionalCheck` for transparency.

### 4d. Putting it together

```python
weights              = normalize(qualities, floor=0.10)
forecast_used, damp  = maybe_dampen(forecast, sentiment, technicals)
overall              = sum(w_i · component_used_i)
contributions_pct    = |w_i · component_used_i| / Σ|w_j · component_used_j| · 100
primary_driver       = argmax(contributions_pct)
label                = bucket(overall) ∈ VERY_BAD..EXCELLENT
```

Every one of those numbers is written into the symbol's `Health` block.

---

## Stage 5 — Final assembly

**Module:** [`ml_services/stock_health.py`](ml_services/stock_health.py)
**Reads:** every JSON in stages 2–4, plus `symbols.py` for company meta.
**Writes:** `integrations/data/stocks.json` (672 ranked symbols on
2026-05-02 cold run).

For each symbol it produces one row containing seven blocks:

| Block         | Source                                                      |
| ------------- | ----------------------------------------------------------- |
| identity      | `Symbol`, `Name`, `Industry` from `symbols.py`.             |
| `LastClose`   | Last row in `historical_data.json` for the ticker.          |
| `Forecast`    | `Best_Model` + price + `ExpectedChangePct` + `Confidence`.  |
| `News`        | Aggregated sentiment block (count, recency, distribution).  |
| `Ratios`      | Mirror of `Technicals` + `Fundamentals` for the ticker.     |
| `Directional` | All horizons + chosen Primary from the classifier.          |
| `Health`      | Output of `compute_fusion(...)` (see Stage 4).              |
| `Suggestion`  | BUY/HOLD/SELL action + confidence + reason + classifier check. |

Rows are sorted by `Health.Score` descending — top of the file is the
healthiest symbol.

---

## Stage 6 — Ingestion to Supabase

**Module:** [`integrations/management/commands/load_ml_outputs.py`](integrations/management/commands/load_ml_outputs.py) (Django management command, owned by Wasif)
**Reads:** `integrations/data/stocks.json` + `news_sentiment.json` + `live_data.json` + `symbols.py`.
**Writes:** Supabase tables — `stock_symbol`, `market_data_cache`,
`stock_forecast`, `stock_signal`, `news_sentiment`, `live_market_data`.

Inside the same Cloud Run container that produced the JSONs, this
command reads them from local disk and upserts into Supabase. **No
separate ingestion process** — the pipeline and the ingestion live in
one Job invocation.

| Supabase table | Source | Mode |
|---|---|---|
| `stock_symbol` | `stocks.json` (per row) + `symbols.py` (catalog) | upsert by ticker |
| `market_data_cache` | `stocks.json` Ratios.Technicals + LastClose | upsert by ticker (today's snapshot) |
| `stock_forecast` | `stocks.json` Forecast block | upsert by (ticker, forecast_date, model_used) |
| `stock_signal` | `stocks.json` Health block (label → BUY/HOLD/SELL via `LABEL_TO_SIGNAL`) | **append-only** with `valid_until = next 06:00 PKT`; the website queries the latest unexpired row per ticker |
| `news_sentiment` | `news_sentiment.json` | dedup by `link` |
| `live_market_data` | `live_data.json` | upsert by (ticker, date) |

The same `_ingest_*()` helpers from
[`integrations/tasks.py`](integrations/tasks.py) are used at finer
granularity for incremental refreshes (e.g. `hourly_refresh()` calls
only `_ingest_live_data()`).

---

## Worked example — ENGRO

Numbers from the most recent run.

| Stage              | Value                                                                |
| ------------------ | -------------------------------------------------------------------- |
| Last close         | `485.38`                                                             |
| ARIMA forecast     | `424.72` (predicted next close)                                      |
| Expected change    | `-12.50 %` → forecast component score `-1.00` (clipped at `±1`)      |
| ARIMA backtest MAPE| `5.75 %` → forecast quality `1 - 0.0575/0.20 = 0.71`                 |
| News articles      | 100 (5 recent), avg sentiment `+0.13` → sentiment quality `0.83`     |
| Technicals         | Price `+31.9 %` over MA50, `+41.6 %` over MA200, RSI 65 → `+0.80`    |
| Technical quality  | full history + non-extreme RSI → `0.90`                              |
| Dynamic weights    | Forecast `0.29`, Sentiment `0.34`, Technicals `0.37`                 |
| Damping?           | Yes — forecast `-1.0` disagrees with `+0.47` (avg of S+T) → factor `0.71` |
| Forecast (damped)  | `-0.71`                                                              |
| Weighted sum       | `0.29·-0.71 + 0.34·0.13 + 0.37·0.80 = +0.13`                         |
| Label              | `NEUTRAL`                                                            |
| Contributions      | Forecast 37.8 %, Sentiment 8.1 %, **Technicals 54.1 %**              |
| Primary driver     | **Technicals**                                                       |

Without damping and without quality-driven weights (i.e. the old
`0.5·F + 0.5·S` logic), ENGRO would have landed at `-0.43` (BAD) on the
strength of the bearish forecast alone. The adaptive logic correctly
recognized that the price is well above its long-term trend and that
news is supportive, and tempered the forecast accordingly.

---

## Orchestration (production — cloud)

In production the daily warm pipeline is split into **4 chained Cloud
Run Jobs** (`finmate-warm-1`..`-4`), plus weekly cold and hourly live
Jobs. Each Job is one-shot — runs to completion, exits, no idle billing.
See [`infrastructure.md`](infrastructure.md) for the full runtime
contract (per-job memory/CPU/timeout, IAM, costs).

| When (PKT)             | Cloud Run Job  | Entrypoint               | What |
|------------------------|----------------|--------------------------|------|
| **18:00 daily** *(parallel)* | `finmate-warm-1-scrape-hist` | [`bin/run_warm_1_scrape_hist.sh`](bin/run_warm_1_scrape_hist.sh) | historical_scraper + key_ratios_scraper |
| **18:00 daily** *(parallel)* | `finmate-warm-2-scrape-news` | [`bin/run_warm_2_scrape_news.sh`](bin/run_warm_2_scrape_news.sh) | news_scraper (today/yesterday filter) + sentiment FinBERT |
| **18:30 daily** *(after #1+#2)* | `finmate-warm-3-ml-fuse` | [`bin/run_warm_3_ml_fuse.sh`](bin/run_warm_3_ml_fuse.sh) | forecasting + directional (warm) + stock_health |
| **18:35 daily** *(after #3)* | `finmate-warm-4-ingest` | [`bin/run_warm_4_ingest.sh`](bin/run_warm_4_ingest.sh) | `python manage.py load_ml_outputs` → Supabase |
| **02:00 Sunday**       | `finmate-cold` | [`bin/run_cold.sh`](bin/run_cold.sh) | Weekly cold retrain — full ML retrain + new models uploaded to GCS (~7-10 hr) |
| **Hourly 10:00–15:00, Mon-Fri** | `finmate-live` | [`bin/run_live.sh`](bin/run_live.sh) | Intraday hourly bars only — `live_scraper` + `_ingest_live_data()` |

The 4 warm subtasks share state via GCS — each uploads its outputs to
`gs://etl_b/outputs/`, the next stage downloads them. End-to-end warm
latency is **~35-45 min** (parallel scrapers dominate).

Every step is idempotent — re-running any subtask produces the same
Supabase rows. `stock_signal` uses snapshot mode (delete-by-ticker
before insert); other tables upsert by their natural keys.

## Orchestration (local dev — fallback)

The whole pipeline still runs as plain Python modules from the project
root, no cloud needed. Useful for debugging or one-off cold runs.

```bash
# scrapers
.venv/bin/python -m integrations.scrapers.historical_scraper
.venv/bin/python -m integrations.scrapers.key_ratios_scraper
.venv/bin/python -m integrations.scrapers.news_scraper
# ML
.venv/bin/python -m ml_services.forecasting              # cold
# .venv/bin/python -m ml_services.forecasting --warm     # daily warm
.venv/bin/python -m ml_services.directional_classifier   # cold
# .venv/bin/python -m ml_services.directional_classifier --warm
.venv/bin/python -m ml_services.sentiment
.venv/bin/python -m ml_services.stock_health
# friend's ingestion
.venv/bin/python manage.py load_ml_outputs               # needs DATABASE_URL
```

Or use the all-in-one launcher (mirrors what Cloud Run does, minus the
GCS sync):

```bash
./scripts/run_full_cold.sh
```

---

## Where to tune things

| Knob                          | File                                                                | Default          | What changes                                                  |
| ----------------------------- | ------------------------------------------------------------------- | ---------------- | ------------------------------------------------------------- |
| Forecast horizon              | `forecasting.BACKTEST_DAYS`                                         | 7                | Backtest length.                                              |
| LSTM retrain threshold        | `forecasting.RETRY_MAPE_THRESHOLD`                                  | 0.05             | When the bigger LSTM gets a second pass.                      |
| Sentiment lexicon             | `sentiment.FINANCE_LEXICON`                                         | curated          | Add finance terms that VADER misses.                          |
| Sentiment buckets             | `sentiment.LABELS`                                                  | 5 ranges         | Move the boundaries between `VERY_BAD…EXCELLENT`.             |
| Health weight floor           | `fusion.WEIGHT_FLOOR`                                               | 0.10             | Minimum voice each component keeps.                           |
| Damping trigger / max         | `fusion.DAMPING_TRIGGER_MAGNITUDE`, `fusion.MAX_DAMPING`            | 0.5, 0.40        | When and how hard to dampen extreme forecasts.                |
| Quality formulas              | `forecast_quality_from`, `sentiment_quality_from`, `technical_quality_from` | as documented | Bias which signal gets more weight by default.                |
| Component score formulas      | `technical_score_from` (and the inline forecast/sentiment normalizers in `stock_health.py`) | — | Change how raw numbers map to the `[-1, 1]` axis.             |

Every knob is in **one file** with **named constants at the top** —
that's the maintenance contract.
