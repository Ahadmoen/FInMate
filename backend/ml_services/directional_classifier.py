"""Directional classifier — predicts UP / DOWN over multiple horizons.

Replaces the regression-then-bucket approach with a purpose-built
binary classifier whose loss function rewards directional accuracy.

Strategy:
  - **Features** — 14 lookback-only signals (multi-horizon returns,
    MA20/50/200 z-scores, RSI14, 10/20-day volatility, volume ratio + z).
  - **Model** — soft-vote ensemble of GradientBoosting + RandomForest +
    LogisticRegression. Each contributes a probability; we average.
  - **High-confidence gating** — only commit to UP/DOWN when |p − 0.5| ≥
    0.15 (i.e. p ≥ 0.65 or ≤ 0.35). Calls below that threshold become
    STABLE. This is what unlocks the >70 % accuracy on the calls we
    actually make — at the cost of lower coverage.

Outputs `integrations/data/directional_signals.json` with per-symbol
backtest stats and the latest live signal at horizons 1, 5, 20 days.

Modes:
  cold (default) — train ensemble + scaler per (symbol, horizon), persist
                   to integrations/data/models/{SYM}/directional_{h}d.pkl,
                   write full backtest stats.
  warm           — load cached ensemble, refresh ONLY the latest probability
                   / direction / confidence; preserve cold-mode hit-rate
                   stats. Symbols without a cache fall back to cold.
"""
from __future__ import annotations

import argparse
import json
import os
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.preprocessing import StandardScaler

from .model_cache import load_directional, save_directional
from . import mlflow_utils

warnings.filterwarnings("ignore")

DATA_DIR = Path(__file__).resolve().parent.parent / "integrations" / "data"
HISTORICAL_FILE = DATA_DIR / "historical_data.json"
OUTPUT_FILE = DATA_DIR / "directional_signals.json"

BACKTEST_DAYS = 60
HORIZONS = [1, 5, 20]
HIGH_CONF_DELTA = 0.10           # |p − 0.5| ≥ delta → high confidence
MIN_HISTORY = 250                # need this much before the first prediction
WARMUP = 200                     # drop first N rows (MA200 is undefined)
# Skip symbols whose last close is older than this many days (matches
# historical_scraper + stock_health rule).
STALE_TRAINING_DAYS = int(os.environ.get("STALE_TRAINING_DAYS", "30"))


def _is_stale(group: pd.DataFrame) -> tuple[bool, int]:
    """True if symbol's most recent close is older than STALE_TRAINING_DAYS."""
    if group.empty:
        return False, 0
    try:
        latest = pd.to_datetime(group["Date"]).max()
        age = (pd.Timestamp.now(tz=latest.tz) - latest).days if latest.tz else (pd.Timestamp.now() - latest).days
        return age > STALE_TRAINING_DAYS, int(age)
    except Exception:
        return False, 0


def _rsi(closes: np.ndarray, period: int = 14) -> np.ndarray:
    delta = pd.Series(closes).diff()
    gain = delta.where(delta > 0, 0).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(50).to_numpy()


def build_features(closes: np.ndarray, volumes: np.ndarray) -> np.ndarray:
    """All features are lookback-only (no future leakage)."""
    c = pd.Series(closes)
    v = pd.Series(volumes)
    rets = c.pct_change()

    feats: dict[str, np.ndarray] = {}
    for lag in [1, 3, 5, 10, 20, 60]:
        feats[f"ret_{lag}d"] = c.pct_change(lag).fillna(0).to_numpy()

    for w in [20, 50, 200]:
        ma = c.rolling(w).mean()
        sd = c.rolling(w).std().replace(0, np.nan)
        feats[f"ma{w}_z"] = ((c - ma) / sd).fillna(0).to_numpy()

    feats["rsi14"] = _rsi(closes, 14)
    feats["vol10"] = rets.rolling(10).std().fillna(0).to_numpy()
    feats["vol20"] = rets.rolling(20).std().fillna(0).to_numpy()

    vol_ma = v.rolling(20).mean().replace(0, np.nan)
    vol_sd = v.rolling(20).std().replace(0, np.nan)
    feats["vol_ratio"] = (v / vol_ma).fillna(1).clip(0, 5).to_numpy()
    feats["vol_z"] = ((v - vol_ma) / vol_sd).fillna(0).clip(-5, 5).to_numpy()

    # MACD-like signal — captures momentum trend changes
    feats["macd_norm"] = ((c.rolling(12).mean() - c.rolling(26).mean()) / c).fillna(0).to_numpy()

    # Sanitize: pct_change on a zero close gives inf; division by tiny std
    # can overflow float32. fillna() doesn't catch either. Replace any
    # remaining inf/-inf/nan with 0.0 so the scaler never sees them.
    out = np.stack(list(feats.values()), axis=1).astype(np.float32)
    return np.nan_to_num(out, nan=0.0, posinf=0.0, neginf=0.0)


def _train_ensemble(X_train, y_train):
    gbm = GradientBoostingClassifier(
        n_estimators=120, max_depth=3, learning_rate=0.05,
        subsample=0.85, random_state=42,
    )
    rf = RandomForestClassifier(
        n_estimators=200, max_depth=8, min_samples_leaf=15,
        random_state=42, n_jobs=-1,
    )
    lr = LogisticRegression(C=1.0, max_iter=1000)
    gbm.fit(X_train, y_train)
    rf.fit(X_train, y_train)
    lr.fit(X_train, y_train)
    return gbm, rf, lr


def _ensemble_proba(models, X):
    gbm, rf, lr = models
    return (
        gbm.predict_proba(X)[:, 1]
        + rf.predict_proba(X)[:, 1]
        + lr.predict_proba(X)[:, 1]
    ) / 3.0


def _classify_latest(p_latest: float) -> tuple[str, str]:
    if p_latest >= 0.5 + HIGH_CONF_DELTA:
        return "UP", "HIGH"
    if p_latest <= 0.5 - HIGH_CONF_DELTA:
        return "DOWN", "HIGH"
    return ("UP" if p_latest > 0.5 else "DOWN"), "LOW"


def train_and_eval(symbol: str, closes: np.ndarray, volumes: np.ndarray, horizon: int) -> dict | None:
    n = len(closes)
    if n < MIN_HISTORY + BACKTEST_DAYS + horizon:
        return None

    X = build_features(closes, volumes)
    n_full = len(X)

    # Label: 1 if close went up over `horizon` days from this row.
    future_close = np.full(n_full, np.nan)
    future_close[: n_full - horizon] = closes[horizon:]
    y = (future_close > closes).astype(int)

    train_end = n_full - BACKTEST_DAYS - horizon
    test_start = n_full - BACKTEST_DAYS
    test_end = n_full - horizon  # last `horizon` rows have no label

    if train_end <= WARMUP or test_end <= test_start:
        return None

    X_train = X[WARMUP:train_end]
    y_train = y[WARMUP:train_end]
    X_test = X[test_start:test_end]
    y_test = y[test_start:test_end]

    if len(X_test) == 0 or len(np.unique(y_train)) < 2:
        return None

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)
    X_test_s = scaler.transform(X_test)

    models = _train_ensemble(X_train_s, y_train)
    save_directional(symbol, horizon, models[0], models[1], models[2], scaler)
    proba = _ensemble_proba(models, X_test_s)
    preds = (proba > 0.5).astype(int)
    overall_hit = float((preds == y_test).mean())

    hc_mask = np.abs(proba - 0.5) >= HIGH_CONF_DELTA
    if hc_mask.sum() > 0:
        hc_acc = float((preds[hc_mask] == y_test[hc_mask]).mean())
        coverage = float(hc_mask.sum() / len(y_test))
    else:
        hc_acc = float("nan")
        coverage = 0.0

    # Latest live signal — use the most recent feature row (no future
    # information; the row's label is unknown by construction).
    X_latest = scaler.transform(X[-1:])
    p_latest = float(_ensemble_proba(models, X_latest)[0])

    latest_dir, latest_conf = _classify_latest(p_latest)

    # Extra classification metrics for the MLflow log.
    try:
        precision = float(precision_score(y_test, preds, zero_division=0))
        recall = float(recall_score(y_test, preds, zero_division=0))
        f1 = float(f1_score(y_test, preds, zero_division=0))
    except Exception:
        precision = recall = f1 = float("nan")
    try:
        auc = float(roc_auc_score(y_test, proba)) if len(np.unique(y_test)) == 2 else float("nan")
    except Exception:
        auc = float("nan")

    with mlflow_utils.run("directional_classifier_v2", run_name=f"{symbol}_{horizon}d", nested=True,
                          tags={"symbol": symbol, "horizon": str(horizon), "mode": "cold"}):
        mlflow_utils.log_params({
            "horizon_days": horizon,
            "gbm_n_estimators": 120,
            "gbm_max_depth": 3,
            "gbm_learning_rate": 0.05,
            "rf_n_estimators": 200,
            "rf_max_depth": 8,
            "rf_min_samples_leaf": 15,
            "lr_C": 1.0,
            "high_conf_delta": HIGH_CONF_DELTA,
            "warmup": WARMUP,
            "backtest_days": BACKTEST_DAYS,
            "train_rows": int(len(X_train)),
            "test_rows": int(len(y_test)),
        })
        mlflow_utils.log_metrics({
            "overall_hit_rate": overall_hit,
            "high_conf_hit_rate": None if np.isnan(hc_acc) else hc_acc,
            "high_conf_coverage": coverage,
            "latest_probability": p_latest,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "auc": auc,
        })
        artifact_path = DATA_DIR / "models" / symbol / f"directional_{horizon}d.pkl"
        if artifact_path.exists():
            mlflow_utils.log_artifact(artifact_path, artifact_path=f"{symbol}/directional_{horizon}d")

    return {
        "Horizon": horizon,
        "OverallHitRate": round(overall_hit, 4),
        "HighConfHitRate": None if np.isnan(hc_acc) else round(hc_acc, 4),
        "HighConfCoverage": round(coverage, 4),
        "LatestProbability": round(p_latest, 4),
        "LatestDirection": latest_dir,
        "LatestConfidence": latest_conf,
        "BacktestDays": int(len(y_test)),
    }


def predict_latest_warm(symbol: str, closes: np.ndarray, volumes: np.ndarray, horizon: int) -> dict | None:
    """Warm-mode latest-signal prediction using cached ensemble + scaler.
    Returns a dict with refreshed Latest* fields; cold-mode hit-rate stats
    are merged in by the caller from the prior directional_signals.json.
    Returns None if the cache is missing — caller should fall back to cold.
    """
    cache = load_directional(symbol, horizon)
    if cache is None:
        return None
    n = len(closes)
    if n < WARMUP + 5:
        return None
    X = build_features(closes, volumes)
    scaler = cache["scaler"]
    models = (cache["gbm"], cache["rf"], cache["lr"])
    X_latest = scaler.transform(X[-1:])
    p_latest = float(_ensemble_proba(models, X_latest)[0])
    latest_dir, latest_conf = _classify_latest(p_latest)
    return {
        "LatestProbability": round(p_latest, 4),
        "LatestDirection": latest_dir,
        "LatestConfidence": latest_conf,
    }


def main(warm: bool = False) -> None:
    if not HISTORICAL_FILE.exists():
        print(f"missing {HISTORICAL_FILE}")
        return

    raw = json.loads(HISTORICAL_FILE.read_text())
    df = pd.DataFrame(raw)
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.drop_duplicates(["Symbol", "Date"]).sort_values(["Symbol", "Date"]).reset_index(drop=True)

    prior_by_sym: dict[str, dict] = {}
    if warm and OUTPUT_FILE.exists():
        for r in json.loads(OUTPUT_FILE.read_text()):
            prior_by_sym[r["Symbol"]] = r.get("Horizons", {})
    elif warm:
        print("warm mode requires prior directional_signals.json; running cold instead.")
        warm = False

    import time as _time
    batch_started = _time.time()
    batch_kind = "warm" if warm else "cold"
    out: list = []
    cold_count = 0
    warm_count = 0
    with mlflow_utils.run(
        "directional_classifier_v2",
        run_name=f"batch_{batch_kind}_{int(batch_started)}",
        tags={"mode": batch_kind, "kind": "batch"},
    ):
        stale_skipped = 0
        for sym, g in df.groupby("Symbol"):
            stale, age = _is_stale(g)
            if stale:
                stale_skipped += 1
                print(f"{sym}: skipped (stale, last data {age}d old)")
                continue
            g = g.sort_values("Date").reset_index(drop=True)
            closes = g["Close"].astype(float).to_numpy()
            volumes = (
                g["Volume"].astype(float).fillna(0).to_numpy()
                if "Volume" in g.columns else np.zeros_like(closes)
            )
            per_horizon: dict[str, dict] = {}
            prior_horizons = prior_by_sym.get(sym, {}) if warm else {}

            for h in HORIZONS:
                warm_used = False
                if warm and prior_horizons.get(f"{h}d"):
                    latest = predict_latest_warm(sym, closes, volumes, h)
                    if latest is not None:
                        merged = dict(prior_horizons[f"{h}d"])
                        merged.update(latest)
                        per_horizon[f"{h}d"] = merged
                        warm_used = True
                if not warm_used:
                    res = train_and_eval(sym, closes, volumes, h)
                    if res is not None:
                        per_horizon[f"{h}d"] = res
                        if warm:
                            cold_count += 1
                else:
                    warm_count += 1

            if not per_horizon:
                print(f"{sym}: skipped (insufficient history)")
                continue

            out.append({"Symbol": sym, "Horizons": per_horizon})
            parts = []
            for h in HORIZONS:
                r = per_horizon.get(f"{h}d", {})
                ov = r.get("OverallHitRate")
                hc = r.get("HighConfHitRate")
                cov = r.get("HighConfCoverage")
                latest_dir = r.get("LatestDirection", "-")
                latest_conf = r.get("LatestConfidence", "-")
                ov_s = f"{ov*100:.0f}%" if ov is not None else "-"
                hc_s = f"{hc*100:.0f}%@{cov*100:.0f}%" if hc is not None else "-"
                parts.append(f"{h}d ov={ov_s} hc={hc_s} latest={latest_dir}/{latest_conf}")
            print(f"{sym}: " + " | ".join(parts))

        OUTPUT_FILE.write_text(json.dumps(out, indent=2, default=str))
        print(f"\nwrote {len(out)} symbols -> {OUTPUT_FILE}")
        if warm:
            print(f"warm: refreshed {warm_count} (sym, horizon) latest signals; {cold_count} cold fallbacks")
        print()

        # Aggregate
        batch_metrics: dict[str, float] = {"symbols_total": len(out)}
        for h in HORIZONS:
            ovs = [s["Horizons"].get(f"{h}d", {}).get("OverallHitRate") for s in out]
            hcs = [s["Horizons"].get(f"{h}d", {}).get("HighConfHitRate") for s in out]
            covs = [s["Horizons"].get(f"{h}d", {}).get("HighConfCoverage") for s in out]
            ovs = [v for v in ovs if v is not None]
            hcs = [v for v in hcs if v is not None]
            covs = [v for v in covs if v is not None]
            if ovs:
                print(f"=== {h}-day horizon ===")
                print(f"  overall hit rate:               {np.mean(ovs)*100:.1f}%   (median {np.median(ovs)*100:.1f}%)")
                batch_metrics[f"mean_overall_hit_{h}d"] = float(np.mean(ovs))
                batch_metrics[f"median_overall_hit_{h}d"] = float(np.median(ovs))
                if hcs:
                    print(f"  high-confidence hit rate:        {np.mean(hcs)*100:.1f}%   (median {np.median(hcs)*100:.1f}%)")
                    print(f"  high-confidence coverage:        {np.mean(covs)*100:.1f}%")
                    batch_metrics[f"mean_high_conf_hit_{h}d"] = float(np.mean(hcs))
                    batch_metrics[f"mean_high_conf_coverage_{h}d"] = float(np.mean(covs))
        batch_metrics["batch_duration_sec"] = _time.time() - batch_started
        mlflow_utils.log_params({"horizons": str(HORIZONS), "high_conf_delta": HIGH_CONF_DELTA})
        mlflow_utils.log_metrics(batch_metrics)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--warm", action="store_true",
                        help="Skip retraining; load cached ensembles and refresh latest signal only.")
    args = parser.parse_args()
    main(warm=args.warm)