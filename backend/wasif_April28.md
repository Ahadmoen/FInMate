# Backend ML Outputs → Supabase Integration (2026-04-28)

This note hands off the new scraper + ML pipeline so it can be wired into
Supabase tables. It covers (1) what changed, (2) what JSON the pipeline
produces, and (3) how to ingest those JSONs into the existing Django models
(which Supabase hosts as Postgres tables via `DATABASE_URL`).

---

## 1. What changed on this branch

**Branch:** `scraper-fixes-forecasting-sentiment`

### Scrapers (`integrations/scrapers/`)

- **One combined JSON per scraper instead of per-symbol.**
  - `historical_scraper.py` → `integrations/data/historical_data.json`
  - `live_scraper.py` → `integrations/data/live_data.json`
  - `news_scraper.py` → `integrations/data/news_data.json` (general macro
    rows merged in with `Symbol = "GENERAL"`)
- **New `registry_scraper.py`** (designed to run monthly). Hits the PSX
  symbols endpoint, refreshes `symbols.py` with every listed equity, and
  re-derives keywords / industry per symbol. The original 20 hand-curated
  entries are preserved as-is.
- **`SCRAPER_LIMIT=N`** environment variable on every scraper — limits the
  iteration to the first `N` symbols. Used for dev runs.

### ML services (`ml_services/`)

- **`forecasting.py`** — implements `get_forecast(ticker)` (single-step
  ARIMA shim used by Django) and a `main()` that backtests the **last 7
  closes** per symbol using both ARIMA(5,1,0) and a small PyTorch LSTM,
  writing `integrations/data/stock_forecasts.json`.
- **`sentiment.py`** — implements `analyze_sentiment(articles)` and a
  `main()` that scores every article in `news_data.json`. Uses VADER with
  a finance-specific lexicon overlay (`downgrade`, `upgrade`, `default`,
  `surge`, …) and buckets the compound score into **five classes**.

### Models (`core/models.py`)

- `NewsSentiment.Sentiment` choices changed from 3-class
  (POSITIVE / NEUTRAL / NEGATIVE) → **5-class**:
  - `VERY_BAD`, `BAD`, `NEUTRAL`, `GOOD`, `EXCELLENT`
- `NewsSentiment` gained a `score: FloatField` (the raw VADER compound
  score, range `-1.0..1.0`) and a `link: URLField` (article URL).
- **A migration is required** before this branch can talk to Supabase:
  ```bash
  python manage.py makemigrations core
  python manage.py migrate
  ```

`StockForecast` already exists in `core/models.py` with the right shape
(`ticker`, `forecast_date`, `direction`, `confidence`, `predicted_price`,
`model_used`) and `unique_together = (ticker, forecast_date, model_used)`,
so we don't need a schema change for forecasts.

### Dependencies (`requirements.txt`)

Added: `statsmodels`, `scikit-learn`, `vaderSentiment`, `torch`.

---

## 2. JSON output schemas

### `stock_forecasts.json`

```json
[
  {
    "Symbol": "HBL",
    "Date": "2026-04-28T00:00:00",
    "Close": 173.69,
    "Forecasting_ARIMA": 175.12,
    "Forecasting_LSTM": 169.08,
    "Direction_ARIMA": "UP",
    "Direction_LSTM": "DOWN"
  }
]
```

133 rows for the curated 20 (19 produced data; SILK was empty — likely
delisted). Each (Symbol, Date) appears twice in the table on the consumer
side: once as `model_used = "ARIMA"`, once as `model_used = "LSTM"`.

### `news_sentiment.json`

Same fields as `news_data.json` with two added columns:

```json
{
  "Symbol": "OGDC",
  "Date": "2026-04-27T09:12:00Z",
  "Heading": "OGDC posts record quarterly earnings",
  "Link": "https://...",
  "Platform": "Business Recorder",
  "Market": "Oil & Gas",
  "Sentiment": "EXCELLENT",
  "SentimentScore": 0.78
}
```

3,088 rows in the latest run.

---

## 3. Loading the JSONs into Supabase

Supabase = Postgres, so the Django models map 1:1 onto Supabase tables.
Two integration paths — pick whichever fits your workload.

### Path A — Django ORM bulk-load (recommended for backend cron jobs)

Run from a Django shell or a management command. Idempotent on re-run
because both models have natural unique keys.

```python
# management command sketch: integrations/management/commands/load_ml_outputs.py
import json
from datetime import datetime, timezone
from pathlib import Path

from django.core.management.base import BaseCommand

from core.models import StockForecast, NewsSentiment

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "integrations" / "data"


class Command(BaseCommand):
    def handle(self, *args, **opts):
        self._load_forecasts()
        self._load_sentiments()

    def _load_forecasts(self):
        rows = json.loads((DATA_DIR / "stock_forecasts.json").read_text())
        for r in rows:
            date = datetime.fromisoformat(r["Date"]).date()
            for model, price_key, dir_key in [
                ("ARIMA", "Forecasting_ARIMA", "Direction_ARIMA"),
                ("LSTM",  "Forecasting_LSTM",  "Direction_LSTM"),
            ]:
                price = r.get(price_key)
                if price is None:
                    continue
                StockForecast.objects.update_or_create(
                    ticker=r["Symbol"],
                    forecast_date=date,
                    model_used=model,
                    defaults={
                        "direction": r.get(dir_key, "STABLE"),
                        "confidence": 0.6,        # placeholder; expose from model later
                        "predicted_price": price,
                    },
                )

    def _load_sentiments(self):
        rows = json.loads((DATA_DIR / "news_sentiment.json").read_text())
        for r in rows:
            published = datetime.fromisoformat(r["Date"].replace("Z", "+00:00"))
            NewsSentiment.objects.update_or_create(
                ticker=r["Symbol"],
                headline=r["Heading"],
                published_at=published,
                defaults={
                    "link": r.get("Link", ""),
                    "source": r.get("Platform", ""),
                    "sentiment": r["Sentiment"],
                    "score": r["SentimentScore"],
                    "confidence": abs(r["SentimentScore"]),
                },
            )
```

Run with:

```bash
python manage.py load_ml_outputs
```

Hook this into Celery beat after the scraper + ML steps so each daily
ingestion ends with the rows landing in Supabase.

### Path B — Direct Supabase upsert (good for one-off backfills)

Use the Supabase JS / Python client to upsert against the same tables.
Match on `(ticker, forecast_date, model_used)` for forecasts and
`(ticker, headline, published_at)` for sentiments to stay idempotent.

```python
# example with supabase-py
from supabase import create_client
import json
sb = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

rows = json.loads(open("integrations/data/news_sentiment.json").read())
payload = [
    {
        "ticker": r["Symbol"],
        "headline": r["Heading"],
        "link": r.get("Link", ""),
        "source": r.get("Platform", ""),
        "sentiment": r["Sentiment"],
        "score": r["SentimentScore"],
        "confidence": abs(r["SentimentScore"]),
        "published_at": r["Date"],
    }
    for r in rows
]
sb.table("news_sentiment").upsert(payload, on_conflict="ticker,headline,published_at").execute()
```

Make sure RLS policies on `news_sentiment` / `stock_forecast` allow the
service role to write.

---

## 4. Suggested Celery wiring

Add to `config/celery_schedule.py`:

| Schedule       | Task                                       | Purpose                                  |
| -------------- | ------------------------------------------ | ---------------------------------------- |
| Monthly, 1st   | `integrations.tasks.run_registry_scraper`  | Refresh `symbols.py` from PSX listing    |
| Daily 17:30 PKT| `integrations.tasks.run_historical_scraper`| Append today's daily bars                |
| Hourly, mkt-hr | `integrations.tasks.run_live_scraper`      | Update intraday hourly bars              |
| Daily 18:00 PKT| `integrations.tasks.run_news_scraper`      | Pull headlines                           |
| Daily 18:30 PKT| `ml_services.tasks.run_forecasting`        | Refit + emit `stock_forecasts.json`      |
| Daily 18:35 PKT| `ml_services.tasks.run_sentiment`          | Score `news_data.json`                   |
| Daily 18:40 PKT| `integrations.tasks.load_ml_outputs`       | Push JSON → Supabase via the ORM         |

The task wrappers are thin — each one just calls the corresponding `main()`
and writes a `ScrapeRun` audit row.

---

## 5. Caveats

- The LSTM is intentionally tiny (single-layer, 32-hidden, 25 epochs). It's
  a baseline, not production-grade — its MAPE on the curated 20 backtest
  was ~10% vs ARIMA's ~2%. Worth replacing with a properly trained model
  before relying on `Forecasting_LSTM`.
- VADER + finance lexicon is a fast, GPU-free baseline. For better
  accuracy on financial text, drop in FinBERT later by replacing the
  `score_text` function — the rest of the pipeline (bucketing, JSON
  output, ORM ingest) is unchanged.
- `historical_data.json` is ~17 MB on disk for 20 symbols × 25 years.
  Scaling to all 738 symbols will produce ~600 MB+ — at that point the
  JSON file should be replaced with direct DB writes from
  `historical_scraper.py`.
- Google News rate-limits aggressive polling. Running `news_scraper`
  across all 738 symbols in one shot will hit DNS / connection failures
  partway through (we saw this on the latest run). Either keep
  `SCRAPER_LIMIT` low or add per-symbol backoff.
