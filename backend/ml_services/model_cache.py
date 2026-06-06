"""Per-symbol artifact cache for warm-mode pipeline runs.

Layout:
  integrations/data/models/{SYMBOL}/
    lstm.pt                # state_dict + (mu, sigma) for normalization
    directional_{h}d.pkl   # {gbm, rf, lr, scaler} for horizon h

Cold mode runs save here; warm mode loads them to skip retraining.
Symbols missing from the cache fall back to cold (full retrain).
"""
from __future__ import annotations

import pickle
from pathlib import Path

import numpy as np
import torch

DATA_DIR = Path(__file__).resolve().parent.parent / "integrations" / "data"
MODEL_DIR = DATA_DIR / "models"


def _symbol_dir(symbol: str) -> Path:
    d = MODEL_DIR / symbol
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_lstm(symbol: str, state_dict: dict, mu: np.ndarray, sigma: np.ndarray) -> None:
    path = _symbol_dir(symbol) / "lstm.pt"
    torch.save(
        {
            "state_dict": state_dict,
            "mu": np.asarray(mu, dtype=float).tolist(),
            "sigma": np.asarray(sigma, dtype=float).tolist(),
        },
        path,
    )


def load_lstm(symbol: str) -> dict | None:
    path = MODEL_DIR / symbol / "lstm.pt"
    if not path.exists():
        return None
    blob = torch.load(path, weights_only=False, map_location="cpu")
    return {
        "state_dict": blob["state_dict"],
        "mu": np.asarray(blob["mu"], dtype=np.float32),
        "sigma": np.asarray(blob["sigma"], dtype=np.float32),
    }


def save_directional(symbol: str, horizon: int, gbm, rf, lr, scaler) -> None:
    path = _symbol_dir(symbol) / f"directional_{horizon}d.pkl"
    with path.open("wb") as f:
        pickle.dump({"gbm": gbm, "rf": rf, "lr": lr, "scaler": scaler}, f)


def load_directional(symbol: str, horizon: int) -> dict | None:
    path = MODEL_DIR / symbol / f"directional_{horizon}d.pkl"
    if not path.exists():
        return None
    with path.open("rb") as f:
        return pickle.load(f)


def has_lstm_cache(symbol: str) -> bool:
    return (MODEL_DIR / symbol / "lstm.pt").exists()


def has_directional_cache(symbol: str, horizon: int) -> bool:
    return (MODEL_DIR / symbol / f"directional_{horizon}d.pkl").exists()
