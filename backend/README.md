# FinMate Backend

FinMate is an AI-powered stock forecasting and smart-portfolio platform.
This repository hosts the Django + DRF backend that exposes the REST API
consumed by the React/Expo frontend, schedules data ingestion + alerts via
Celery, and serves as the bridge to the ML inference services.

## Team / Module Ownership

| Folder          | Owner  | Responsibility                                    |
| --------------- | ------ | ------------------------------------------------- |
| `users/`        | Haider | Auth, JWT, user profile, notification preferences |
| `core/`         | Haider | Symbols, market data cache, signals, housekeeping |
| `portfolio/`    | Haider | Portfolio, holdings, transactions, analytics      |
| `chatbot/`      | Haider | Chat sessions / messages, RAG entrypoint          |
| `alerts/`       | Ammara | Alert dispatch, formatters, channel adapters      |
| `integrations/` | Ahad   | Scrapers, scheduled ingestion tasks               |
| `ml_services/`  | Ahad   | Forecasting / sentiment / fusion / chatbot RAG    |

## Tech Stack

- Django 4.2 + Django REST Framework
- SimpleJWT (24h access / 7d refresh)
- PostgreSQL via Supabase (`DATABASE_URL`)
- Redis via Upstash (`REDIS_URL`)
- Celery + django-celery-beat
- django-environ for `.env` loading
- httpx for ML service HTTP calls
- corsheaders for the React/Expo frontend

## Setup

```bash
# 1. Clone and enter the repo
git clone <repo-url> finmate-backend
cd finmate-backend

# 2. Copy env template and fill in real values
cp .env.example .env

# 3. Create a virtual environment
python -m venv .venv

# 4. Install dependencies
pip install -r requirements.txt

# 5. Run the API
python manage.py runserver 0.0.0.0:3100
```

Schema-change note for contributors:

- If you modify models, run `python manage.py makemigrations` and
  `python manage.py migrate` against the appropriate environment.

## Celery (worker + beat)

In two separate terminals (with `.env` populated):

```bash
celery -A config worker -l info
celery -A config beat   -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

The full beat schedule (PKT timezone) lives in `config/celery_schedule.py`.

## API Base URL & Auth

- Base URL: `http://localhost:3100/api/v1/`
- All endpoints require a JWT access token, except `/api/v1/users/register/`,
  `/api/v1/login/`.
- `/api/v1/users/register/` accepts basic account + KYC + investment profile fields
  in one payload and returns JWT tokens on success.

Login:

```bash
curl -X POST http://localhost:3100/api/v1/login/ \
  -H "Content-Type: application/json" \
  -d '{"email": "<your-email>", "password": "<your-password>"}'
```

Use it in subsequent requests:

```bash
curl http://localhost:3100/api/v1/portfolio/ \
  -H "Authorization: Bearer <ACCESS_TOKEN>"
```

## ML Artifacts

Trained model artifacts (`*.pkl`, `*.h5`, `*.pt`) live in
`ml_services/artifacts/` and are intentionally **gitignored**. Each developer
should drop the latest versions into that folder locally — do not commit them.

## Scrapers & ML Pipeline

The `integrations/scrapers/` modules pull data from PSX and Google News into
combined JSON files under `integrations/data/`. The `ml_services/` modules
consume those files and emit forecast / sentiment outputs in the same folder.

### Scrapers (run from project root as Python modules)

```bash
.venv/bin/python -m integrations.scrapers.registry_scraper   # monthly: refresh symbols.py from PSX listing
.venv/bin/python -m integrations.scrapers.historical_scraper # daily-OHLCV from 2000 to today
.venv/bin/python -m integrations.scrapers.live_scraper       # today's intraday hourly bars (PKT)
.venv/bin/python -m integrations.scrapers.news_scraper       # Google News RSS per symbol + macro queries
.venv/bin/python -m integrations.scrapers.key_ratios_scraper # daily technicals (MA/RSI/vol) + best-effort fundamentals
```

`SCRAPER_LIMIT=N` runs the scrapers over the first `N` symbols only — useful
for development since `symbols.py` now contains all 738 PSX equities. The
first 20 are the curated set with hand-tuned aliases / keywords.

### Outputs (`integrations/data/`)

| File                       | Producer                       | Shape                                                                  |
| -------------------------- | ------------------------------ | ---------------------------------------------------------------------- |
| `historical_data.json`     | `historical_scraper.py`        | `[{Symbol, Date, Open, High, Low, Close, Volume}, …]`                  |
| `live_data.json`           | `live_scraper.py`              | Same shape, hourly bars for today's session                            |
| `news_data.json`           | `news_scraper.py`              | `[{Symbol, Date, Heading, Link, Keywords, KeywordContext, Market, …}]` |
| `stock_forecasts.json`     | `ml_services/forecasting`      | 60-day walk-forward backtest, ARIMA + multi-feature LSTM, best-of per symbol. |
| `forecasting_trend.json`   | `ml_services/forecasting`      | 30-business-day forward forecast (ARIMA, multi-step from latest close). |
| `best_models.json`         | `ml_services/forecasting`      | Per-symbol MAPE summary + winning model.                               |
| `directional_signals.json` | `ml_services/directional_classifier` | Purpose-built UP/DOWN classifier (1d/5d/20d horizons), per-symbol hit rates and live signal. |
| `news_sentiment.json`      | `ml_services/sentiment`        | FinBERT-scored news rows (VADER fallback). 5-class label + score.      |
| `daily_ratios.json`        | `key_ratios_scraper`           | Per-symbol technicals (MA20/50/200, RSI14, volatility, vol ratio).     |
| `fundamental_ratios.json`  | `key_ratios_scraper`           | Per-symbol PSX fundamentals snapshot (best-effort).                    |
| `stocks.json`              | `ml_services/stock_health`     | Merged per-symbol view with fused `Health` and per-component contributions. |

### ML modules

```bash
.venv/bin/python -m ml_services.forecasting              # 60d walk-forward backtest + 30d trend, ARIMA + multi-feature LSTM
.venv/bin/python -m ml_services.sentiment                # FinBERT (with VADER fallback), 5-class buckets
.venv/bin/python -m ml_services.directional_classifier   # purpose-built UP/DOWN ensemble at 1/5/20-day horizons
.venv/bin/python -m ml_services.stock_health             # fuse everything → stocks.json with Suggestion
```

The forecasting module:
- 60-day walk-forward backtest with weekly ARIMA refits and a 2-layer
  LSTM (64 hidden, dropout 0.2, lookback 60) trained on close + volume +
  1d returns + 5d returns. Early stopping on a 15% chronological val split.
- A separate 30-business-day forward trend forecast, written to
  `forecasting_trend.json`. ARIMA-only over the multi-step horizon —
  autoregressive LSTM compounds error too fast over 30 days.

The sentiment module:
- Loads `ProsusAI/finbert` (financial-text-tuned BERT) by default, with
  a `SENTIMENT_BACKEND=vader` env var to force the lighter fallback.
  Each article's compound score is `pos_prob − neg_prob` from the
  3-class output; bucketed into the same 5-class labels.

Sentiment labels: `VERY_BAD`, `BAD`, `NEUTRAL`, `GOOD`, `EXCELLENT`. The
`NewsSentiment` model in `core/models.py` mirrors these choices. Forecast
results map onto the existing `StockForecast` model (per-model row, with
`predicted_price` / `direction` / `model_used`).

The **directional classifier** ([`ml_services/directional_classifier.py`](ml_services/directional_classifier.py))
is a separate purpose-built model that predicts UP/DOWN over 1, 5, and 20-day
horizons. Unlike the regression-based forecast (which is trained for price
accuracy and gets ~37 % directional hit rate), the classifier ensemble
(GradientBoosting + RandomForest + LogisticRegression on 15 engineered
features) averages **51.5 % hit rate on next-day direction** and **70 %+
on specific (symbol, horizon) pairs** where it's decisive. Output goes to
`directional_signals.json` and is folded into the `Directional` block of
each `stocks.json` row, where Suggestion uses it as a confirmation /
veto modifier.

The fusion logic in [`ml_services/fusion.py`](ml_services/fusion.py) is
**adaptive per stock**:

- **Dynamic weights** — each component (`Forecast`, `Sentiment`,
  `Technicals`) carries a `Quality` score in `[0, 1]` that reflects how
  much we trust that signal *for that symbol right now* (forecast: from
  the model's backtest MAPE; sentiment: from article count + recency +
  magnitude; technicals: from history depth + RSI extremity). Weights are
  normalized from those qualities — a stock with sparse news naturally
  de-emphasizes the news component, and so on. A 10% floor prevents any
  signal from going fully dark.
- **Divergence damping** — when the forecast is extreme (`|score| ≥ 0.5`)
  but the average of sentiment + technicals points the *opposite* way,
  the forecast is dampened up to 40 % before fusion. This is the
  reality-check guard: a wildly bullish ARIMA can't override clearly
  negative news + technicals.

Each row in `stocks.json` exposes these in the `Health` block —
`Quality`, `Weights`, `Components` (post-damping), `ComponentsRaw` (pre),
`ForecastDamping` (factor applied), and the `Contributions` /
`PrimaryDriver` view that answers "*why* is this stock GOOD/BAD?"
