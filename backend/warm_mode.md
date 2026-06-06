# Warm Mode — Daily Incremental Refresh

The two heavy ML stages — forecasting and directional classifier —
each support a `--warm` flag that loads cached model artifacts and
runs inference only. No retraining. Per-symbol cost drops by roughly
two orders of magnitude.

| Stage                                | Cold (per symbol) | Warm (per symbol) |
| ------------------------------------ | ----------------- | ----------------- |
| `ml_services.forecasting`            | ~30–40 s          | ~0.5 s            |
| `ml_services.directional_classifier` | ~5–8 s            | ~0.1 s            |

For a 600-symbol universe that's the difference between a 7-hour
overnight retrain and a ~10-minute daily refresh.

---

## How it works

Cold mode (the default) trains every model from scratch and saves the
trained artifact per symbol to:

```
integrations/data/models/{SYMBOL}/
    lstm.pt                   # state_dict + (mu, sigma) for normalization
    directional_1d.pkl        # GBM + RF + LR + scaler for the 1-day horizon
    directional_5d.pkl        # …5-day…
    directional_20d.pkl       # …20-day…
```

Warm mode loads those artifacts and runs inference only:

- **Forecasting (warm):** load cached LSTM weights + cached normalization
  stats, run a single forward pass on the lookback window ending at the
  most recent close. ARIMA is refit from scratch each warm run because
  fitting is cheap (~1–3 s per symbol) and not worth caching. Result:
  one new prediction row appended to `stock_forecasts.json`. The MAPE /
  Best_Model summary is reused verbatim from the prior cold run — the
  trained model's accuracy estimate is a property of the model, not of
  any single one-step prediction.

- **Directional classifier (warm):** load cached ensemble + scaler per
  horizon, predict the latest probability. Update the
  `LatestProbability` / `LatestDirection` / `LatestConfidence` fields
  in `directional_signals.json`. All hit-rate / coverage stats are
  preserved from the prior cold run — those describe the trained model,
  not today's call.

Symbols without a cached artifact silently fall back to cold mode for
that symbol — so the first run after adding new tickers still works,
just slower for the ones that need a cold train.

---

## Running it

```bash
# Cold — full retrain. Run weekly, or on demand when symbol coverage
# changes, or when you want fresh backtest stats.
.venv/bin/python -m ml_services.forecasting
.venv/bin/python -m ml_services.directional_classifier

# Warm — daily incremental refresh. Requires a prior cold run to have
# populated the cache. Falls back per-symbol to cold for any symbol
# without an artifact.
.venv/bin/python -m ml_services.forecasting --warm
.venv/bin/python -m ml_services.directional_classifier --warm
```

After the warm runs, rebuild `stocks.json` as usual:

```bash
.venv/bin/python -m ml_services.stock_health
```

---

## Recommended daily schedule

The pipeline schedule in [`pipeline_flow.md`](pipeline_flow.md) is the
heavyweight cold-run schedule. The warm-mode equivalent looks like this:

| When            | Step                                            | Mode  | Purpose                                  |
| --------------- | ----------------------------------------------- | ----- | ---------------------------------------- |
| Weekly (Sun)    | `forecasting` + `directional_classifier`        | cold  | Refresh model weights + backtest stats.  |
| 17:30 PKT daily | `historical_scraper.main()`                     | —     | Append today's daily bars.               |
| 18:00 PKT daily | `news_scraper.main()`                           | —     | Pull headlines.                          |
| 18:05 PKT daily | `key_ratios_scraper.main()`                     | —     | Recompute technicals + fundamentals.     |
| 18:30 PKT daily | `ml_services.forecasting --warm`                | warm  | Append today's prediction row.           |
| 18:32 PKT daily | `ml_services.directional_classifier --warm`     | warm  | Refresh latest directional signal.       |
| 18:35 PKT daily | `ml_services.sentiment.main()`                  | —     | Score yesterday's news.                  |
| 18:40 PKT daily | `ml_services.stock_health.main()`               | —     | Fuse everything → `stocks.json`.         |

---

## Cache invalidation

There is no automatic invalidation — the cache is overwritten only when
cold mode runs. That's intentional: warm mode never silently retrains.

When to force a cold run:

- **Code changed** in `forecasting._train_lstm`, `_build_features`,
  `directional_classifier.build_features`, or `_train_ensemble`.
- **Symbol's recent MAPE** in `best_models.json` drifts noticeably from
  the model's claimed MAPE — usually a sign the symbol regime shifted.
- **New symbol** with no cache (handled automatically — falls back to
  cold for that symbol on the next warm run).
- **Scheduled weekly refresh** (recommended cadence).

To wipe a single symbol's cache and force a cold rebuild on next run:

```bash
rm -rf integrations/data/models/UBL
```

To wipe everything:

```bash
rm -rf integrations/data/models
```
