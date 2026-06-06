# Table & JSON Schemas — File-by-File Reference

Every JSON file produced by the scrapers and ML services lives in
`integrations/data/`. Each is a flat **list of records** (one row per dict)
unless noted. This doc lists every column, the producer module, and the
matching Django/Postgres table where applicable.

---

## `historical_data.json`

**Producer:** [`integrations/scrapers/historical_scraper.py`](integrations/scrapers/historical_scraper.py)
**Source:** PSX historical OHLCV via the local `psx` package.
**Cadence:** Daily (cron / Celery beat).
**Maps to table:** *(no Django model yet — backfill candidate; pair with
`MarketDataCache` for latest-only access.)*

| Column   | Type    | Notes                                |
| -------- | ------- | ------------------------------------ |
| `Symbol` | string  | PSX ticker (`OGDC`, `HBL`, …).       |
| `Date`   | ISO-8601| Trading date (no time component).    |
| `Open`   | float   | PKR.                                 |
| `High`   | float   | PKR.                                 |
| `Low`    | float   | PKR.                                 |
| `Close`  | float   | PKR.                                 |
| `Volume` | float   | Shares traded.                       |

Idempotency: deduped on `(Symbol, Date)`.

---

## `live_data.json`

**Producer:** [`integrations/scrapers/live_scraper.py`](integrations/scrapers/live_scraper.py)
**Source:** `https://dps.psx.com.pk/timeseries/int/{SYMBOL}` (today's intraday ticks).
**Cadence:** Hourly during market hours.
**Maps to table:** `MarketDataCache` (latest only) — would need a new
hourly bars table for full history.

Same shape as `historical_data.json` but hourly bars in PKT (`Date` carries
the time component, e.g. `2026-04-28T12:00:00+05:00`).

Idempotency: deduped on `(Symbol, Date)` (where `Date` is the hour bucket).

---

## `news_data.json`

**Producer:** [`integrations/scrapers/news_scraper.py`](integrations/scrapers/news_scraper.py)
**Source:** Google News RSS — per-symbol queries built from
`COMPANIES[symbol].name` + aliases, plus the macro queries in
`GENERAL_QUERIES`.
**Cadence:** Daily.
**Maps to table:** seed for `NewsSentiment` (after running sentiment).

| Column           | Type    | Notes                                                                                       |
| ---------------- | ------- | ------------------------------------------------------------------------------------------- |
| `Symbol`         | string  | Ticker, or `"GENERAL"` for macro query rows.                                                |
| `Date`           | ISO-8601| `pubDate` from RSS, normalized to UTC.                                                      |
| `Heading`        | string  | Article title (publisher suffix stripped).                                                  |
| `Link`           | URL     | RSS link.                                                                                   |
| `Keywords`       | list    | Subset of the symbol's keyword pool that appeared in the text.                              |
| `KeywordContext` | list    | Sentences from the title/desc that contained one of the keywords.                           |
| `Market`         | string  | `COMPANIES[symbol].industry` for symbol rows; the bucket label for macro rows.              |
| `Platform`       | string  | RSS `<source>` (publisher).                                                                 |
| `Sentiment`      | null    | Placeholder; filled in by sentiment.py downstream.                                          |

Idempotency: deduped on `(Symbol, Link)`.

---

## `news_sentiment.json`

**Producer:** [`ml_services/sentiment.py`](ml_services/sentiment.py)
**Input:** `news_data.json`.
**Cadence:** Daily after news scrape.
**Maps to table:** `NewsSentiment` (in `core/models.py`).

Same fields as `news_data.json` plus:

| Column           | Type   | Notes                                                                       |
| ---------------- | ------ | --------------------------------------------------------------------------- |
| `Sentiment`      | string | One of `VERY_BAD`, `BAD`, `NEUTRAL`, `GOOD`, `EXCELLENT`.                   |
| `SentimentScore` | float  | Raw VADER compound score in `[-1, 1]` (with finance-lexicon overlay).       |

Bucket boundaries:

| Score range  | Label       |
| ------------ | ----------- |
| `[-1, -0.6)` | `VERY_BAD`  |
| `[-0.6, -0.2)` | `BAD`     |
| `[-0.2, 0.2)`  | `NEUTRAL` |
| `[0.2, 0.6)`   | `GOOD`    |
| `[0.6, 1]`     | `EXCELLENT` |

Latest run: 3,088 articles, distribution: VERY_BAD 89, BAD 422, NEUTRAL 1457, GOOD 844, EXCELLENT 276.

---

## `stock_forecasts.json`

**Producer:** [`ml_services/forecasting.py`](ml_services/forecasting.py)
**Input:** `historical_data.json`.
**Cadence:** Daily after historical scrape.
**Maps to table:** `StockForecast` (in `core/models.py`) — *two rows per
(Symbol, Date)* on the consumer side, one for `model_used="ARIMA"` and one
for `model_used="LSTM"`.

| Column              | Type    | Notes                                                      |
| ------------------- | ------- | ---------------------------------------------------------- |
| `Symbol`            | string  | Ticker.                                                    |
| `Date`              | ISO-8601| Backtest day (one of last `BACKTEST_DAYS=60` closes — 1-step-ahead walk-forward). |
| `Close`             | float   | Actual close on `Date`.                                    |
| `Forecasting_ARIMA` | float\|null | ARIMA(5,1,0) prediction for `Date`.                    |
| `Forecasting_LSTM`  | float\|null | Tiny PyTorch LSTM prediction for `Date`.               |
| `Forecasting_Best`  | float\|null | Same value as the model named in `Best_Model`.         |
| `Best_Model`        | string  | `"ARIMA"` or `"LSTM"` — winner by lowest backtest MAPE.   |
| `Direction_ARIMA`   | string  | `UP` / `DOWN` / `STABLE` from previous actual close.       |
| `Direction_LSTM`    | string  | Same.                                                      |
| `Direction_Best`    | string  | Same.                                                      |

Idempotency: 7 rows × N symbols on every run; overwritten in place.

---

## `forecasting_trend.json`

**Producer:** [`ml_services/forecasting.py`](ml_services/forecasting.py)
**Inputs:** `historical_data.json` (uses *all* available history; no holdout).
**Cadence:** Daily, alongside the backtest.
**Maps to table:** *(no Django model yet — candidate for a `StockTrendForecast`
model later, or simply expose via API as derived data.)*

Multi-step forward forecast, **30 business days** from the last available
close. ARIMA(5,1,0) is used regardless of which model won the backtest —
multi-step autoregressive LSTM forecasts compound error too quickly to
trust over a 30-day horizon.

| Column              | Type    | Notes                                                      |
| ------------------- | ------- | ---------------------------------------------------------- |
| `Symbol`            | string  | Ticker.                                                    |
| `Date`              | ISO     | Future business day (skip weekends).                       |
| `PredictedClose`    | float   | ARIMA forecast for that date in PKR.                       |
| `Direction`         | string  | `UP` / `DOWN` / `STABLE` vs the previous predicted close.  |
| `Model`             | string  | Always `"ARIMA"` for now — see note above.                 |
| `BasedOnLastClose`  | float   | The close anchoring this forecast (latest in history).     |
| `DaysAhead`         | int     | Calendar days ahead of `BasedOnLastClose` date.            |

Caveat: ARIMA's multi-step forecast decays toward the long-run mean
within 5–10 steps, so the further out you go, the flatter the line. Use
the first 5–7 days as the primary signal; treat days 15–30 as
"directional bias" rather than a precise price.

---

## `best_models.json`

**Producer:** [`ml_services/forecasting.py`](ml_services/forecasting.py) (sidecar to `stock_forecasts.json`).
**Cadence:** Same as forecasting.
**Maps to table:** *(no DB model — pure ops/audit. Surface via an API
endpoint if frontend needs it.)*

| Column         | Type   | Notes                                                                                |
| -------------- | ------ | ------------------------------------------------------------------------------------ |
| `Symbol`       | string | Ticker.                                                                              |
| `ARIMA_MAPE`   | float  | MAPE in fraction (e.g. `0.0091` = 0.91%).                                            |
| `LSTM_MAPE`    | float  | Same scale.                                                                          |
| `Best_Model`   | string | Winner by min MAPE.                                                                  |
| `Best_MAPE`    | float  | `min(ARIMA_MAPE, LSTM_MAPE)`.                                                        |
| `LSTM_Retried` | bool   | `true` when both initial MAPEs exceeded `RETRY_MAPE_THRESHOLD` and a bigger LSTM ran.|

Latest run: 19 symbols, ARIMA wins 18, LSTM wins 1 (LUCK), 2 retries.

---

## `directional_signals.json`

**Producer:** [`ml_services/directional_classifier.py`](ml_services/directional_classifier.py)
**Inputs:** `historical_data.json`.
**Cadence:** Daily.
**Maps to table:** *(no Django model yet — surface via API or fold into a
future `StockDirectionalSignal` model.)*

A purpose-built UP/DOWN classifier (GradientBoosting + RandomForest +
LogisticRegression ensemble on 15 engineered features). Trained per
symbol, evaluated at horizons 1, 5, and 20 days.

Top-level shape: `[{Symbol, Horizons: {1d: {...}, 5d: {...}, 20d: {...}}}]`

Each horizon record:

| Field                  | Type    | Notes                                                                                     |
| ---------------------- | ------- | ----------------------------------------------------------------------------------------- |
| `Horizon`              | int     | Days ahead being predicted.                                                               |
| `OverallHitRate`       | float   | Direction accuracy on every backtest day (60-day walk-forward).                           |
| `HighConfHitRate`      | float\|null | Accuracy when the classifier is decisive (`|p − 0.5| ≥ 0.10`). `null` if no decisive day. |
| `HighConfCoverage`     | float   | Fraction of backtest days the classifier was decisive.                                    |
| `LatestProbability`    | float   | Today's predicted probability the price goes UP over `Horizon` days.                     |
| `LatestDirection`      | string  | `UP` or `DOWN` (sign of `LatestProbability − 0.5`).                                       |
| `LatestConfidence`     | string  | `HIGH` or `LOW` (HIGH iff `|p − 0.5| ≥ 0.10`).                                            |
| `BacktestDays`         | int     | Number of test days used (60 minus horizon).                                              |

Realistic accuracy ranges (60-day backtest):
- 1-day: aggregate ~52 %; per-symbol best ~69 % (NESTLE).
- 5-day: aggregate ~48 %; per-symbol best ~63 % (PSO).
- 20-day: aggregate ~47 %; per-symbol best 100 % at 18 % coverage (DGKC).

The system surfaces a chosen "Primary" horizon per symbol (the one with
the best HighConfHitRate at ≥ 20 % coverage) inside `stocks.json`.

---

## `daily_ratios.json`

**Producer:** [`integrations/scrapers/key_ratios_scraper.py`](integrations/scrapers/key_ratios_scraper.py)
**Inputs:** `historical_data.json` (technicals are computed, not fetched).
**Cadence:** Daily, after the historical scrape.
**Maps to table:** *(no Django model yet — surface via API or fold into a
future `StockTechnicals` model.)*

One row per symbol, latest values only.

| Path                          | Type   | Notes                                                              |
| ----------------------------- | ------ | ------------------------------------------------------------------ |
| `Symbol`                      | string | Ticker.                                                            |
| `Updated`                     | ISO    | When the row was computed (UTC).                                   |
| `Technicals.Close`            | float  | Latest close.                                                      |
| `Technicals.MA20`             | float  | 20-day simple moving average.                                      |
| `Technicals.MA50`             | float  | 50-day SMA.                                                        |
| `Technicals.MA200`            | float  | 200-day SMA (null if `<200` history).                              |
| `Technicals.RSI14`            | float  | 14-day relative strength index.                                    |
| `Technicals.Volatility20d`    | float  | Annualized 20-day stddev of daily returns.                         |
| `Technicals.VolumeRatio`      | float  | Latest volume / 20-day avg volume.                                 |
| `Technicals.PriceVsMA50Pct`   | float  | `(close - MA50) / MA50 * 100`. Sign tells you above / below trend. |
| `Technicals.PriceVsMA200Pct`  | float  | Same vs MA200.                                                     |

---

## `fundamental_ratios.json`

**Producer:** [`integrations/scrapers/key_ratios_scraper.py`](integrations/scrapers/key_ratios_scraper.py)
**Inputs:** PSX dps company page (`https://dps.psx.com.pk/company/{SYMBOL}`),
best-effort HTML parse.
**Cadence:** Daily (cheap to refresh).
**Maps to table:** *(no Django model yet — candidate for a `StockFundamentals`
model later.)*

| Path                       | Type        | Notes                                                                          |
| -------------------------- | ----------- | ------------------------------------------------------------------------------ |
| `Symbol`                   | string      | Ticker.                                                                        |
| `Updated`                  | ISO         | When fetched.                                                                  |
| `Snapshot.PE`              | float\|null | P/E. `null` when the dps page didn't surface it (frequent — page is partly JS-rendered). |
| `Snapshot.EPS`             | float\|null | Earnings per share.                                                            |
| `Snapshot.DividendYield`   | float\|null | Most-recent dividend yield.                                                    |
| `Snapshot.MarketCap`       | float\|null | Market cap.                                                                    |
| `Snapshot.BookValue`       | float\|null | Book value per share.                                                          |
| `Snapshot.FaceValue`       | float\|null | Face value per share.                                                          |
| `Reports`                  | list        | Per-report ratios (annual / quarterly). **Empty for now** — needs PDF extraction from PSX announcements. |

The `Reports` list is the extension point. Each future row should be of
shape `{Period: "Annual 2024" \| "Q1 2025", Ratios: {...}}` once an
extractor is wired up.

---

## `stocks.json`

**Producer:** [`ml_services/stock_health.py`](ml_services/stock_health.py)
**Inputs:** `historical_data.json`, `stock_forecasts.json`, `best_models.json`,
`news_sentiment.json`, `daily_ratios.json`, `fundamental_ratios.json`, plus
`integrations/scrapers/symbols.py` for company meta.
**Cadence:** Last step in the daily pipeline.
**Maps to table:** *(no DB model yet — this is the API-friendly merged view.
Suggested next step: a `StockSnapshot` Django model keyed on
`(symbol, snapshot_date)` storing the same shape.)*

One row per symbol, sorted by `Health.Score` descending.

| Path                         | Type          | Notes                                                                                                                          |
| ---------------------------- | ------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `Symbol`                     | string        | Ticker.                                                                                                                        |
| `Name`                       | string        | From `COMPANIES[symbol].name`.                                                                                                 |
| `Industry`                   | string        | From `COMPANIES[symbol].industry`.                                                                                             |
| `LastClose`                  | float         | Most recent close from historical data.                                                                                        |
| `Forecast.Model`             | string        | `Best_Model` for that symbol (`ARIMA` or `LSTM`).                                                                              |
| `Forecast.PredictedPrice`    | float         | Latest backtest day's `Forecasting_Best`.                                                                                      |
| `Forecast.ExpectedChangePct` | float         | `(predicted - last_close) / last_close * 100`.                                                                                 |
| `Forecast.Direction`         | string        | `UP` / `DOWN` / `STABLE`.                                                                                                      |
| `Forecast.MAPE`              | float         | `Best_MAPE` from sidecar.                                                                                                      |
| `Forecast.Confidence`        | float         | `1 - MAPE`, clamped to `[0, 1]`.                                                                                               |
| `News.Articles`              | int           | Total articles for this ticker.                                                                                                |
| `News.Recent7d`              | int           | Articles in the last 7 days.                                                                                                   |
| `News.AvgSentimentScore`     | float         | Mean `SentimentScore` across all articles.                                                                                     |
| `News.Distribution`          | dict[str,int] | Counts per 5-class label.                                                                                                      |
| `News.DominantSentiment`     | string        | Argmax of `Distribution`.                                                                                                      |
| `Ratios.Technicals`          | dict          | Mirror of `daily_ratios.json` `Technicals` block.                                                                              |
| `Ratios.Fundamentals`        | dict          | Mirror of `fundamental_ratios.json` `Snapshot`.                                                                                |
| `Ratios.Reports`             | list          | Mirror of `fundamental_ratios.json` `Reports` (empty for now).                                                                 |
| `Directional.Horizons`       | dict          | Mirror of `directional_signals.json` `Horizons` for this symbol — all 3 horizons (1d/5d/20d).                                  |
| `Directional.Primary`        | dict          | The best-trust horizon (highest `HighConfHitRate` at ≥ 20 % coverage). Use this when surfacing a directional signal in the UI. |
| `Health.Score`               | float         | Fused score in `[-1, 1]`. Computed in [`ml_services/fusion.py`](ml_services/fusion.py).                                        |
| `Health.Label`               | string        | Same 5-class buckets as sentiment.                                                                                             |
| `Health.Components`          | dict          | Component scores **after** divergence damping: `{Forecast, Sentiment, Technicals}`, each in `[-1, 1]`.                         |
| `Health.ComponentsRaw`       | dict          | Component scores **before** damping. Equal to `Components` when no damping applies.                                            |
| `Health.Quality`             | dict          | Per-component trust score in `[0, 1]` (forecast: from MAPE; sentiment: coverage / recency / decisiveness; technicals: history depth / RSI extremity). Drives the dynamic weights. |
| `Health.Weights`             | dict          | **Per-stock dynamic weights** derived by normalizing `Quality` (with a `WEIGHT_FLOOR=0.10` so no signal goes fully dark).      |
| `Health.Contributions`       | dict          | Per-component % share of the total absolute weighted score. Sums to 100. Tells you which signal moved the needle most.        |
| `Health.PrimaryDriver`       | string        | Argmax of `Contributions`. `Forecast` / `Sentiment` / `Technicals`.                                                            |
| `Health.ForecastDamping`     | float         | `1.0` = no damping; `< 1.0` = forecast was tempered because it strongly disagreed with the average of sentiment + technicals.  |
| `Suggestion.Action`          | string        | `STRONG_BUY` / `BUY` / `HOLD` / `SELL` / `STRONG_SELL`. Derived in `stock_health._make_suggestion`.                            |
| `Suggestion.Confidence`      | string        | `HIGH` / `MEDIUM` / `LOW`. Upgraded when classifier confirms forecast direction.                                               |
| `Suggestion.Reason`          | string        | One-line human-readable explanation suitable for the UI.                                                                       |
| `Suggestion.BlendedScore`    | float         | `0.5 × HealthScore + 0.5 × ForecastSignedScore` — primary decision metric.                                                     |
| `Suggestion.ForecastSignedScore` | float     | `clip(ExpectedChangePct/3, ±1) × ForecastConfidence` — accuracy-weighted forecast.                                            |
| `Suggestion.ForecastMAPE`    | float         | Backtest MAPE of the model used for this symbol.                                                                               |
| `Suggestion.ForecastConfidence` | float      | `1 − MAPE`, clamped.                                                                                                            |
| `Suggestion.AlignedSignals`  | bool          | True when fused score, forecast direction, and effective direction agree.                                                      |
| `Suggestion.ContradictingSignals` | bool     | True when health score and forecast-signed score have opposite signs above noise.                                              |
| `Suggestion.DirectionalCheck` | dict\|null   | Snapshot of the directional classifier's primary call (Direction, Confidence, HitRate, Horizon) used to confirm or veto.       |

---

## `model_results.ipynb`

**Producer:** Manual / executed via `jupyter execute --inplace`.
**Inputs:** `stock_forecasts.json`, `best_models.json`.
**Purpose:** Side-by-side accuracy comparison (per-symbol MAPE + RMSE
table, headline averages, actual-vs-predicted plots for top-4 / worst-4).
**Outputs:** Embedded in the notebook itself (committed with results).

---

## Cross-reference: which file feeds which Django model

| Django model (in `core/models.py`) | Fed by                                                |
| ---------------------------------- | ----------------------------------------------------- |
| `MarketDataCache`                  | `live_data.json` (latest row per symbol).             |
| `StockForecast`                    | `stock_forecasts.json` (one row per model_used).      |
| `NewsSentiment`                    | `news_sentiment.json`.                                |
| `StockSymbol`                      | `integrations/scrapers/symbols.py` (registry scraper).|
| *(no model)* `StockSnapshot` candidate | `stocks.json` — health view; build the model when API consumers need it. |

Wiring sketch (Django ORM bulk-load for `StockForecast` + `NewsSentiment`)
lives in [`wasif_April28.md`](wasif_April28.md).
