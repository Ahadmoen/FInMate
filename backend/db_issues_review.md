# FinMate Backend — Database Issues Review
**Date:** 2026-05-04
**Prepared by:** Wasif Haider
**For:** Ahad (Lead)

---

## Overview

During the DB integration of the ML pipeline outputs into Supabase, four issues were identified across the Django models and data ingestion logic. These issues relate to incorrect data sourcing, table design problems, data duplication, and missing fields. Each issue is described below with its current state, impact, and recommended fix.

---

## Issue 1 — `StockSignal` Table Is Using the Wrong Data Source

### Current State
The `StockSignal` table stores the final BUY/SELL/HOLD recommendation that gets shown to users and triggers alerts. Currently the ingestion code (`load_ml_outputs.py` and `tasks.py`) reads the signal from `Health.Label` in `stocks.json` and maps it to a signal value using a hardcoded `LABEL_TO_SIGNAL` dictionary:

```python
LABEL_TO_SIGNAL = {
    "EXCELLENT": "STRONG_BUY",
    "GOOD":      "BUY",
    "NEUTRAL":   "HOLD",
    "BAD":       "SELL",
    "VERY_BAD":  "STRONG_SELL",
}
signal = LABEL_TO_SIGNAL.get(health.get("Label"))
```

### What It Should Be
`stocks.json` already has a `Suggestion` block which is the final, processed recommendation produced by `stock_health.py` **after** the directional classifier has confirmed or vetoed the signal:

```json
"Suggestion": {
  "Action": "BUY",
  "Confidence": "HIGH",
  "Reason": "Forecast UP +1.4% (97% confidence, MAPE 2.8%) + GOOD consensus, blended score +0.39.",
  "BlendedScore": 0.3865,
  "ForecastSignedScore": 0.4381,
  ...
}
```

The `Suggestion.Action` field (`STRONG_BUY`, `BUY`, `HOLD`, `SELL`, `STRONG_SELL`) is the correct field to use. It is the end result of the full pipeline including:
1. Forecast score
2. Sentiment score
3. Technical score
4. Divergence damping
5. Directional classifier veto/upgrade

### Impact
By using `Health.Label` we are bypassing the directional classifier's final veto/upgrade step entirely. The whole purpose of the directional classifier is to be the last check — if we skip it, it contributes nothing to the signal shown to users or sent as alerts.

Additionally, `Suggestion` provides richer fields we are missing:
- `Suggestion.Reason` — a human-readable explanation suitable for the UI (e.g. "All three signals aligned...")
- `Suggestion.BlendedScore` — the numeric decision metric
- `Suggestion.ForecastSignedScore` — accuracy-weighted forecast score

Currently `reason` is being manually constructed from `Health` weights which is less informative than the ready-made `Suggestion.Reason`.

### Recommended Fix
In both `load_ml_outputs.py` and `tasks.py`, replace:

```python
# Current (wrong)
signal = LABEL_TO_SIGNAL.get(health.get("Label"))
confidence = abs(health.get("Score", 0.0))
forecast_score = components.get("Forecast", 0.0)
reason = f"Primary driver: {primary_driver}. Forecast weight..."
```

With:

```python
# Correct
action = suggestion.get("Action", "")
confidence = abs(suggestion.get("BlendedScore", 0.0))
forecast_score = suggestion.get("ForecastSignedScore", 0.0)
reason = suggestion.get("Reason", "")
```

---

## Issue 2 — `MarketDataCache` Table Has No Clear Purpose

### Current State
`MarketDataCache` was originally designed as a fast single-row price lookup per ticker. It currently stores two completely unrelated types of data:

**Price fields** (updated hourly from `live_data.json`):
- `open_price`, `current_price`, `high`, `low`, `volume`, `change_pct`, `fetched_at`

**Technical indicator fields** (updated daily from `stocks.json`):
- `rsi14`, `ma20`, `ma50`, `ma200`, `volatility20d`, `volume_ratio`, `eps`

### Why This Is a Problem

**Concern 1 — Duplication with `LiveMarketData`:**
We already have a `LiveMarketData` table that stores all hourly bars for today's session with `open_price`, `high`, `low`, `close`, `volume` per bar. The frontend can get the latest live price from `LiveMarketData` with a simple query:

```sql
SELECT close FROM live_market_data
WHERE ticker = 'OGDC'
ORDER BY date DESC
LIMIT 1;
```

This makes the price fields in `MarketDataCache` a direct duplication of data that already exists in `LiveMarketData`.

**Concern 2 — Two different concerns, two different sources, one table:**
Price data updates hourly during market hours from `live_data.json`. Technical indicators update once daily after the ML pipeline runs from `stocks.json`. Mixing them in one table makes the update logic confusing and the table's responsibility unclear.

### Recommended Fix
Drop `MarketDataCache` entirely. Create a new dedicated `StockTechnicals` table:

```python
class StockTechnicals(TimestampMixin):
    ticker        = models.CharField(max_length=10, unique=True)
    rsi14         = models.FloatField(null=True)
    ma20          = models.DecimalField(max_digits=12, decimal_places=4, null=True)
    ma50          = models.DecimalField(max_digits=12, decimal_places=4, null=True)
    ma200         = models.DecimalField(max_digits=12, decimal_places=4, null=True)
    volatility20d = models.FloatField(null=True)
    volume_ratio  = models.FloatField(null=True)
    eps           = models.DecimalField(max_digits=12, decimal_places=4, null=True)
    computed_at   = models.DateTimeField()
```

- Updated once daily from `stocks.json` after pipeline runs
- Frontend reads live price from `LiveMarketData` (latest bar)
- No duplication, single responsibility per table

---

## Issue 3 — `NewsSentiment` Stores the Same Value Twice

### Current State
The `NewsSentiment` model has two fields that store identical values:

```python
score      = models.FloatField(default=0.0)   # raw SentimentScore
confidence = models.FloatField()               # abs(SentimentScore)
```

In the ingestion code both are populated from the same source:

```python
score=r.get("SentimentScore", 0.0),
confidence=abs(r.get("SentimentScore", 0.0)),
```

Since `SentimentScore` is already a value in `[-1, 1]` from FinBERT/VADER, `abs(SentimentScore)` is not a meaningful "confidence" — it is just the magnitude of the score. The two fields carry the same information.

### Impact
With 41,000+ articles currently in the DB and growing daily across 738 symbols, this is wasted storage on every single row. Every API response also exposes two fields that mean the same thing, which is confusing for anyone consuming the API.

### Recommended Fix
Drop the `confidence` column from `NewsSentiment`. Keep only `score` which is the raw compound score from FinBERT/VADER in `[-1, 1]`. If the frontend needs a magnitude, it can take `abs(score)` at the application layer.

---

## Issue 4 — `StockForecast` Not Storing Raw `MAPE`

### Current State
`stocks.json` provides both `Forecast.MAPE` and `Forecast.Confidence` (`= 1 - MAPE`):

```json
"Forecast": {
  "Model": "ARIMA",
  "PredictedPrice": 423.8372,
  "ExpectedChangePct": 5.7821,
  "Direction": "UP",
  "MAPE": 0.0556,
  "Confidence": 0.9444
}
```

Currently only `Confidence` is stored in `StockForecast`. `MAPE` is discarded.

### Impact
If the frontend wants to display raw model accuracy (e.g. "Average error: 5.6%") or if the alert system wants to filter out signals from low-accuracy models (e.g. skip alerts when `MAPE > 0.15`), that data is not available from the DB. It would require re-reading the JSON file which defeats the purpose of the DB.

### Recommended Fix
Add a `mape` field to `StockForecast`:

```python
mape = models.FloatField(null=True, blank=True)
```

Populate it from `Forecast.MAPE` during ingestion alongside the existing `Confidence` field.

---

## Summary Table

| # | Issue | Affected Table | Type | Priority |
|---|---|---|---|---|
| 1 | Signal read from `Health.Label` instead of `Suggestion.Action` | `stock_signal` | Wrong data source | High |
| 2 | Price data duplicated with `LiveMarketData`, technicals mixed with prices | `market_data_cache` | Table design | High |
| 3 | `confidence` column is duplicate of `score` | `news_sentiment` | Data duplication | Medium |
| 4 | `MAPE` field not stored | `stock_forecast` | Missing field | Low |

---

*All issues above were identified during the DB seeding and integration phase. Issues 1 and 2 should be resolved before frontend API development begins as they directly affect the data the APIs will serve.*
