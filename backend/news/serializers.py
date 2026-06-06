"""Serialization for Market News API responses."""

from __future__ import annotations

from news import services


def serialize_article(article) -> dict:
    sentiment = (article.sentiment or "NEUTRAL").upper()
    tone = services.TONE_KIND.get(sentiment, "neutral")

    return {
        "id": str(article.id),
        "ticker": article.ticker,
        "headline": article.headline,
        "source": article.source,
        "link": article.link or "",
        "status_badge": sentiment,
        "sentiment_label": services.TONE_LABEL.get(sentiment, "STABLE"),
        "sentiment_tone": tone,
        "score": round(article.score or 0.0, 4),
        "published_at": article.published_at.isoformat() if article.published_at else None,
        "time_ago": services.format_time_ago(article.published_at),
    }
