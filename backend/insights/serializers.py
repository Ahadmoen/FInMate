"""Serialization helpers for insights API responses."""

from __future__ import annotations

from core.market_utils import effective_change_pct, live_snapshot_updated_iso
from insights import services


def serialize_list_item(sym) -> dict:
    """Build one insights card payload from an annotated StockSymbol row."""
    signal = getattr(sym, "signal", None)
    health = getattr(sym, "health_label", None)
    confidence = getattr(sym, "suggestion_confidence", None)

    close = getattr(sym, "close", None)
    open_price = getattr(sym, "open_price", None)
    change_pct = getattr(sym, "change_pct", None)
    rsi = getattr(sym, "rsi14", None)
    price_updated_at = getattr(sym, "price_updated_at", None)

    return {
        "symbol_id": str(sym.id),
        "ticker": sym.ticker,
        "company_name": sym.company_name,
        "sector": sym.sector or "",
        "close": float(close) if close is not None else None,
        "change_pct": effective_change_pct(change_pct, open_price, close),
        "price_updated_at": live_snapshot_updated_iso(price_updated_at),
        "signal": signal,
        "signal_label": services.signal_label(signal),
        "health_label": health,
        "health_display": services.health_display(health),
        "suggestion_confidence": confidence,
        "confidence_display": services.confidence_display(confidence),
        "rsi14": round(rsi, 1) if rsi is not None else None,
        "signal_strength_dots": services.signal_strength_dots(confidence),
    }


def serialize_live(lmd) -> dict | None:
    if lmd is None:
        return None
    return {
        "close": float(lmd.close),
        "change_pct": effective_change_pct(lmd.change_pct, lmd.open_price, lmd.close),
        "open_price": float(lmd.open_price),
        "high": float(lmd.high),
        "low": float(lmd.low),
        "volume": lmd.volume,
        "rsi14": lmd.rsi14,
        "ma20": float(lmd.ma20) if lmd.ma20 is not None else None,
        "ma50": float(lmd.ma50) if lmd.ma50 is not None else None,
        "ma200": float(lmd.ma200) if lmd.ma200 is not None else None,
        "volatility20d": lmd.volatility20d,
        "volume_ratio": lmd.volume_ratio,
        "eps": float(lmd.eps) if lmd.eps is not None else None,
        "as_of": live_snapshot_updated_iso(lmd.updated_at),
    }


def serialize_signal(sig) -> dict | None:
    if sig is None:
        return None
    return {
        "action": sig.signal,
        "signal_label": services.signal_label(sig.signal),
        "health_label": sig.health_label,
        "health_display": services.health_display(sig.health_label),
        "suggestion_confidence": sig.suggestion_confidence,
        "confidence_display": services.confidence_display(sig.suggestion_confidence),
        "confidence": sig.confidence,
        "blended_score": sig.blended_score,
        "forecast_score": sig.forecast_score,
        "sentiment_score": sig.sentiment_score,
        "dominant_sentiment": sig.dominant_sentiment,
        "horizon": sig.horizon,
        "reason": sig.reason,
        "contributions": sig.contributions or {},
        "signal_strength_dots": services.signal_strength_dots(sig.suggestion_confidence),
        "valid_until": sig.valid_until.isoformat() if sig.valid_until else None,
        "generated_at": sig.generated_at.isoformat() if sig.generated_at else None,
    }


def serialize_forecast(fc) -> dict | None:
    if fc is None:
        return None
    return {
        "direction": fc.direction,
        "predicted_price": float(fc.predicted_price),
        "expected_change_pct": fc.expected_change_pct,
        "confidence": fc.confidence,
        "mape": fc.mape,
        "model_used": fc.model_used,
        "forecast_date": fc.forecast_date.isoformat() if fc.forecast_date else None,
    }


def serialize_news_item(article) -> dict:
    score = article.score or 0.0
    if score > 0.2:
        tone = "positive"
    elif score < -0.2:
        tone = "negative"
    else:
        tone = "neutral"

    return {
        "id": str(article.id),
        "headline": article.headline,
        "source": article.source,
        "link": article.link or "",
        "sentiment": article.sentiment,
        "score": round(score, 4),
        "tone": tone,
        "published_at": article.published_at.isoformat() if article.published_at else None,
        "time_ago": services.format_time_ago(article.published_at),
    }
