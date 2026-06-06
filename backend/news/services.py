"""
Market News feed — aggregates ``news_sentiment`` rows for the News tab.

Market Sentiment Index maps the 7-day average FinBERT/VADER score (-1…1) onto
0–100 (Fear & Greed style). Article cards reuse the same sentiment labels as
insights detail news.
"""

from __future__ import annotations

from datetime import timedelta

from django.db.models import Avg, QuerySet
from django.utils import timezone

from core.models import NewsSentiment, StockSymbol
from insights import services as insight_services


SENTIMENT_FILTERS = [
    {"id": "all", "label": "All Sentiment"},
    {"id": "positive", "label": "Positive"},
    {"id": "stable", "label": "Stable"},
    {"id": "negative", "label": "Negative"},
    {"id": "excellent", "label": "Excellent"},
    {"id": "good", "label": "Good"},
    {"id": "neutral", "label": "Neutral"},
    {"id": "bad", "label": "Bad"},
    {"id": "very_bad", "label": "Very Bad"},
]

TONE_LABEL = {
    "EXCELLENT": "POSITIVE",
    "GOOD": "POSITIVE",
    "NEUTRAL": "STABLE",
    "BAD": "NEGATIVE",
    "VERY_BAD": "NEGATIVE",
}

TONE_KIND = {
    "EXCELLENT": "positive",
    "GOOD": "positive",
    "NEUTRAL": "neutral",
    "BAD": "negative",
    "VERY_BAD": "negative",
}

INDEX_PHASES = [
    (80, "Extreme Greed", "Market is in an 'Extreme Greed' phase. Caution advised for new entries."),
    (60, "Greed", "Market is in a 'Greed' phase. Momentum may be stretched — watch for reversals."),
    (40, "Neutral", "Market sentiment is balanced. No strong fear or greed signal."),
    (20, "Fear", "Market is in a 'Fear' phase. Volatility may offer selective opportunities."),
    (0, "Extreme Fear", "Market is in an 'Extreme Fear' phase. Risk-off sentiment dominates headlines."),
]


def _score_to_index(avg_score: float) -> float:
    """Map compound sentiment [-1, 1] → index [0, 100]."""
    clamped = max(-1.0, min(1.0, avg_score))
    return round((clamped + 1.0) / 2.0 * 100.0, 1)


def _phase_for_index(index: float) -> tuple[str, str]:
    for threshold, phase, message in INDEX_PHASES:
        if index >= threshold:
            return phase, message
    return INDEX_PHASES[-1][1], INDEX_PHASES[-1][2]


def compute_market_sentiment_index(window_days: int = 7) -> dict:
    """Fear & Greed-style index from recent headline sentiment scores."""
    now = timezone.now()
    current_start = now - timedelta(days=window_days)
    prev_start = now - timedelta(days=window_days * 2)
    prev_end = current_start

    current_avg = float(
        NewsSentiment.objects.filter(published_at__gte=current_start).aggregate(
            a=Avg("score"),
        )["a"]
        or 0.0
    )
    prev_avg = float(
        NewsSentiment.objects.filter(
            published_at__gte=prev_start,
            published_at__lt=prev_end,
        ).aggregate(a=Avg("score"))["a"]
        or 0.0
    )

    value = _score_to_index(current_avg)
    prev_value = _score_to_index(prev_avg)
    if prev_value > 0:
        change_pct = round((value - prev_value) / prev_value * 100.0, 1)
    else:
        change_pct = 0.0

    phase, message = _phase_for_index(value)

    return {
        "value": value,
        "change_pct": change_pct,
        "progress": value,
        "phase": phase,
        "message": message,
        "window_days": window_days,
    }


def list_industry_filters() -> list[dict]:
    """Sectors for tickers that have at least one news article."""
    tickers_with_news = (
        NewsSentiment.objects.values_list("ticker", flat=True).distinct()
    )
    sectors = (
        StockSymbol.objects.filter(
            is_active=True,
            ticker__in=tickers_with_news,
        )
        .exclude(sector="")
        .values_list("sector", flat=True)
        .distinct()
        .order_by("sector")
    )
    return [
        {"id": "all", "label": "All Industries"},
        *[{"id": s, "label": s} for s in sectors],
    ]


def list_stock_filters(limit: int = 200) -> list[dict]:
    """Tickers present in the news feed (recent first by latest article)."""
    tickers = (
        NewsSentiment.objects.values("ticker")
        .distinct()
        .order_by("ticker")[:limit]
    )
    ticker_list = [row["ticker"] for row in tickers if row["ticker"]]
    names = {
        sym.ticker: sym.company_name
        for sym in StockSymbol.objects.filter(ticker__in=ticker_list).only(
            "ticker", "company_name",
        )
    }
    return [
        {"id": "all", "label": "All Stocks"},
        *[
            {
                "id": t,
                "label": f"{t} — {names[t]}" if names.get(t) else t,
            }
            for t in sorted(ticker_list)
        ],
    ]


def apply_news_filters(
    qs: QuerySet,
    *,
    sentiment: str = "all",
    industry: str = "all",
    stock: str = "all",
) -> QuerySet:
    stock_key = (stock or "all").lower()
    if stock_key != "all":
        qs = qs.filter(ticker__iexact=stock.upper())

    industry_key = industry or "all"
    if industry_key.lower() != "all":
        tickers = StockSymbol.objects.filter(
            is_active=True,
            sector__iexact=industry_key,
        ).values_list("ticker", flat=True)
        qs = qs.filter(ticker__in=list(tickers))

    sentiment_key = (sentiment or "all").lower()
    if sentiment_key == "positive":
        qs = qs.filter(sentiment__in=["EXCELLENT", "GOOD"])
    elif sentiment_key == "stable":
        qs = qs.filter(sentiment="NEUTRAL")
    elif sentiment_key == "negative":
        qs = qs.filter(sentiment__in=["BAD", "VERY_BAD"])
    elif sentiment_key not in ("", "all"):
        qs = qs.filter(sentiment__iexact=sentiment_key.upper())

    return qs


def news_feed_queryset() -> QuerySet:
    return NewsSentiment.objects.all().order_by("-published_at")


def apply_headline_search(qs: QuerySet, q: str) -> QuerySet:
    """Case-insensitive substring match on article headline."""
    query = (q or "").strip()
    if not query:
        return qs
    return qs.filter(headline__icontains=query)


def format_time_ago(dt) -> str:
    return insight_services.format_time_ago(dt)
