"""Stock price forecasting via ARIMA + a multi-feature LSTM.

Two outputs:

1. **Backtest** — 60-day walk-forward 1-step-ahead per symbol with both
   models. ARIMA refits every `ARIMA_REFIT_INTERVAL` days for speed; LSTM
   is trained once on the train slice with early stopping, then predicts
   each test day using the actual previous-day window.

2. **Trend forecast** — `FUTURE_HORIZON` (default 30) days ahead from the
   latest close, using the best model per symbol. Saved to
   `forecasting_trend.json`. ARIMA is used for multi-step trend
   forecasting because autoregressive LSTM accumulates error fast on
   long horizons.

Modes:
  cold (default) — full retrain + 60-day backtest, persists LSTM weights
                   per symbol to integrations/data/models/{SYM}/lstm.pt.
  warm           — loads cached LSTM, predicts only the most-recent day,
                   appends one row to stock_forecasts.json. ARIMA refits
                   from scratch each warm run (cheap — 1-3s/symbol).
                   Symbols without a cache fall back to cold per-symbol.
"""
import argparse
import copy
import json
import math
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA

import torch
from torch import nn

from .model_cache import load_lstm, save_lstm
from . import mlflow_utils

warnings.filterwarnings("ignore")

DATA_DIR = Path(__file__).resolve().parent.parent / "integrations" / "data"
HISTORICAL_FILE = DATA_DIR / "historical_data.json"
OUTPUT_FILE = DATA_DIR / "stock_forecasts.json"
BEST_MODEL_FILE = DATA_DIR / "best_models.json"
TREND_FILE = DATA_DIR / "forecasting_trend.json"

BACKTEST_DAYS = 60
ARIMA_REFIT_INTERVAL = 7        # refit ARIMA every N walk-forward days
ARIMA_ORDER = (5, 1, 0)

LSTM_LOOKBACK = 60
LSTM_HIDDEN = 64
LSTM_LAYERS = 2
LSTM_DROPOUT = 0.2
LSTM_MAX_EPOCHS = 100
LSTM_PATIENCE = 10
LSTM_LR = 0.005
LSTM_BATCH = 64
LSTM_FEATURES = ["close", "volume", "ret1", "ret5"]  # close must be index 0
N_FEATURES = len(LSTM_FEATURES)

FUTURE_HORIZON = 30
MIN_HISTORY = LSTM_LOOKBACK + BACKTEST_DAYS + 60

# Skip any symbol whose latest historical data is older than this many
# days. Matches historical_scraper's MAX_LOOKBACK_DAYS so a ticker
# that scraper deems "delisted/halted" never reaches the trainer.
# Saves ~5 min of LSTM training time per stale ticker on cold runs.
import os as _os
STALE_TRAINING_DAYS = int(_os.environ.get("STALE_TRAINING_DAYS", "30"))


def _is_stale(group: pd.DataFrame) -> tuple[bool, int]:
    """True if the symbol's most recent close is > STALE_TRAINING_DAYS
    old. Returns (is_stale, age_in_days). Tickers like MODAM that last
    traded April 2024 stay in historical_data.json but get skipped here
    so the model doesn't extrapolate dead price action into fresh signals."""
    if group.empty:
        return False, 0
    try:
        latest = pd.to_datetime(group["Date"]).max()
        age = (pd.Timestamp.now(tz=latest.tz) - latest).days if latest.tz else (pd.Timestamp.now() - latest).days
        return age > STALE_TRAINING_DAYS, int(age)
    except Exception:
        return False, 0


# ---------------- LSTM ----------------------------------------------------

class StockLSTM(nn.Module):
    def __init__(self, input_size: int = N_FEATURES, hidden: int = LSTM_HIDDEN,
                 num_layers: int = LSTM_LAYERS, dropout: float = LSTM_DROPOUT):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0.0,
        )
        self.head = nn.Linear(hidden, 1)

    def forward(self, x):
        out, _ = self.lstm(x)
        return self.head(out[:, -1, :])


def _build_features(closes: np.ndarray, volumes: np.ndarray) -> tuple:
    """Return (features_TxF, mu_F, sigma_F) z-normalized per column.

    Feature 0 is always `close` so we can de-normalize predictions back
    to price units."""
    n = len(closes)
    ret1 = np.zeros(n)
    ret1[1:] = np.diff(closes) / np.where(closes[:-1] == 0, 1, closes[:-1])
    ret5 = np.zeros(n)
    if n > 5:
        ret5[5:] = (closes[5:] - closes[:-5]) / np.where(closes[:-5] == 0, 1, closes[:-5])

    feats = np.stack([closes, volumes, ret1, ret5], axis=1).astype(np.float32)
    mu = feats.mean(axis=0)
    sigma = feats.std(axis=0)
    sigma = np.where(sigma == 0, 1.0, sigma)
    return (feats - mu) / sigma, mu, sigma


def _make_windows(features: np.ndarray, lookback: int) -> tuple:
    """Build (X, y) windows. X[i] is `lookback` rows of all features;
    y[i] is the next row's `close` (feature 0)."""
    xs, ys = [], []
    for i in range(len(features) - lookback):
        xs.append(features[i : i + lookback])
        ys.append(features[i + lookback, 0])
    return np.asarray(xs, dtype=np.float32), np.asarray(ys, dtype=np.float32)


def _train_lstm(features: np.ndarray, lookback: int, *,
                hidden: int = LSTM_HIDDEN, layers: int = LSTM_LAYERS,
                max_epochs: int = LSTM_MAX_EPOCHS, patience: int = LSTM_PATIENCE,
                lr: float = LSTM_LR, batch: int = LSTM_BATCH) -> StockLSTM | None:
    """Train an LSTM with 85/15 chronological train/val split and early
    stopping on val loss. Returns the best model, or None if not enough data."""
    xs, ys = _make_windows(features, lookback)
    if len(xs) < lookback:
        return None

    split = int(0.85 * len(xs))
    if split < lookback or split == len(xs):
        return None
    x_tr, y_tr = torch.tensor(xs[:split]), torch.tensor(ys[:split]).unsqueeze(-1)
    x_va, y_va = torch.tensor(xs[split:]), torch.tensor(ys[split:]).unsqueeze(-1)

    model = StockLSTM(input_size=features.shape[1], hidden=hidden, num_layers=layers)
    opt = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.MSELoss()

    best_val, best_state, bad = float("inf"), None, 0
    n = x_tr.shape[0]
    for _ in range(max_epochs):
        model.train()
        perm = torch.randperm(n)
        for i in range(0, n, batch):
            idx = perm[i : i + batch]
            opt.zero_grad()
            loss = loss_fn(model(x_tr[idx]), y_tr[idx])
            loss.backward()
            opt.step()

        model.eval()
        with torch.no_grad():
            val = float(loss_fn(model(x_va), y_va).item())
        if val < best_val:
            best_val = val
            best_state = copy.deepcopy(model.state_dict())
            bad = 0
        else:
            bad += 1
            if bad >= patience:
                break

    if best_state is not None:
        model.load_state_dict(best_state)
    return model


def _lstm_walk_forward(model: StockLSTM, all_features: np.ndarray, train_len: int,
                       test_len: int, lookback: int, close_mu: float, close_sigma: float) -> list:
    """For each of the `test_len` test days, predict using the lookback
    window that ends at day `train_len + i - 1` (i.e. all actual previous
    values). Returns price-scale forecasts."""
    forecasts = []
    model.eval()
    with torch.no_grad():
        for i in range(test_len):
            end = train_len + i
            if end - lookback < 0:
                forecasts.append(float("nan"))
                continue
            window = all_features[end - lookback : end]
            inp = torch.tensor(window, dtype=torch.float32).unsqueeze(0)
            yhat_norm = float(model(inp).item())
            forecasts.append(yhat_norm * close_sigma + close_mu)
    return forecasts


def _lstm_autoregressive(model: StockLSTM, last_window: np.ndarray, steps: int,
                         close_mu: float, close_sigma: float) -> list:
    """Multi-step trend forecast for the LSTM. Uses the predicted close to
    extend the window; non-close features held flat at their last
    observed normalized value (acceptable approximation for short trend)."""
    if model is None:
        return [float("nan")] * steps
    forecasts = []
    window = last_window.copy()
    model.eval()
    with torch.no_grad():
        for _ in range(steps):
            inp = torch.tensor(window, dtype=torch.float32).unsqueeze(0)
            yhat_norm = float(model(inp).item())
            forecasts.append(yhat_norm * close_sigma + close_mu)
            new_row = window[-1].copy()
            new_row[0] = yhat_norm
            window = np.vstack([window[1:], new_row])
    return forecasts


# ---------------- ARIMA ---------------------------------------------------

def _first_forecast(fit) -> float:
    """statsmodels returns ndarray in newer versions, Series in older.
    Normalize to a plain float."""
    out = fit.forecast(steps=1)
    arr = np.asarray(out)
    return float(arr.flat[0])


def _arima_walk_forward(train: np.ndarray, test: np.ndarray,
                        refit_every: int = ARIMA_REFIT_INTERVAL) -> list:
    """Walk-forward 1-step-ahead with periodic refits using actual test
    values (not predictions) to extend the history."""
    forecasts = []
    history = list(train)
    try:
        fit = ARIMA(history, order=ARIMA_ORDER).fit()
    except Exception:
        return [float("nan")] * len(test)

    for i, actual in enumerate(test):
        if i > 0 and i % refit_every == 0:
            try:
                fit = ARIMA(history, order=ARIMA_ORDER).fit()
            except Exception:
                pass
        try:
            yhat = _first_forecast(fit)
        except Exception:
            yhat = float("nan")
        forecasts.append(yhat)
        history.append(float(actual))
    return forecasts


def _arima_multi_step(history: np.ndarray, steps: int) -> list:
    try:
        fit = ARIMA(history, order=ARIMA_ORDER).fit()
        return [float(v) for v in np.asarray(fit.forecast(steps=steps)).flat]
    except Exception:
        return [float("nan")] * steps


# ---------------- Helpers -------------------------------------------------

def _mape(actual: np.ndarray, pred: list) -> float:
    pairs = [(a, p) for a, p in zip(actual, pred) if not (math.isnan(p) or a == 0)]
    if not pairs:
        return float("inf")
    return sum(abs(a - p) / abs(a) for a, p in pairs) / len(pairs)


def _regression_metrics(actual: np.ndarray, pred: list) -> dict[str, float]:
    """R², MAE, RMSE, plus walk-forward directional accuracy. Returns
    values in raw price units (MAE/RMSE) and a dimensionless R²."""
    pairs = np.array([(a, p) for a, p in zip(actual, pred) if not math.isnan(p)])
    if len(pairs) == 0:
        return {"r2": float("nan"), "mae": float("nan"), "rmse": float("nan"), "directional_acc": float("nan")}
    a, p = pairs[:, 0], pairs[:, 1]
    mae = float(np.mean(np.abs(a - p)))
    rmse = float(np.sqrt(np.mean((a - p) ** 2)))
    ss_res = float(np.sum((a - p) ** 2))
    ss_tot = float(np.sum((a - np.mean(a)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    # Directional: count cases where (predicted change) and (actual change)
    # had the same sign, using the previous actual as the anchor.
    if len(a) > 1:
        actual_diff = np.diff(a)
        pred_diff = p[1:] - a[:-1]
        matches = np.sign(actual_diff) == np.sign(pred_diff)
        directional_acc = float(np.mean(matches))
    else:
        directional_acc = float("nan")
    return {"r2": r2, "mae": mae, "rmse": rmse, "directional_acc": directional_acc}


DIRECTION_FLOOR = 0.005          # at least ±0.5% required to call UP/DOWN
DIRECTION_VOL_MULT = 0.5         # threshold = max(floor, mult × median |daily return|)
DIRECTION_VOL_LOOKBACK = 60


def _direction_threshold(closes: np.ndarray) -> float:
    """Per-stock STABLE band: half the typical absolute daily return over
    the last `DIRECTION_VOL_LOOKBACK` days (floor 0.5 %). Volatile stocks
    get wider bands; calm stocks tighter ones — so a small move on a
    high-vol stock is correctly classified as STABLE, while the same
    relative move on a quiet stock is meaningful direction."""
    if len(closes) < DIRECTION_VOL_LOOKBACK + 1:
        return DIRECTION_FLOOR
    recent = closes[-(DIRECTION_VOL_LOOKBACK + 1):]
    rets = np.diff(recent) / np.where(recent[:-1] == 0, 1, recent[:-1])
    median_abs = float(np.median(np.abs(rets)))
    return max(DIRECTION_FLOOR, DIRECTION_VOL_MULT * median_abs)


def _direction(prev: float, pred: float, threshold: float = DIRECTION_FLOOR) -> str:
    if math.isnan(pred) or math.isnan(prev):
        return "STABLE"
    diff = (pred - prev) / max(abs(prev), 1e-9)
    if diff > threshold:
        return "UP"
    if diff < -threshold:
        return "DOWN"
    return "STABLE"


# ---------------- Backtest + trend ---------------------------------------

def backtest_symbol(symbol: str, df: pd.DataFrame) -> tuple:
    df = df.sort_values("Date").reset_index(drop=True)
    closes = df["Close"].astype(float).to_numpy()
    volumes = df["Volume"].astype(float).fillna(0).to_numpy() if "Volume" in df else np.zeros_like(closes)
    if len(closes) < MIN_HISTORY:
        return [], None, []

    train_closes = closes[:-BACKTEST_DAYS]
    test_closes = closes[-BACKTEST_DAYS:]
    train_vols = volumes[:-BACKTEST_DAYS]

    test_dates = df["Date"].iloc[-BACKTEST_DAYS:].tolist()

    # ARIMA walk-forward
    arima_preds = _arima_walk_forward(train_closes, test_closes)

    # LSTM: features built on train slice only; train once; walk-forward predict
    train_feats, mu_train, sigma_train = _build_features(train_closes, train_vols)
    model = _train_lstm(train_feats, LSTM_LOOKBACK)
    lstm_preds = [float("nan")] * BACKTEST_DAYS
    if model is not None:
        save_lstm(symbol, model.state_dict(), mu_train, sigma_train)
        # Build features over the full series using train-time mu/sigma so
        # the model sees the same normalization at test time.
        full_closes_for_norm = closes
        full_vols_for_norm = volumes
        n = len(full_closes_for_norm)
        ret1 = np.zeros(n); ret1[1:] = np.diff(full_closes_for_norm) / np.where(full_closes_for_norm[:-1] == 0, 1, full_closes_for_norm[:-1])
        ret5 = np.zeros(n)
        if n > 5:
            ret5[5:] = (full_closes_for_norm[5:] - full_closes_for_norm[:-5]) / np.where(full_closes_for_norm[:-5] == 0, 1, full_closes_for_norm[:-5])
        full_feats = (np.stack([full_closes_for_norm, full_vols_for_norm, ret1, ret5], axis=1).astype(np.float32) - mu_train) / sigma_train
        lstm_preds = _lstm_walk_forward(
            model, full_feats, train_len=len(train_closes), test_len=BACKTEST_DAYS,
            lookback=LSTM_LOOKBACK, close_mu=float(mu_train[0]), close_sigma=float(sigma_train[0]),
        )

    arima_mape = _mape(test_closes, arima_preds)
    lstm_mape = _mape(test_closes, lstm_preds)
    best_model = "ARIMA" if arima_mape <= lstm_mape else "LSTM"
    best_forecast = arima_preds if best_model == "ARIMA" else lstm_preds

    with mlflow_utils.run("forecasting_v2", run_name=symbol, nested=True,
                          tags={"symbol": symbol, "mode": "cold"}):
        mlflow_utils.log_params({
            "arima_order": str(ARIMA_ORDER),
            "arima_refit_interval": ARIMA_REFIT_INTERVAL,
            "lstm_lookback": LSTM_LOOKBACK,
            "lstm_hidden": LSTM_HIDDEN,
            "lstm_layers": LSTM_LAYERS,
            "lstm_dropout": LSTM_DROPOUT,
            "lstm_lr": LSTM_LR,
            "lstm_patience": LSTM_PATIENCE,
            "lstm_batch": LSTM_BATCH,
            "backtest_days": BACKTEST_DAYS,
            "features": ",".join(LSTM_FEATURES),
            "train_rows": int(len(train_closes)),
        })
        arima_extra = _regression_metrics(test_closes, arima_preds)
        lstm_extra = _regression_metrics(test_closes, lstm_preds)
        mlflow_utils.log_metrics({
            "arima_mape": arima_mape if math.isfinite(arima_mape) else None,
            "lstm_mape": lstm_mape if math.isfinite(lstm_mape) else None,
            "best_mape": min(arima_mape, lstm_mape) if math.isfinite(min(arima_mape, lstm_mape)) else None,
            "arima_r2": arima_extra["r2"],
            "arima_mae": arima_extra["mae"],
            "arima_rmse": arima_extra["rmse"],
            "arima_directional_acc": arima_extra["directional_acc"],
            "lstm_r2": lstm_extra["r2"],
            "lstm_mae": lstm_extra["mae"],
            "lstm_rmse": lstm_extra["rmse"],
            "lstm_directional_acc": lstm_extra["directional_acc"],
        })
        if model is not None:
            lstm_artifact = DATA_DIR / "models" / symbol / "lstm.pt"
            if lstm_artifact.exists():
                mlflow_utils.log_artifact(lstm_artifact, artifact_path=f"{symbol}/lstm")

    # Dynamic per-stock STABLE band — derived from train data so the
    # backtest honours the same threshold actuals are evaluated against.
    threshold = _direction_threshold(train_closes)

    rows = []
    prev_actual = float(train_closes[-1])
    for i, (date, actual) in enumerate(zip(test_dates, test_closes)):
        rows.append({
            "Symbol": symbol,
            "Date": pd.Timestamp(date).isoformat(),
            "Close": float(actual),
            "Forecasting_ARIMA": arima_preds[i] if not math.isnan(arima_preds[i]) else None,
            "Forecasting_LSTM": lstm_preds[i] if not math.isnan(lstm_preds[i]) else None,
            "Forecasting_Best": best_forecast[i] if not math.isnan(best_forecast[i]) else None,
            "Best_Model": best_model,
            "Direction_ARIMA": _direction(prev_actual, arima_preds[i], threshold),
            "Direction_LSTM": _direction(prev_actual, lstm_preds[i], threshold),
            "Direction_Best": _direction(prev_actual, best_forecast[i], threshold),
            "DirectionThreshold": round(threshold, 5),
        })
        prev_actual = float(actual)

    summary = {
        "Symbol": symbol,
        "ARIMA_MAPE": round(arima_mape, 4) if math.isfinite(arima_mape) else None,
        "LSTM_MAPE": round(lstm_mape, 4) if math.isfinite(lstm_mape) else None,
        "Best_Model": best_model,
        "Best_MAPE": round(min(arima_mape, lstm_mape), 4),
        "BacktestDays": BACKTEST_DAYS,
        "DirectionThreshold": round(threshold, 5),
    }

    # ------------- 30-day forward trend forecast ------------------
    last_close = float(closes[-1])
    last_date = pd.Timestamp(df["Date"].iloc[-1])
    business_days = pd.bdate_range(start=last_date + pd.Timedelta(days=1), periods=FUTURE_HORIZON)

    trend_preds = _arima_multi_step(closes, FUTURE_HORIZON)  # ARIMA — robust over multi-step
    trend_rows = []
    # Trend Direction is **cumulative-vs-anchor**: where does the predicted
    # close stand relative to today's close? (The previous bug compared
    # day-vs-prev-day which rounds to STABLE since multi-step ARIMA drifts
    # smoothly.) Threshold scales with horizon — a tiny move on day +30
    # shouldn't read the same as a tiny move on day +1.
    for d, yhat in zip(business_days, trend_preds):
        if math.isnan(yhat):
            continue
        days_ahead = (d - last_date).days
        # Larger STABLE band further out — ARIMA's variance grows with horizon.
        horizon_factor = max(1.0, days_ahead / 5)
        trend_threshold = threshold * horizon_factor
        change_pct = (float(yhat) - last_close) / max(abs(last_close), 1e-9)
        trend_rows.append({
            "Symbol": symbol,
            "Date": d.isoformat(),
            "PredictedClose": round(float(yhat), 4),
            "Direction": _direction(last_close, float(yhat), trend_threshold),
            "ChangePctFromAnchor": round(change_pct * 100, 4),
            "Model": "ARIMA",
            "BasedOnLastClose": round(last_close, 4),
            "DaysAhead": days_ahead,
        })

    return rows, summary, trend_rows


def forecast_symbol_warm(symbol: str, df: pd.DataFrame, prior_summary: dict | None = None) -> tuple:
    """Warm-mode 1-step-ahead forecast using cached LSTM + fresh ARIMA fit.

    Returns (rows, summary, trend_rows) shaped like backtest_symbol() but
    `rows` contains a SINGLE new row (latest date) and `summary` reuses
    cold-mode MAPE / Best_Model from `prior_summary` so accuracy estimates
    don't drift on every warm run.
    """
    df = df.sort_values("Date").reset_index(drop=True)
    closes = df["Close"].astype(float).to_numpy()
    volumes = df["Volume"].astype(float).fillna(0).to_numpy() if "Volume" in df else np.zeros_like(closes)
    if len(closes) < LSTM_LOOKBACK + 2:
        return [], None, []

    cache = load_lstm(symbol)
    if cache is None or prior_summary is None:
        # No cached artifact — fall back to cold backtest for this symbol.
        return backtest_symbol(symbol, df)

    mu = cache["mu"]
    sigma = cache["sigma"]

    # Build features over the full series, normalize with cached mu/sigma.
    n = len(closes)
    ret1 = np.zeros(n)
    ret1[1:] = np.diff(closes) / np.where(closes[:-1] == 0, 1, closes[:-1])
    ret5 = np.zeros(n)
    if n > 5:
        ret5[5:] = (closes[5:] - closes[:-5]) / np.where(closes[:-5] == 0, 1, closes[:-5])
    full_feats = (
        np.stack([closes, volumes, ret1, ret5], axis=1).astype(np.float32) - mu
    ) / sigma

    model = StockLSTM(input_size=N_FEATURES, hidden=LSTM_HIDDEN, num_layers=LSTM_LAYERS)
    model.load_state_dict(cache["state_dict"])
    model.eval()

    # Predict latest date: window ends one day before, predicts the latest close.
    if len(full_feats) < LSTM_LOOKBACK + 1:
        return [], None, []
    window = full_feats[-LSTM_LOOKBACK - 1 : -1]
    with torch.no_grad():
        yhat_norm = float(model(torch.tensor(window, dtype=torch.float32).unsqueeze(0)).item())
    lstm_pred = yhat_norm * float(sigma[0]) + float(mu[0])

    # ARIMA: fit on history through day-before-latest, 1-step ahead.
    history = closes[:-1]
    try:
        fit = ARIMA(history, order=ARIMA_ORDER).fit()
        arima_pred = _first_forecast(fit)
    except Exception:
        arima_pred = float("nan")

    # Pick model per cold-trained best_models.json — accuracy estimates are
    # a property of the trained model, not of any single warm-day prediction.
    best_model = prior_summary.get("Best_Model", "ARIMA")
    best_pred = arima_pred if best_model == "ARIMA" else lstm_pred

    threshold = _direction_threshold(closes[:-1])
    prev_actual = float(closes[-2])
    actual = float(closes[-1])
    last_date = pd.Timestamp(df["Date"].iloc[-1])

    rows = [{
        "Symbol": symbol,
        "Date": last_date.isoformat(),
        "Close": actual,
        "Forecasting_ARIMA": arima_pred if not math.isnan(arima_pred) else None,
        "Forecasting_LSTM": lstm_pred if not math.isnan(lstm_pred) else None,
        "Forecasting_Best": best_pred if not math.isnan(best_pred) else None,
        "Best_Model": best_model,
        "Direction_ARIMA": _direction(prev_actual, arima_pred, threshold),
        "Direction_LSTM": _direction(prev_actual, lstm_pred, threshold),
        "Direction_Best": _direction(prev_actual, best_pred, threshold),
        "DirectionThreshold": round(threshold, 5),
    }]

    # Reuse cold-mode summary verbatim — MAPE estimate is stable.
    summary = dict(prior_summary)
    summary["DirectionThreshold"] = round(threshold, 5)

    # Trend forecast — regenerate from updated last_close.
    last_close = float(closes[-1])
    business_days = pd.bdate_range(start=last_date + pd.Timedelta(days=1), periods=FUTURE_HORIZON)
    trend_preds = _arima_multi_step(closes, FUTURE_HORIZON)
    trend_rows = []
    for d, yhat in zip(business_days, trend_preds):
        if math.isnan(yhat):
            continue
        days_ahead = (d - last_date).days
        horizon_factor = max(1.0, days_ahead / 5)
        trend_threshold = threshold * horizon_factor
        change_pct = (float(yhat) - last_close) / max(abs(last_close), 1e-9)
        trend_rows.append({
            "Symbol": symbol,
            "Date": d.isoformat(),
            "PredictedClose": round(float(yhat), 4),
            "Direction": _direction(last_close, float(yhat), trend_threshold),
            "ChangePctFromAnchor": round(change_pct * 100, 4),
            "Model": "ARIMA",
            "BasedOnLastClose": round(last_close, 4),
            "DaysAhead": days_ahead,
        })

    return rows, summary, trend_rows


def get_forecast(ticker: str) -> dict:
    """One-step-ahead forecast for a single ticker (Django shim)."""
    if not HISTORICAL_FILE.exists():
        return {"ticker": ticker, "direction": "STABLE", "confidence": 0.0, "predicted_price": 0.0}

    raw = json.loads(HISTORICAL_FILE.read_text())
    df = pd.DataFrame([r for r in raw if r.get("Symbol") == ticker])
    if df.empty:
        return {"ticker": ticker, "direction": "STABLE", "confidence": 0.0, "predicted_price": 0.0}

    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date").reset_index(drop=True)
    closes = df["Close"].astype(float).to_numpy()
    if len(closes) < MIN_HISTORY:
        return {"ticker": ticker, "direction": "STABLE", "confidence": 0.0, "predicted_price": float(closes[-1])}

    pred = _arima_multi_step(closes, 1)[0]
    last = float(closes[-1])
    return {
        "ticker": ticker,
        "direction": _direction(last, pred),
        "confidence": 0.6,
        "predicted_price": float(pred) if not math.isnan(pred) else last,
        "model_used": "ARIMA",
    }


def main(warm: bool = False) -> None:
    if not HISTORICAL_FILE.exists():
        print(f"missing {HISTORICAL_FILE} — run historical_scraper first")
        return

    raw = json.loads(HISTORICAL_FILE.read_text())
    df = pd.DataFrame(raw)
    if df.empty:
        print("historical_data.json is empty")
        return

    df["Date"] = pd.to_datetime(df["Date"])

    if warm:
        # Warm: append today's prediction row to existing files without retraining.
        if not (OUTPUT_FILE.exists() and BEST_MODEL_FILE.exists()):
            print("warm mode requires prior cold-run artifacts (best_models.json + stock_forecasts.json).")
            print("running cold instead.")
            warm = False
        else:
            existing_rows = json.loads(OUTPUT_FILE.read_text())
            existing_summaries = json.loads(BEST_MODEL_FILE.read_text())
            summary_by_sym = {s["Symbol"]: s for s in existing_summaries}
            new_trend = []
            appended = 0
            cold_fallbacks = 0
            for symbol, group in df.groupby("Symbol"):
                stale, age = _is_stale(group)
                if stale:
                    print(f"{symbol}: skipped (stale, last data {age}d old)")
                    continue
                prior = summary_by_sym.get(symbol)
                rows, summary, trend = forecast_symbol_warm(symbol, group, prior)
                if not rows:
                    print(f"{symbol}: skipped (insufficient history)")
                    continue
                if prior is None or len(rows) > 1:
                    # Fell back to cold for this symbol — replace its rows.
                    cold_fallbacks += 1
                    existing_rows = [r for r in existing_rows if r.get("Symbol") != symbol]
                    existing_rows.extend(rows)
                    summary_by_sym[symbol] = summary
                    new_trend.extend(trend)
                    print(f"{symbol}: cold fallback (no cache)")
                else:
                    # Warm path: append the single new row, dedup by (Symbol, Date).
                    new_date = rows[0]["Date"]
                    existing_rows = [
                        r for r in existing_rows
                        if not (r.get("Symbol") == symbol and r.get("Date") == new_date)
                    ]
                    existing_rows.extend(rows)
                    summary_by_sym[symbol] = summary
                    new_trend.extend(trend)
                    appended += 1
                    pred = rows[0].get("Forecasting_Best")
                    actual = rows[0].get("Close")
                    pred_s = f"{pred:.2f}" if pred is not None else "nan"
                    print(f"{symbol}: warm | actual={actual:.2f} pred={pred_s} model={rows[0]['Best_Model']}")

            # Trend file: keep rows for symbols we didn't refresh; replace those we did.
            existing_trend = json.loads(TREND_FILE.read_text()) if TREND_FILE.exists() else []
            refreshed_syms = {r["Symbol"] for r in new_trend}
            preserved_trend = [r for r in existing_trend if r["Symbol"] not in refreshed_syms]
            all_trend = preserved_trend + new_trend

            OUTPUT_FILE.write_text(json.dumps(existing_rows, indent=2, default=str))
            BEST_MODEL_FILE.write_text(json.dumps(list(summary_by_sym.values()), indent=2))
            TREND_FILE.write_text(json.dumps(all_trend, indent=2, default=str))
            print(f"\nwarm: appended {appended} rows, {cold_fallbacks} cold fallbacks")
            print(f"wrote {len(existing_rows)} total rows -> {OUTPUT_FILE}")
            print(f"wrote {len(summary_by_sym)} summaries -> {BEST_MODEL_FILE}")
            print(f"wrote {len(all_trend)} trend rows     -> {TREND_FILE}")
            return

    # Cold mode (default, also fallback if warm was requested but no prior artifacts).
    import time as _time
    batch_started = _time.time()
    with mlflow_utils.run("forecasting_v2", run_name=f"batch_cold_{int(batch_started)}",
                          tags={"mode": "cold", "kind": "batch"}):
        all_rows, summaries, all_trend = [], [], []
        stale_skipped = 0
        for symbol, group in df.groupby("Symbol"):
            stale, age = _is_stale(group)
            if stale:
                stale_skipped += 1
                print(f"{symbol}: skipped (stale, last data {age}d old)")
                continue
            rows, summary, trend = backtest_symbol(symbol, group)
            if rows:
                all_rows.extend(rows)
                summaries.append(summary)
                all_trend.extend(trend)
                arima_p = (summary["ARIMA_MAPE"] or 0) * 100
                lstm_p = (summary["LSTM_MAPE"] or 0) * 100
                print(
                    f"{symbol}: ARIMA {arima_p:5.2f}% | LSTM {lstm_p:5.2f}% | "
                    f"best={summary['Best_Model']} | trend={len(trend)} days"
                )
            else:
                print(f"{symbol}: skipped (need >= {MIN_HISTORY} closes, have {len(group)})")

        OUTPUT_FILE.write_text(json.dumps(all_rows, indent=2, default=str))
        BEST_MODEL_FILE.write_text(json.dumps(summaries, indent=2))
        TREND_FILE.write_text(json.dumps(all_trend, indent=2, default=str))
        print(f"\nwrote {len(all_rows)} backtest rows -> {OUTPUT_FILE}")
        print(f"wrote {len(summaries)} summaries  -> {BEST_MODEL_FILE}")
        print(f"wrote {len(all_trend)} trend rows -> {TREND_FILE}")
        arima_wins = sum(1 for s in summaries if s["Best_Model"] == "ARIMA")
        lstm_wins = sum(1 for s in summaries if s["Best_Model"] == "LSTM")
        print(f"  ARIMA wins: {arima_wins}")
        print(f"  LSTM wins:  {lstm_wins}")

        arima_mapes = [s["ARIMA_MAPE"] for s in summaries if s["ARIMA_MAPE"] is not None]
        lstm_mapes = [s["LSTM_MAPE"] for s in summaries if s["LSTM_MAPE"] is not None]
        best_mapes = [s["Best_MAPE"] for s in summaries if s["Best_MAPE"] is not None]
        mlflow_utils.log_params({"backtest_days": BACKTEST_DAYS, "horizons": FUTURE_HORIZON})
        mlflow_utils.log_metrics({
            "symbols_total": len(summaries),
            "arima_wins": arima_wins,
            "lstm_wins": lstm_wins,
            "median_arima_mape": float(np.median(arima_mapes)) if arima_mapes else None,
            "median_lstm_mape": float(np.median(lstm_mapes)) if lstm_mapes else None,
            "median_best_mape": float(np.median(best_mapes)) if best_mapes else None,
            "batch_duration_sec": _time.time() - batch_started,
        })


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--warm", action="store_true",
                        help="Skip retraining; load cached LSTMs and append today's prediction row.")
    args = parser.parse_args()
    main(warm=args.warm)
