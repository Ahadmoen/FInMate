# post_deployment_change.md — schema cleanup after first cloud cutover

After the cloud pipeline (warm-1..4 + cold + live + quarterly) was wired
up and producing fresh `stocks.json` daily, a review of how those
outputs landed in Supabase surfaced five issues. They are post-deployment
fixes — none of them block ML, but each one was either showing wrong data
to users, duplicating data unnecessarily, or dropping useful signal on
the floor before it reached the DB.

This doc lists each issue, the fix that shipped, and the migration /
deployment steps that put it into Supabase.

Branch: `scraper-fixes-forecasting-sentiment`
Migrations: `core/migrations/0006_*` (Issues #2, #3, #4) and
`core/migrations/0007_*` (Issue #5)
Image: rebuilt as `pipeline:latest` (v12) after the changes
Cutover trigger: `finmate-warm-4-ingest` execution
`finmate-warm-4-ingest-mbnvj` — applied 0006 + 0007 to Supabase, then
ingested 673 rows under the new schema in ~37 seconds.

---

## Issue #1 — `StockSignal` was reading the wrong field

### What was happening
The `stock_signal` table holds the final BUY/SELL/HOLD recommendation
shown to users. The ingest code was sourcing that from
`Health.Label` in `stocks.json`, which is the **intermediate** fused-score
label — computed *before* the directional classifier has had a chance
to confirm or override it.

### What it should have been
`stocks.json` exposes a separate `Suggestion.Action` field — the
**final** recommendation after the directional classifier has either
upgraded confidence to HIGH or vetoed a BUY/SELL down to HOLD. That is
the field users should see.

### Impact
Users and the alerts system were seeing a signal that hadn't gone
through the final directional check. The whole point of the
directional classifier is to be the last line of defence — skipping
its output meant it was effectively doing nothing.

### Fix
- Replaced `LABEL_TO_SIGNAL.get(health.get("Label"))` with
  `ACTION_TO_SIGNAL.get(suggestion.get("Action"))` in both
  [integrations/tasks.py](integrations/tasks.py) and
  [integrations/management/commands/load_ml_outputs.py](integrations/management/commands/load_ml_outputs.py).
- Kept `Health.Label` alongside as a new diagnostic column
  `stock_signal.health_label` so we can still see when the directional
  classifier overrode the fusion's call (added in migration 0004 prior
  to this cleanup).
- Added a `horizon` field too (1 / 5 / 20 days) sourced from
  `Suggestion.DirectionalCheck.Horizon`, so we know which directional
  horizon backed the call.

---

## Issue #2 — `MarketDataCache` had no clear purpose

### What was happening
`MarketDataCache` was originally a single-row price snapshot per ticker,
updated hourly during market hours. But `LiveMarketData` already stores
all hourly bars (open / high / low / close / volume per bar) — so live
price was being written to two places simultaneously, with no benefit.

On top of that, `MarketDataCache` *also* stored daily technical
indicators (`rsi14`, `ma20`, `ma50`, `ma200`, `volatility20d`,
`volume_ratio`, `eps`) sourced from `stocks.json` on a completely
different cadence. Two unrelated concerns in one table.

### Impact
- Any API reading `MarketDataCache` for live price was reading stale
  data when `LiveMarketData` had a fresher bar.
- Mixed concerns made it unclear what the table was responsible for.
- Maintenance burden: two tasks writing to the same table at
  different times with different data.

### Fix
- Dropped `MarketDataCache` entirely.
- Created `StockTechnicals` (table `stock_technicals`) holding only
  daily technical indicators: `ticker`, `rsi14`, `ma20`, `ma50`,
  `ma200`, `volatility20d`, `volume_ratio`, `eps`, `computed_at`. One
  row per ticker, refreshed by warm-1.
- Live price now lives only in `LiveMarketData`. Frontend reads the
  most recent intraday bar from `/live/<ticker>/`; daily indicators
  from `/technicals/<ticker>/`.
- Updated all friend's app code that referenced the old table:
  [core/admin.py](core/admin.py),
  [core/services.py](core/services.py),
  [core/views.py](core/views.py),
  [core/serializers.py](core/serializers.py),
  [core/urls.py](core/urls.py),
  [portfolio/services.py](portfolio/services.py).
- Removed the `MarketDataCache` mirror update from
  `_ingest_live_data()` in [integrations/tasks.py](integrations/tasks.py).

Migration: `core/migrations/0006_stocktechnicals_delete_marketdatacache_and_more.py`

---

## Issue #3 — `NewsSentiment` was storing the same value twice

### What was happening
`NewsSentiment` had two fields — `score` and `confidence` — both
populated with `abs(SentimentScore)` from `news_sentiment.json` on
every insert. They held the exact same value.

### Impact
Wasted storage across 41,000+ rows and growing daily. Any API
response was exposing two fields that meant the same thing —
confusing for frontend developers consuming the API.

### Fix
- Dropped the `confidence` column from `news_sentiment`.
- Kept `score` as the raw FinBERT / VADER compound score in
  `[-1, 1]` (negative = bearish, positive = bullish).
- Removed the `confidence=` write from `_ingest_news_sentiment()` in
  [integrations/tasks.py](integrations/tasks.py) and from
  `_load_news_sentiment()` in
  [integrations/management/commands/load_ml_outputs.py](integrations/management/commands/load_ml_outputs.py).
- Updated `NewsSentimentAdmin` in [core/admin.py](core/admin.py) to
  drop `confidence` from `list_display` and `search_fields`.

Migration: bundled into `core/migrations/0006_*`.

---

## Issue #4 — `StockForecast` wasn't storing MAPE

### What was happening
`stocks.json` provides both `Forecast.MAPE` (raw mean absolute
percentage error of the winning model on the 60-day backtest, e.g.
`0.0316` = 3.16% error) and `Forecast.Confidence` (`1 - MAPE`,
e.g. `0.9684`). The ingest stored `Confidence` correctly but discarded
`MAPE`.

### Impact
If the frontend wanted to show "Model accuracy: 3.2% average error"
or filter out low-quality forecasts (e.g. ignore predictions where
`mape > 0.10`), that data wasn't available from the DB. It would
require re-reading the JSON file — defeating the point of having a DB.

### Fix
- Added `mape` (FloatField, nullable) to `StockForecast`.
- Populated it from `forecast.get("MAPE")` in both
  [integrations/tasks.py](integrations/tasks.py) and
  [integrations/management/commands/load_ml_outputs.py](integrations/management/commands/load_ml_outputs.py).

Migration: bundled into `core/migrations/0006_*`.

---

## Issue #5 — `StockSignal` was discarding the post-Suggestion decision metrics

### What was happening
`stocks.json`'s `Suggestion` block exposes four numeric fields the
Suggestion logic uses to pick the action — `Confidence`,
`BlendedScore`, `ForecastSignedScore`, `SignalStrength` — and the
ingest was discarding all of them. Only `Suggestion.Action` (the
categorical BUY/HOLD/SELL output, fixed in Issue #1) was being kept.

```json
"Suggestion": {
  "Action": "STRONG_SELL",
  "Confidence": "HIGH",
  "BlendedScore": -0.4956,
  "ForecastSignedScore": -0.969,
  "SignalStrength": 0.969
}
```

### Impact
The frontend could see *what* the recommendation was (BUY / HOLD / etc.)
but not *how confident* the directional classifier was, *what
component drove it* (forecast vs. fusion), or *how strong* the
strongest single component was. Filtering low-confidence calls or
explaining a recommendation to the user would have meant re-reading
JSON.

### Fix
Added four fields to `StockSignal`:

| Field | Type | Source | Use |
|---|---|---|---|
| `suggestion_confidence` | CharField (HIGH/MEDIUM/LOW) | `Suggestion.Confidence` | Categorical confidence in the BUY/HOLD/SELL recommendation |
| `blended_score` | FloatField in roughly `[-1, 1]` | `Suggestion.BlendedScore` | The decision metric the Suggestion logic uses to pick the action |
| `forecast_signed_score` | FloatField in `[-1, 1]` | `Suggestion.ForecastSignedScore` | Forecast component as a signed score, scaled by model confidence |
| `signal_strength` | FloatField | `Suggestion.SignalStrength` | `max(\|Health.Score\|, \|forecast_signed_score\|)` — how confident the strongest single component is |

Note: the categorical confidence field is named `suggestion_confidence`
(not just `confidence`) because `StockSignal.confidence` already exists
as a FloatField holding `abs(Health.Score)` — the magnitude of the
fused Health score. Two different things; two different field names.

Wired into both
[integrations/tasks.py](integrations/tasks.py) and
[integrations/management/commands/load_ml_outputs.py](integrations/management/commands/load_ml_outputs.py),
and surfaced in the API via [core/serializers.py](core/serializers.py).

Migration: `core/migrations/0007_stocksignal_blended_score_and_more.py`

---

## Operational changes that supported the cutover

A few one-time operational changes that fell out of these schema fixes:

### warm-4 now self-heals schema drift

`bin/run_warm_4_ingest.sh` runs `python manage.py migrate --noinput`
as stage 1 before any ingest. Idempotent at DB-HEAD; if a new
migration is committed, the next warm-4 run picks it up without a
separate manual step. Solves the deploy-order problem where new ingest
code would otherwise try to write to columns that don't exist yet.

### Image rebuild

After the schema + ingest changes were committed and pushed, the
`pipeline:latest` image had to be rebuilt so the Cloud Run Jobs would
pick up the new code. Two earlier builds (v10, v11) were cancelled
mid-flight when the in-progress fix list grew; **v12** is the image
currently serving all jobs.

```
gcloud builds submit \
  --tag us-central1-docker.pkg.dev/venom-scent-476112/finmate/pipeline:latest \
  --project=venom-scent-476112 --timeout=3600
```

### Cutover execution

Migration 0006 + 0007 were applied to Supabase by triggering
`finmate-warm-4-ingest` once after v12 deployed. The execution log
(`finmate-warm-4-ingest-mbnvj`) shows the migrate stage applying 0007
cleanly, then bulk-ingesting 673 rows in ~13 seconds:

```
[22:09:16Z] 1. apply pending Django migrations to Supabase
  Applying core.0007_stocksignal_blended_score_and_more... OK
[22:09:38Z] 2. download outputs from GCS to container disk
  [gcs_sync] downloaded outputs/stocks.json (2.23 MB)
  [gcs_sync] downloaded outputs/news_sentiment.json (3.25 MB)
[22:09:40Z] 3. bulk ingest into Supabase via tasks._ingest_*
  rows: 673
  new articles inserted: 0
  intraday bars: 0
[22:09:53Z] DONE — finmate-warm-4-ingest complete
```

After this point the daily 18:00 PKT scheduler chain runs against the
new schema with no further intervention needed.

---

## Verification

To confirm the new fields are populated, query Supabase:

```sql
SELECT ticker, signal, health_label, suggestion_confidence,
       blended_score, forecast_signed_score, signal_strength,
       horizon, dominant_sentiment
FROM stock_signal
ORDER BY generated_at DESC
LIMIT 5;

SELECT ticker, mape, confidence, predicted_price
FROM stock_forecast
ORDER BY forecast_date DESC LIMIT 5;

SELECT ticker, rsi14, ma20, ma50, ma200, eps, computed_at
FROM stock_technicals
ORDER BY computed_at DESC LIMIT 5;
```

`MarketDataCache` should no longer exist; attempting `SELECT * FROM
market_data_cache` will return "relation does not exist". That is the
expected post-cutover state.
