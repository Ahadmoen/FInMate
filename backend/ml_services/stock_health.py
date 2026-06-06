"""Merge forecasting + news sentiment + technical ratios per symbol into a
single stocks.json with a fused health score.

Reads:
  integrations/data/historical_data.json   (last close)
  integrations/data/stock_forecasts.json   (last backtest row per symbol)
  integrations/data/best_models.json       (winning model + MAPE per symbol)
  integrations/data/news_sentiment.json    (per-article sentiment)
  integrations/data/daily_ratios.json      (technical indicators per symbol)
  integrations/data/fundamental_ratios.json (best-effort PSX fundamentals)
  integrations/scrapers/symbols.py         (name + industry per symbol)

Writes:
  integrations/data/stocks.json   (one row per symbol — merged health view)
"""
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ml_services.fusion import (
    compute_fusion,
    forecast_quality_from,
    sentiment_quality_from,
    technical_quality_from,
    technical_score_from,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "integrations" / "data"
HISTORICAL = DATA_DIR / "historical_data.json"
FORECASTS = DATA_DIR / "stock_forecasts.json"
BEST_MODELS = DATA_DIR / "best_models.json"
SENTIMENT = DATA_DIR / "news_sentiment.json"
DAILY_RATIOS = DATA_DIR / "daily_ratios.json"
FUNDAMENTALS = DATA_DIR / "fundamental_ratios.json"
DIRECTIONAL = DATA_DIR / "directional_signals.json"
OUTPUT = DATA_DIR / "stocks.json"


def _pick_primary_horizon(horizons: dict) -> dict | None:
    """For each symbol the classifier reports 1d / 5d / 20d. Pick the
    horizon with the highest backtest accuracy where coverage >= 20%
    (so we don't celebrate a 100% hit rate on 1 sample). Falls back to
    overall hit rate if no horizon clears the coverage bar."""
    if not horizons:
        return None
    candidates = [
        (k, h) for k, h in horizons.items()
        if h.get("HighConfHitRate") is not None and h.get("HighConfCoverage", 0) >= 0.20
    ]
    if candidates:
        k, h = max(candidates, key=lambda kh: kh[1]["HighConfHitRate"])
    else:
        k, h = max(horizons.items(), key=lambda kh: kh[1].get("OverallHitRate", 0))
    return {"Horizon": k, **h}


def _last_close(rows: list, symbol: str) -> float | None:
    """Find latest Close across either historical_data or live_data shape."""
    sym_rows = [r for r in rows if r.get("Symbol") == symbol and r.get("Close") is not None]
    if not sym_rows:
        return None
    sym_rows.sort(key=lambda r: r["Date"])
    return float(sym_rows[-1]["Close"])


def _last_trade_age_days(rows: list, symbol: str) -> int | None:
    """How many days since the symbol's most recent close. Returns None if
    no history exists. Used to suppress signals on delisted / halted /
    suspended tickers — MODAM and similar PSX strays still sit in
    historical_data.json with prices from 2024 but haven't actually
    traded since, so the forecaster happily extrapolates and the n8n
    workflow then recommends 'STRONG BUY' on a dead stock."""
    from datetime import datetime, timezone
    sym_rows = [r for r in rows if r.get("Symbol") == symbol and r.get("Date")]
    if not sym_rows:
        return None
    try:
        latest_str = max(r["Date"] for r in sym_rows)
        latest = datetime.fromisoformat(latest_str.replace("Z", "+00:00"))
        if latest.tzinfo is None:
            latest = latest.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - latest).days
    except Exception:
        return None


# Skip symbols whose last close is older than this many calendar days.
# 30 matches historical_scraper's MAX_LOOKBACK_DAYS so the rules are
# consistent end-to-end. Tunable via env for one-off backfills.
STALE_SUGGESTION_DAYS = int(os.environ.get("STALE_SUGGESTION_DAYS", "30"))


def _company_meta() -> dict:
    """Pull name/industry without importing Django (symbols.py is plain Python)."""
    import importlib.util
    sym_path = Path(__file__).resolve().parent.parent / "integrations" / "scrapers" / "symbols.py"
    spec = importlib.util.spec_from_file_location("symbols_module", sym_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.COMPANIES


# Last-7-days filter for prediction sentiment. Older articles still
# live in news_sentiment.json (UI history) but don't drag the average
# the prediction reacts to. Day-0 was unbounded "all articles", which
# meant bad news from 3 weeks ago kept vetoing fresh BUY signals.
PREDICTION_WINDOW_DAYS = int(os.environ.get("PREDICTION_WINDOW_DAYS", "7"))

# Industry + macro blending weights. A cement-industry article
# affects every cement ticker's sentiment with 0.4× the weight of a
# direct ticker mention. A petrol/dollar/IMF article affects every
# ticker with 0.2× weight (more diffuse, less specific). Weights are
# bucket-level: bucket-mean is multiplied by weight, sum of weights
# normalises so a single direct article isn't drowned by N industry
# articles. Tunable via env for ablation experiments.
DIRECT_WEIGHT   = float(os.environ.get("SENTIMENT_DIRECT_WEIGHT", "1.0"))
INDUSTRY_WEIGHT = float(os.environ.get("SENTIMENT_INDUSTRY_WEIGHT", "0.4"))
MACRO_WEIGHT    = float(os.environ.get("SENTIMENT_MACRO_WEIGHT", "0.2"))


def _is_recent_article(a: dict, cutoff: datetime) -> bool:
    """True iff article's Date is >= cutoff. Falls back to True if the
    date can't be parsed (better to include than silently drop)."""
    try:
        d = datetime.fromisoformat(a["Date"].replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d >= cutoff
    except Exception:
        return True


def _aggregate_news(articles: list, companies: dict | None = None) -> dict:
    """Aggregate sentiment per ticker, blending three buckets:

      1. Direct ticker hits           (Symbol == ticker)            weight DIRECT
      2. Industry hits for the sector (Symbol=GENERAL, Market=<ind>) weight INDUSTRY
      3. Macro hits                   (Symbol=GENERAL, Market=Macro) weight MACRO

    Bucket-mean blending: each bucket's mean sentiment is multiplied
    by its weight; empty buckets are excluded from the denominator so
    a ticker with no direct articles still gets a sentiment signal
    from industry + macro. All buckets are filtered to the last
    PREDICTION_WINDOW_DAYS (7 by default) — older articles are kept
    in the DB for UI history but excluded from prediction.

    `companies` maps ticker → {industry, name, ...}. If None, only
    direct + macro blending happens (industry mapping unavailable).
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=PREDICTION_WINDOW_DAYS)
    companies = companies or {}

    # Bucket articles into direct / industry / macro pools.
    direct_by_sym: dict[str, list] = defaultdict(list)
    industry_by_market: dict[str, list] = defaultdict(list)
    macro_articles: list = []
    for a in articles:
        if not _is_recent_article(a, cutoff):
            continue
        sym = a.get("Symbol") or "GENERAL"
        market = a.get("Market") or ""
        if sym == "GENERAL":
            if market == "Macro":
                macro_articles.append(a)
            elif market:
                industry_by_market[market].append(a)
        else:
            direct_by_sym[sym].append(a)

    macro_score = (sum(float(a.get("SentimentScore", 0.0)) for a in macro_articles)
                   / len(macro_articles)) if macro_articles else None
    industry_score_by_market = {
        m: (sum(float(a.get("SentimentScore", 0.0)) for a in items) / len(items))
        for m, items in industry_by_market.items()
    }

    # Determine the set of tickers we need an entry for: every symbol
    # with direct articles, plus every symbol that has a known industry
    # in `companies` (so a ticker with NO direct news still gets a
    # signal from industry + macro). 'GENERAL' itself also gets a row
    # so the UI can show the aggregated GENERAL feed.
    all_syms = set(direct_by_sym) | set(companies)
    all_syms.add("GENERAL")

    out = {}
    for sym in all_syms:
        direct_items = direct_by_sym.get(sym, [])
        # Industry articles that should bleed into this ticker.
        if sym == "GENERAL":
            ind_items: list = []
        else:
            ind_market = (companies.get(sym) or {}).get("industry") or ""
            ind_items = industry_by_market.get(ind_market, [])

        direct_score = (sum(float(a.get("SentimentScore", 0.0)) for a in direct_items)
                        / len(direct_items)) if direct_items else None
        industry_score = (sum(float(a.get("SentimentScore", 0.0)) for a in ind_items)
                          / len(ind_items)) if ind_items else None

        # Blend the buckets that actually have articles. Empty buckets
        # contribute nothing (not zero) so a ticker with only direct
        # news isn't pulled toward neutral.
        wt_sum, scr_sum = 0.0, 0.0
        if direct_score is not None:
            wt_sum += DIRECT_WEIGHT;   scr_sum += DIRECT_WEIGHT * direct_score
        if industry_score is not None:
            wt_sum += INDUSTRY_WEIGHT; scr_sum += INDUSTRY_WEIGHT * industry_score
        if macro_score is not None:
            wt_sum += MACRO_WEIGHT;    scr_sum += MACRO_WEIGHT * macro_score
        blended = (scr_sum / wt_sum) if wt_sum > 0 else 0.0

        # Distribution + dominant label use direct articles only — the
        # UI label ('GOOD/BAD/...') for the ticker should reflect what
        # was said about THIS ticker, not its sector mean.
        labels = [a.get("Sentiment", "NEUTRAL") for a in direct_items]
        dist = dict(Counter(labels))
        dominant = max(dist.items(), key=lambda kv: kv[1])[0] if dist else "NEUTRAL"

        out[sym] = {
            "Articles": len(direct_items),
            "Recent7d": len(direct_items),  # already filtered to 7d
            "IndustryArticles": len(ind_items),
            "MacroArticles": len(macro_articles) if sym != "GENERAL" else 0,
            "AvgSentimentScore": round(blended, 4),
            "DirectScore": round(direct_score, 4) if direct_score is not None else None,
            "IndustryScore": round(industry_score, 4) if industry_score is not None else None,
            "MacroScore": round(macro_score, 4) if macro_score is not None else None,
            "Distribution": dist,
            "DominantSentiment": dominant,
        }
    return out


def _latest_forecast_per_symbol(forecasts: list) -> dict:
    """For each symbol, take the last backtest row (most recent date)."""
    by_sym = defaultdict(list)
    for r in forecasts:
        by_sym[r["Symbol"]].append(r)
    out = {}
    for sym, rows in by_sym.items():
        rows.sort(key=lambda r: r["Date"])
        out[sym] = rows[-1]
    return out


def main() -> None:
    if not FORECASTS.exists():
        print(f"missing {FORECASTS} — run forecasting first")
        return

    import time as _time
    from . import mlflow_utils
    _started = _time.time()
    _mlflow_ctx = mlflow_utils.run("stock_health_v2", run_name=f"batch_{int(_started)}",
                                    tags={"kind": "inference_batch"})
    _mlflow_ctx.__enter__()
    try:
        _run_main(forecasts_path=FORECASTS, started=_started, mlflow_mod=mlflow_utils)
    finally:
        _mlflow_ctx.__exit__(None, None, None)


def _run_main(*, forecasts_path, started, mlflow_mod) -> None:
    forecasts = json.loads(forecasts_path.read_text())
    summaries = json.loads(BEST_MODELS.read_text()) if BEST_MODELS.exists() else []
    summary_by_sym = {s["Symbol"]: s for s in summaries}
    latest_fc = _latest_forecast_per_symbol(forecasts)

    historical = json.loads(HISTORICAL.read_text()) if HISTORICAL.exists() else []
    articles = json.loads(SENTIMENT.read_text()) if SENTIMENT.exists() else []
    companies = _company_meta()
    news_by_sym = _aggregate_news(articles, companies)

    daily_ratios = json.loads(DAILY_RATIOS.read_text()) if DAILY_RATIOS.exists() else []
    technicals_by_sym = {r["Symbol"]: r.get("Technicals", {}) for r in daily_ratios}
    fundamentals = json.loads(FUNDAMENTALS.read_text()) if FUNDAMENTALS.exists() else []
    fundamentals_by_sym = {r["Symbol"]: r for r in fundamentals}
    directional = json.loads(DIRECTIONAL.read_text()) if DIRECTIONAL.exists() else []
    directional_by_sym = {r["Symbol"]: r.get("Horizons", {}) for r in directional}

    rows = []
    stale_skipped: list[tuple[str, int]] = []
    for symbol, fc in latest_fc.items():
        # Stale-symbol gate: if historical data is older than
        # STALE_SUGGESTION_DAYS, don't generate a fresh signal.
        # Otherwise n8n alerts users to "STRONG BUY" on delisted /
        # suspended tickers (e.g., MODAM last traded April 2024).
        age = _last_trade_age_days(historical, symbol)
        if age is not None and age > STALE_SUGGESTION_DAYS:
            stale_skipped.append((symbol, age))
            continue
        meta = companies.get(symbol, {})
        last_close = _last_close(historical, symbol) or fc.get("Close")
        best_price = fc.get("Forecasting_Best")
        best_model = fc.get("Best_Model")
        summary = summary_by_sym.get(symbol, {})
        mape = summary.get("Best_MAPE")

        if best_price is None or last_close in (None, 0):
            forecast_block = {
                "Model": best_model,
                "PredictedPrice": best_price,
                "ExpectedChangePct": None,
                "Direction": fc.get("Direction_Best", "STABLE"),
                "MAPE": mape,
                "Confidence": None,
            }
            forecast_norm = 0.0
        else:
            change_pct = (best_price - last_close) / last_close * 100
            confidence = max(0.0, 1.0 - (mape if mape is not None else 0.5))
            forecast_block = {
                "Model": best_model,
                "PredictedPrice": round(best_price, 4),
                "ExpectedChangePct": round(change_pct, 4),
                "Direction": fc.get("Direction_Best", "STABLE"),
                "MAPE": mape,
                "Confidence": round(confidence, 4),
            }
            forecast_norm = max(-1.0, min(1.0, change_pct / 3.0))  # ±3% → ±1 (more sensitive)

        news_block = news_by_sym.get(symbol, {
            "Articles": 0, "Recent7d": 0, "AvgSentimentScore": 0.0,
            "Distribution": {}, "DominantSentiment": "NEUTRAL",
        })
        sentiment_norm = news_block["AvgSentimentScore"]

        technicals = technicals_by_sym.get(symbol, {})
        technical_norm = technical_score_from(technicals)

        # Per-stock quality scores drive dynamic weights inside compute_fusion.
        fc_quality = forecast_quality_from(mape)
        sn_quality = sentiment_quality_from(news_block)
        tc_quality = technical_quality_from(technicals)

        health = compute_fusion(
            forecast_norm,
            sentiment_norm,
            technical_norm,
            forecast_quality=fc_quality,
            sentiment_quality=sn_quality,
            technical_quality=tc_quality,
        )

        funds = fundamentals_by_sym.get(symbol, {})
        ratios_block = {
            "Technicals": technicals,
            "Fundamentals": funds.get("Snapshot", {}),
            "Reports": funds.get("Reports", []),
        }

        directional_horizons = directional_by_sym.get(symbol, {})
        primary = _pick_primary_horizon(directional_horizons)
        directional_block = {
            "Horizons": directional_horizons,
            "Primary": primary,
        }

        suggestion = _make_suggestion(health, forecast_block, news_block, primary)

        rows.append({
            "Symbol": symbol,
            "Name": meta.get("name", symbol),
            "Industry": meta.get("industry", ""),
            "LastClose": round(last_close, 4) if last_close is not None else None,
            "Forecast": forecast_block,
            "News": news_block,
            "Ratios": ratios_block,
            "Directional": directional_block,
            "Health": health,
            "Suggestion": suggestion,
        })

    rows.sort(key=lambda r: r["Health"]["Score"], reverse=True)
    OUTPUT.write_text(json.dumps(rows, indent=2, default=str))

    counts = Counter(r["Health"]["Label"] for r in rows)
    actions = Counter(r["Suggestion"]["Action"] for r in rows)
    print(f"wrote {len(rows)} symbols -> {OUTPUT}")
    for label in ["EXCELLENT", "GOOD", "NEUTRAL", "BAD", "VERY_BAD"]:
        print(f"  {label:10s} {counts.get(label, 0)}")
    print()
    print("Suggestion breakdown:")
    for action in ["STRONG_BUY", "BUY", "HOLD", "SELL", "STRONG_SELL"]:
        print(f"  {action:12s} {actions.get(action, 0)}")

    import time as _t
    mlflow_mod.log_metrics({
        "symbols_total": len(rows),
        "duration_sec": _t.time() - started,
        **{f"health_{k.lower()}_count": float(v) for k, v in counts.items()},
        **{f"action_{k.lower()}_count": float(v) for k, v in actions.items()},
    })


def _make_suggestion(health: dict, forecast: dict, news: dict, directional: dict | None = None) -> dict:
    """Translate the fused Health + Forecast + News blocks into a
    human-readable BUY / HOLD / SELL recommendation.

    The decision metric is a **blend of the fused Health score and a
    forecast-driven score that already weights forecast magnitude by
    model accuracy**. So a 3% predicted move with 95% confidence
    contributes more to the blend than a 5% move with 60% confidence —
    accurate forecasters get more voice. News acts as a *veto*: a
    strongly contradicting sentiment downgrades a BUY/SELL to HOLD even
    when the blended score otherwise warrants action.
    """
    score = float(health.get("Score", 0.0))
    label = health.get("Label", "NEUTRAL")
    direction = forecast.get("Direction", "STABLE")
    fc_confidence = float(forecast.get("Confidence", 0.0) or 0.0)
    fc_mape = float(forecast.get("MAPE", 0.5) or 0.5)
    expected_pct_raw = forecast.get("ExpectedChangePct")
    expected_pct = float(expected_pct_raw) if expected_pct_raw is not None else 0.0
    primary = health.get("PrimaryDriver", "?")
    contributions = health.get("Contributions", {})
    primary_share = float(contributions.get(primary, 0.0))
    sentiment_score = float(news.get("AvgSentimentScore", 0.0) or 0.0) if news else 0.0

    # Forecast-derived signed score in [-1, 1]:
    #   - magnitude scaled so ±3% predicted move maps to ±1.0
    #   - then attenuated by model confidence (1 - MAPE)
    # Accurate forecasts get more voice; noisy forecasts get less.
    fc_signed = max(-1.0, min(1.0, expected_pct / 3.0)) * fc_confidence

    # Blended decision score: 50% fused Health (forecast + news + technicals),
    # 50% forecast-signed (already accuracy-weighted). Two paths to the
    # same number — if either is strong AND aligned with direction, we act.
    blended = 0.5 * score + 0.5 * fc_signed
    strength = max(abs(score), abs(fc_signed))

    # Effective direction = sign of ExpectedChangePct (the raw forecast move),
    # not the categorical Direction label which goes STABLE for moves under
    # the dynamic threshold. A 1% predicted move with 95% accuracy is still
    # a real bull signal — we shouldn't lose it just because the categorical
    # label rounded to STABLE.
    if abs(expected_pct) < 0.30:
        effective_dir = "STABLE"
    elif expected_pct > 0:
        effective_dir = "UP"
    else:
        effective_dir = "DOWN"

    aligned_up = score > 0 and fc_signed > 0 and effective_dir == "UP"
    aligned_down = score < 0 and fc_signed < 0 and effective_dir == "DOWN"
    contradicts = score * fc_signed < -0.10

    if blended >= 0.40 and aligned_up and fc_confidence >= 0.90:
        action, conf = "STRONG_BUY", "HIGH"
    elif blended >= 0.15 and effective_dir == "UP" and not contradicts:
        action = "BUY"
        if fc_confidence >= 0.90 and aligned_up and abs(score) >= 0.20:
            conf = "HIGH"
        elif fc_confidence >= 0.82:
            conf = "MEDIUM"
        else:
            conf = "LOW"
    elif blended <= -0.40 and aligned_down and fc_confidence >= 0.90:
        action, conf = "STRONG_SELL", "HIGH"
    elif blended <= -0.15 and effective_dir == "DOWN" and not contradicts:
        action = "SELL"
        if fc_confidence >= 0.90 and aligned_down and abs(score) >= 0.20:
            conf = "HIGH"
        elif fc_confidence >= 0.82:
            conf = "MEDIUM"
        else:
            conf = "LOW"
    elif contradicts:
        action, conf = "HOLD", "LOW"
    else:
        action = "HOLD"
        conf = "MEDIUM" if strength >= 0.10 else "LOW"

    # NEWS VETO — strongly contradicting news downgrades to HOLD.
    veto_reason = ""
    if action in ("STRONG_BUY", "BUY") and sentiment_score <= -0.30:
        veto_reason = f" — held by bearish news (avg sentiment {sentiment_score:+.2f})"
        action, conf = "HOLD", "LOW"
    elif action in ("STRONG_SELL", "SELL") and sentiment_score >= 0.30:
        veto_reason = f" — held by bullish news (avg sentiment {sentiment_score:+.2f})"
        action, conf = "HOLD", "LOW"

    # DIRECTIONAL CLASSIFIER MODIFIER —
    # The classifier (separate from the regression-based forecast) gives
    # an independent UP/DOWN call with a historical hit-rate. When it
    # agrees with our action AND its hit-rate is meaningfully above 0.55,
    # we upgrade confidence. When it strongly disagrees AND has high
    # hit-rate, we downgrade BUY/SELL to HOLD.
    dir_used = None
    if directional is not None:
        d_dir = directional.get("LatestDirection")
        d_conf_label = directional.get("LatestConfidence")  # HIGH or LOW
        d_hit = directional.get("HighConfHitRate") or directional.get("OverallHitRate") or 0
        d_horizon = directional.get("Horizon", "?")
        dir_used = {
            "Direction": d_dir,
            "Confidence": d_conf_label,
            "HitRate": d_hit,
            "Horizon": d_horizon,
        }
        wants_up = action in ("STRONG_BUY", "BUY")
        wants_down = action in ("STRONG_SELL", "SELL")
        # Trust the classifier's signal if it's been right >55% historically
        if d_conf_label == "HIGH" and d_hit >= 0.55:
            if wants_up and d_dir == "DOWN":
                action, conf = "HOLD", "LOW"
                veto_reason = (
                    f" — directional classifier disagrees ({d_horizon} horizon, "
                    f"{d_hit*100:.0f}% historical accuracy says DOWN)"
                )
            elif wants_down and d_dir == "UP":
                action, conf = "HOLD", "LOW"
                veto_reason = (
                    f" — directional classifier disagrees ({d_horizon} horizon, "
                    f"{d_hit*100:.0f}% historical accuracy says UP)"
                )
            elif wants_up and d_dir == "UP":
                conf = "HIGH"  # both signals agree decisively
            elif wants_down and d_dir == "DOWN":
                conf = "HIGH"

    expected_str = f"{expected_pct:+.1f}%" if expected_pct_raw is not None else "n/a"

    if action in ("STRONG_BUY", "STRONG_SELL"):
        reason = (
            f"All three signals aligned: {label} consensus + forecast {direction} {expected_str} "
            f"({fc_confidence*100:.0f}% model confidence, MAPE {fc_mape*100:.1f}%). "
            f"{primary} drove {primary_share:.0f}% of the fused signal."
        )
    elif action == "BUY":
        reason = (
            f"Forecast UP {expected_str} ({fc_confidence*100:.0f}% confidence, "
            f"MAPE {fc_mape*100:.1f}%) + {label} consensus, blended score {blended:+.2f}."
        )
    elif action == "SELL":
        reason = (
            f"Forecast DOWN {expected_str} ({fc_confidence*100:.0f}% confidence, "
            f"MAPE {fc_mape*100:.1f}%) + {label} consensus, blended score {blended:+.2f}."
        )
    elif contradicts:
        reason = (
            f"Mixed signals: forecast {direction} {expected_str} but fused health is {label.lower()} "
            f"(score {score:+.2f}). Wait for confirmation.{veto_reason}"
        )
    elif veto_reason:
        reason = (
            f"Forecast {direction} {expected_str} would have triggered an action{veto_reason}."
        )
    else:
        reason = (
            f"No strong signal — health {label.lower()} (score {score:+.2f}), "
            f"forecast {direction.lower()} {expected_str} (MAPE {fc_mape*100:.1f}%)."
        )

    return {
        "Action": action,
        "Confidence": conf,
        "Reason": reason,
        "BlendedScore": round(blended, 4),
        "ForecastSignedScore": round(fc_signed, 4),
        "SignalStrength": round(strength, 4),
        "ForecastMAPE": round(fc_mape, 4),
        "ForecastConfidence": round(fc_confidence, 4),
        "AlignedSignals": aligned_up or aligned_down,
        "ContradictingSignals": contradicts,
        "DirectionalCheck": dir_used,
    }


if __name__ == "__main__":
    main()
