"""Fusion engine — combines forecast + sentiment + technical signals into
a single health score with **dynamic per-stock weights** and **divergence
damping**.

Two adaptive behaviors:

1. **Quality-based weighting.** Each component carries a quality score in
   `[0, 1]` reflecting how much we trust *this signal for this symbol*
   right now (forecast MAPE, news coverage / recency / magnitude,
   technical history length / RSI decisiveness). Weights are normalized
   from those qualities so a symbol with sparse news naturally
   de-emphasizes the news component for that symbol — and so on.

2. **Divergence damping.** When the forecast is extreme (|score| ≥ 0.5)
   and the average of the other two signals points the *opposite* way,
   the forecast is dampened (up to 40 %) before fusion. This stops a
   bullish ARIMA from overruling a clearly negative news + technicals
   reality check.
"""
from __future__ import annotations

# Default weights used only if all quality scores are zero (degenerate case).
WEIGHTS = {
    "Forecast":   0.40,
    "Sentiment":  0.40,
    "Technicals": 0.20,
}

# No component drops below this floor in the dynamic mix — we still want
# a small voice from each signal even when its quality is 0.
WEIGHT_FLOOR = 0.10

# Forecast must clear this magnitude before damping is even considered.
DAMPING_TRIGGER_MAGNITUDE = 0.5
# Maximum proportional reduction applied to the forecast on full disagreement.
MAX_DAMPING = 0.40

LABEL_BUCKETS = [
    (-1.01, -0.6,  "VERY_BAD"),
    (-0.6,  -0.2,  "BAD"),
    (-0.2,   0.2,  "NEUTRAL"),
    ( 0.2,   0.6,  "GOOD"),
    ( 0.6,   1.01, "EXCELLENT"),
]


def label_for(score: float) -> str:
    for lo, hi, name in LABEL_BUCKETS:
        if lo <= score < hi:
            return name
    return "NEUTRAL"


# ----------------- Component score derivation -----------------------------

def technical_score_from(t: dict | None) -> float:
    """Map a technicals dict (output of key_ratios_scraper) to a score in
    [-1, 1]. Above MA50/MA200 → positive; RSI extremes adjust toward
    mean-reversion expectations."""
    if not t:
        return 0.0
    score = 0.0
    pct50 = t.get("PriceVsMA50Pct")
    pct200 = t.get("PriceVsMA200Pct")
    rsi = t.get("RSI14")

    if pct50 is not None:
        score += max(-0.4, min(0.4, pct50 / 25.0))
    if pct200 is not None:
        score += max(-0.4, min(0.4, pct200 / 50.0))
    if rsi is not None:
        if rsi < 30:
            score += 0.2
        elif rsi > 70:
            score -= 0.2
    return max(-1.0, min(1.0, score))


# ----------------- Per-component QUALITY (drives weights) -----------------

def forecast_quality_from(mape: float | None) -> float:
    """Lower MAPE = higher quality. MAPE 0% → 1.0, MAPE 20%+ → 0."""
    if mape is None:
        return 0.0
    return max(0.0, min(1.0, 1.0 - mape / 0.20))


def sentiment_quality_from(news: dict | None) -> float:
    """Quality reflects how trustworthy the news signal is *for this symbol*.

    Three drivers: coverage (article count), recency (recent-7d count),
    and decisiveness (magnitude of the avg sentiment score)."""
    if not news:
        return 0.0
    articles = news.get("Articles", 0) or 0
    recent = news.get("Recent7d", 0) or 0
    decisiveness = abs(news.get("AvgSentimentScore", 0.0) or 0.0)

    coverage = min(articles / 30.0, 1.0)   # 30 articles = full coverage
    recency = min(recent / 5.0, 1.0)       # 5 recent articles = full
    return min(1.0, 0.40 * coverage + 0.40 * recency + 0.20 * decisiveness)


def technical_quality_from(t: dict | None) -> float:
    """Quality scales with how complete the technical picture is and
    whether RSI is in decisive territory."""
    if not t:
        return 0.0
    quality = 0.30  # we have *some* technicals
    if t.get("MA50") is not None:
        quality += 0.30
    if t.get("MA200") is not None:
        quality += 0.30
    rsi = t.get("RSI14")
    if rsi is not None and (rsi < 30 or rsi > 70):
        quality += 0.10
    return min(1.0, quality)


# ----------------- Dynamic weighting + damping ----------------------------

def _normalize_weights(qf: float, qs: float, qt: float) -> dict:
    qf = max(qf, WEIGHT_FLOOR)
    qs = max(qs, WEIGHT_FLOOR)
    qt = max(qt, WEIGHT_FLOOR)
    total = qf + qs + qt
    return {
        "Forecast":   qf / total,
        "Sentiment":  qs / total,
        "Technicals": qt / total,
    }


def _maybe_dampen_forecast(forecast: float, sentiment: float, technical: float) -> tuple:
    """If forecast is extreme but the others contradict, return a dampened
    forecast and the damping factor applied. Otherwise return the original
    score and 1.0."""
    if abs(forecast) < DAMPING_TRIGGER_MAGNITUDE:
        return forecast, 1.0

    other_avg = (sentiment + technical) / 2.0
    if forecast * other_avg >= 0:
        return forecast, 1.0  # same direction, no damping

    disagreement = min(abs(forecast - other_avg), 2.0) / 2.0  # 0..1
    factor = 1.0 - MAX_DAMPING * disagreement                  # 1.0..0.6
    return forecast * factor, factor


def compute_fusion(
    forecast_score: float,
    sentiment_score: float,
    technical_score: float,
    *,
    forecast_quality: float = 1.0,
    sentiment_quality: float = 1.0,
    technical_quality: float = 1.0,
    damp_divergent_forecast: bool = True,
) -> dict:
    """Fuse three pre-normalized [-1, 1] component scores into a final
    health view. The two adaptive behaviors live in this function:
    quality-driven weight normalization and forecast divergence damping.
    """
    # 1. dynamic weights from quality
    weights = _normalize_weights(forecast_quality, sentiment_quality, technical_quality)

    # 2. optional damping on the forecast component
    if damp_divergent_forecast:
        forecast_used, damping_factor = _maybe_dampen_forecast(
            forecast_score, sentiment_score, technical_score
        )
    else:
        forecast_used, damping_factor = forecast_score, 1.0

    components_raw = {
        "Forecast":   float(forecast_score),
        "Sentiment":  float(sentiment_score),
        "Technicals": float(technical_score),
    }
    components_used = {
        "Forecast":   float(forecast_used),
        "Sentiment":  float(sentiment_score),
        "Technicals": float(technical_score),
    }

    weighted = {name: weights[name] * value for name, value in components_used.items()}
    overall = sum(weighted.values())

    abs_total = sum(abs(v) for v in weighted.values())
    if abs_total < 1e-9:
        contributions = {k: round(weights[k] * 100, 2) for k in weights}
    else:
        contributions = {
            name: round(abs(value) / abs_total * 100, 2)
            for name, value in weighted.items()
        }
    primary = max(contributions, key=contributions.get)

    return {
        "Score": round(overall, 4),
        "Label": label_for(overall),
        "Components": {k: round(v, 4) for k, v in components_used.items()},
        "ComponentsRaw": {k: round(v, 4) for k, v in components_raw.items()},
        "Quality": {
            "Forecast":   round(forecast_quality, 4),
            "Sentiment":  round(sentiment_quality, 4),
            "Technicals": round(technical_quality, 4),
        },
        "Weights": {k: round(v, 4) for k, v in weights.items()},
        "Contributions": contributions,
        "PrimaryDriver": primary,
        "ForecastDamping": round(damping_factor, 4),  # 1.0 = no damping
    }


# ----------------- Django shim -------------------------------------------

def get_fusion_signal(ticker: str) -> dict:
    """Read stocks.json (built by stock_health.py) and translate the
    per-symbol Health block into a buy/sell/hold signal."""
    import json
    from pathlib import Path
    stocks = Path(__file__).resolve().parent.parent / "integrations" / "data" / "stocks.json"
    if not stocks.exists():
        return {"signal": "HOLD", "confidence": 0.0, "reason": "stocks.json missing"}
    rows = json.loads(stocks.read_text())
    match = next((r for r in rows if r["Symbol"] == ticker), None)
    if not match:
        return {"signal": "HOLD", "confidence": 0.0, "reason": f"{ticker} not in stocks.json"}

    health = match.get("Health", {})
    label = health.get("Label", "NEUTRAL")
    signal_map = {
        "EXCELLENT": "STRONG_BUY", "GOOD": "BUY", "NEUTRAL": "HOLD",
        "BAD": "SELL", "VERY_BAD": "STRONG_SELL",
    }
    primary = health.get("PrimaryDriver", "?")
    contributions = health.get("Contributions", {})
    return {
        "signal": signal_map.get(label, "HOLD"),
        "confidence": abs(health.get("Score", 0.0)),
        "reason": f"{primary} dominated ({contributions.get(primary, 0)}%)",
    }
