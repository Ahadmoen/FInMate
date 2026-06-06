# MLflow on DagsHub — setup

MLflow tracking is wired into `forecasting.py` and `directional_classifier.py`
(real per-symbol training runs with params, metrics, and model artifacts)
and into `sentiment.py` + `stock_health.py` (batch monitoring runs:
input/output counts, duration, label distributions).

## 1. Create a DagsHub repo + get credentials

1. Sign up at [dagshub.com](https://dagshub.com).
2. Create a repo (e.g. `FinMate-ML`). On the repo page, click **Remote → Experiments → MLflow**.
3. Copy:
   - **Tracking URI** — `https://dagshub.com/<user>/<repo>.mlflow`
   - **Username** — your DagsHub username
   - **Token** — generate at *Profile → Settings → Tokens*

## 2. Set env vars

In your `.env` (or process env):

```env
MLFLOW_TRACKING_URI=https://dagshub.com/<user>/<repo>.mlflow
MLFLOW_TRACKING_USERNAME=<your-dagshub-username>
MLFLOW_TRACKING_PASSWORD=<the-token>
```

Leaving any of these unset disables tracking — scripts still run, no
network calls happen, no errors. This is intentional for CI / quick
local runs.

## 3. Install dependency

```
pip install -r requirements.txt
```

## 4. Run any ML script

```
python -m ml_services.forecasting              # cold — full retrain, logs runs
python -m ml_services.directional_classifier   # cold — full retrain, logs runs
python -m ml_services.sentiment                # batch monitoring run
python -m ml_services.stock_health             # batch monitoring run
```

## 5. View runs

Open `<tracking-uri-without-.mlflow-suffix>` in a browser — you'll see
four experiments:

- **forecasting** — one parent batch run per cold execution + nested per-symbol runs (ARIMA_MAPE, LSTM_MAPE, hyperparams, LSTM weights as artifact)
- **directional_classifier** — one parent batch run + nested per (symbol × horizon) runs (OverallHitRate, HighConfHitRate, ensemble pickle as artifact)
- **sentiment** — batch run with input article count + label distribution
- **stock_health** — batch run with health label + suggestion distribution

Click any run to see params, metrics, artifacts, and side-by-side
comparison with previous runs.

## Notes

- Warm-mode runs (`--warm`) on forecasting/directional_classifier do
  log a batch-level run but skip per-symbol nested runs since no
  training happens. This keeps the experiment view focused on actual
  retrains.
- `fusion.py` is a library called from `stock_health.py` — its outputs
  are tracked there, not separately.
- For local debugging without DagsHub, run a local MLflow UI:
  `pip install mlflow && mlflow ui --port 5000` then set
  `MLFLOW_TRACKING_URI=http://localhost:5000`.
