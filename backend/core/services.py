"""
Service helpers for the core app.

Views stay thin and call into these helpers so business logic lives in one
place. Most lookups return the latest snapshot per ticker.
"""

from typing import Iterable

from django.db.models import DateTimeField, FloatField, OuterRef, Subquery

from .models import LiveMarketData, StockSignal, StockSymbol, StockTechnicals


def list_active_symbols() -> Iterable[StockSymbol]:
    return StockSymbol.objects.filter(is_active=True).order_by("ticker")


def latest_signal_for(ticker: str) -> StockSignal | None:
    return (
        StockSignal.objects.filter(ticker=ticker)
        .order_by("-generated_at")
        .first()
    )


def latest_signals_per_ticker():
    """Return one row per ticker — the most recently generated StockSignal."""
    latest_per_ticker = (
        StockSignal.objects.filter(ticker=OuterRef("ticker"))
        .order_by("-generated_at")
        .values("pk")[:1]
    )
    return StockSignal.objects.filter(
        pk__in=Subquery(latest_per_ticker)
    ).order_by("ticker")


def latest_technicals_for(ticker: str) -> StockTechnicals | None:
    """Daily technical indicators (MA/RSI/EPS/etc.) — refreshed by warm-1."""
    return StockTechnicals.objects.filter(ticker=ticker).first()


def latest_technicals_all():
    return StockTechnicals.objects.all().order_by("ticker")


def latest_live_bar_for(ticker: str) -> LiveMarketData | None:
    """Live price snapshot — most recent intraday hourly bar.
    Replaces what `MarketDataCache` used to expose for current_price."""
    return (
        LiveMarketData.objects.filter(ticker=ticker)
        .order_by("-date")
        .first()
    )


def search_stocks():
    """Return all active StockSymbol rows annotated with live price data.

    Each row gains two extra attributes via subquery annotation:
      - ``current_price``   DecimalField  — latest LiveMarketData.close
      - ``live_change_pct`` FloatField    — latest LiveMarketData.change_pct

    ``last_close`` is derived in the serializer from these two values using:
        last_close = current_price / (1 + live_change_pct / 100)
    """
    latest_bar = (
        LiveMarketData.objects
        .filter(ticker=OuterRef("ticker"))
        .order_by("-date")
    )

    return StockSymbol.objects.filter(is_active=True).annotate(
        current_price=Subquery(latest_bar.values("close")[:1]),
        live_change_pct=Subquery(
            latest_bar.values("change_pct")[:1],
            output_field=FloatField(),
        ),
        live_price_updated_at=Subquery(
            latest_bar.values("updated_at")[:1],
            output_field=DateTimeField(),
        ),
    ).order_by("ticker")
