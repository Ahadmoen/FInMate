"""
Insights list/detail query helpers.

Joins StockSymbol with latest LiveMarketData and StockSignal rows via
correlated subqueries (same pattern as core.services.search_stocks).
"""

from __future__ import annotations

from django.db.models import DateTimeField, Exists, FloatField, OuterRef, Q, QuerySet, Subquery
from django.utils import timezone

from core.models import LiveMarketData, NewsSentiment, StockForecast, StockSignal, StockSymbol


# ── Display maps (match frontend mock) ────────────────────────────────────────

HEALTH_DISPLAY = {
    "EXCELLENT": "EXCELLENT",
    "GOOD": "GOOD",
    "NEUTRAL": "STABLE",
    "BAD": "WEAK",
    "VERY_BAD": "POOR",
}

BUY_SIGNALS = frozenset({"BUY", "STRONG_BUY"})
SELL_SIGNALS = frozenset({"SELL", "STRONG_SELL"})

TREND_FILTERS = [
    {"id": "all", "label": "All Signals"},
    {"id": "buy", "label": "Buy Signals"},
    {"id": "hold", "label": "Hold Signals"},
    {"id": "sell", "label": "Sell Signals"},
    {"id": "gainers", "label": "Top Gainers"},
    {"id": "losers", "label": "Top Losers"},
]

SORT_OPTIONS = [
    {"id": "name", "label": "Sort by Name"},
    {"id": "change_desc", "label": "Change % High → Low"},
    {"id": "change_asc", "label": "Change % Low → High"},
    {"id": "price_desc", "label": "Price High → Low"},
    {"id": "signal", "label": "Signal Strength"},
]


def list_sector_filters() -> list[dict]:
    """Sectors for symbols that are active and have a live price row."""
    sectors = (
        _active_symbols_with_live()
        .exclude(sector="")
        .values_list("sector", flat=True)
        .distinct()
        .order_by("sector")
    )
    return [{"id": "all", "label": "All Sectors"}, *[{"id": s, "label": s} for s in sectors]]


def _active_symbols_with_live() -> QuerySet:
    """Active StockSymbol rows that have at least one LiveMarketData snapshot."""
    has_live = LiveMarketData.objects.filter(ticker=OuterRef("ticker"))
    return StockSymbol.objects.filter(is_active=True).filter(Exists(has_live))


def _latest_live_subquery():
    return LiveMarketData.objects.filter(ticker=OuterRef("ticker")).order_by("-date")


def _latest_signal_subquery():
    return StockSignal.objects.filter(ticker=OuterRef("ticker")).order_by("-generated_at")


def insights_symbols_queryset() -> QuerySet:
    """Active symbols with live price + latest signal (473 pipeline tickers).

    Only includes rows present in ``stock_symbol`` (``is_active=True``) that
    also have a ``live_market_data`` row — excludes ~265 registry symbols with
    no scraped price/signal data.
    """
    latest_bar = _latest_live_subquery()
    latest_signal = _latest_signal_subquery()

    return (
        _active_symbols_with_live()
        .annotate(
            close=Subquery(latest_bar.values("close")[:1]),
            open_price=Subquery(latest_bar.values("open_price")[:1]),
            change_pct=Subquery(
                latest_bar.values("change_pct")[:1],
                output_field=FloatField(),
            ),
            rsi14=Subquery(
                latest_bar.values("rsi14")[:1],
                output_field=FloatField(),
            ),
            price_updated_at=Subquery(
                latest_bar.values("updated_at")[:1],
                output_field=DateTimeField(),
            ),
            signal=Subquery(latest_signal.values("signal")[:1]),
            health_label=Subquery(latest_signal.values("health_label")[:1]),
            suggestion_confidence=Subquery(
                latest_signal.values("suggestion_confidence")[:1],
            ),
            blended_score=Subquery(
                latest_signal.values("blended_score")[:1],
                output_field=FloatField(),
            ),
        )
        .filter(close__isnull=False)
    )


def apply_insights_filters(
    qs: QuerySet,
    *,
    q: str = "",
    sector: str = "all",
    trend: str = "all",
    sort: str = "name",
) -> QuerySet:
    query = (q or "").strip()
    if query:
        qs = qs.filter(
            Q(ticker__icontains=query)
            | Q(company_name__icontains=query)
            | Q(sector__icontains=query)
        )

    if sector and sector.lower() != "all":
        qs = qs.filter(sector__iexact=sector)

    trend_key = (trend or "all").lower()
    if trend_key == "buy":
        qs = qs.filter(signal__in=BUY_SIGNALS)
    elif trend_key == "hold":
        qs = qs.filter(signal="HOLD")
    elif trend_key == "sell":
        qs = qs.filter(signal__in=SELL_SIGNALS)
    elif trend_key == "gainers":
        qs = qs.filter(change_pct__gt=0)
    elif trend_key == "losers":
        qs = qs.filter(change_pct__lt=0)

    if sort == "change_desc":
        return qs.order_by("-change_pct", "ticker")
    if sort == "change_asc":
        return qs.order_by("change_pct", "ticker")
    if sort == "price_desc":
        return qs.order_by("-close", "ticker")
    if sort == "signal":
        return qs.order_by("-blended_score", "ticker")
    return qs.order_by("company_name", "ticker")


def signal_label(signal: str | None) -> str | None:
    if not signal:
        return None
    return f"{signal.replace('_', ' ')} SIGNAL"


def confidence_display(confidence: str | None) -> str | None:
    if not confidence:
        return None
    mapping = {"HIGH": "HIGH CONFIDENCE", "MEDIUM": "MED CONFIDENCE", "LOW": "LOW CONFIDENCE"}
    return mapping.get(confidence.upper(), confidence)


def health_display(health: str | None) -> str | None:
    if not health:
        return None
    return HEALTH_DISPLAY.get(health.upper(), health)


def signal_strength_dots(confidence: str | None) -> int:
    if not confidence:
        return 1
    return {"HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(confidence.upper(), 1)


def latest_forecast_for(ticker: str) -> StockForecast | None:
    return (
        StockForecast.objects.filter(ticker=ticker.upper())
        .order_by("-forecast_date")
        .first()
    )


def latest_live_for(ticker: str) -> LiveMarketData | None:
    return (
        LiveMarketData.objects.filter(ticker=ticker.upper())
        .order_by("-date")
        .first()
    )


def latest_signal_for(ticker: str) -> StockSignal | None:
    return (
        StockSignal.objects.filter(ticker=ticker.upper())
        .order_by("-generated_at")
        .first()
    )


def get_symbol(ticker: str) -> StockSymbol | None:
    return _active_symbols_with_live().filter(ticker=ticker.upper()).first()


def news_for_ticker(ticker: str, offset: int = 0, limit: int = 5) -> tuple[list[NewsSentiment], int]:
    base = NewsSentiment.objects.filter(ticker=ticker.upper()).order_by("-published_at")
    total = base.count()
    items = list(base[offset : offset + limit])
    return items, total


def format_time_ago(dt) -> str:
    if dt is None:
        return ""
    now = timezone.now()
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.get_current_timezone())
    delta = now - dt
    seconds = int(delta.total_seconds())
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m ago"
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h ago"
    days = hours // 24
    if days < 7:
        return f"{days}d ago"
    weeks = days // 7
    if weeks < 5:
        return f"{weeks}w ago"
    return dt.strftime("%b %d, %Y")
