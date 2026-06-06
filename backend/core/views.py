from rest_framework import generics
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated

from .models import ForecastTrend, LiveMarketData, StockSignal, StockSymbol, StockTechnicals
from .serializers import (
    ForecastTrendSerializer,
    LiveMarketDataSerializer,
    StockSearchSerializer,
    StockSignalSerializer,
    StockSymbolSerializer,
    StockTechnicalsSerializer,
)
from .services import (
    latest_live_bar_for,
    latest_signal_for,
    latest_signals_per_ticker,
    latest_technicals_all,
    latest_technicals_for,
    list_active_symbols,
    search_stocks,
)


class StockSymbolListView(generics.ListAPIView):
    """GET /api/core/symbols/ — all active stock symbols."""

    serializer_class = StockSymbolSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return list_active_symbols()


class StockSignalListView(generics.ListAPIView):
    """GET /api/core/signals/ — latest StockSignal per ticker."""

    serializer_class = StockSignalSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return latest_signals_per_ticker()


class StockSignalDetailView(generics.RetrieveAPIView):
    """GET /api/core/signals/<ticker>/ — latest StockSignal for a single ticker."""

    serializer_class = StockSignalSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        ticker = self.kwargs["ticker"].upper()
        signal = latest_signal_for(ticker)
        if signal is None:
            raise NotFound(f"No signal found for ticker '{ticker}'.")
        return signal


class StockTechnicalsListView(generics.ListAPIView):
    """GET /api/core/technicals/ — daily technical indicators per ticker."""

    serializer_class = StockTechnicalsSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return latest_technicals_all()


class StockTechnicalsDetailView(generics.RetrieveAPIView):
    """GET /api/core/technicals/<ticker>/ — daily technicals for one ticker."""

    serializer_class = StockTechnicalsSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        ticker = self.kwargs["ticker"].upper()
        row = latest_technicals_for(ticker)
        if row is None:
            raise NotFound(f"No technicals found for ticker '{ticker}'.")
        return row


class ForecastTrendListView(generics.ListAPIView):
    """GET /api/core/forecast-trend/<ticker>/ — full ~30-day forward curve for one ticker.

    Returns one row per day_ahead (1..30), ordered by days_ahead.
    Frontend uses this to draw the long-term prediction overlay on
    the price chart.
    """

    serializer_class = ForecastTrendSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        ticker = self.kwargs["ticker"].upper()
        return ForecastTrend.objects.filter(ticker=ticker).order_by("days_ahead")


class LiveMarketDataDetailView(generics.RetrieveAPIView):
    """GET /api/core/live/<ticker>/ — most recent intraday bar for one ticker."""

    serializer_class = LiveMarketDataSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        ticker = self.kwargs["ticker"].upper()
        bar = latest_live_bar_for(ticker)
        if bar is None:
            raise NotFound(f"No live data found for ticker '{ticker}'.")
        return bar


class StockSearchView(generics.ListAPIView):
    """GET /api/v1/core/stock-search/

    Returns all active PSX stocks enriched with live price data.
    Filtering and search are handled entirely on the client.

    Each item contains:
      symbol          — PSX ticker (e.g. "HBL")
      name            — full company name
      industry        — sector / industry label
      current_price   — latest close from LiveMarketData (null if no live data yet)
      change_percent  — today's % change vs prior close (null if not available)
      last_close      — prior-day close derived from current_price and change_percent

    Pagination is intentionally disabled: the client receives the full
    universe in one response and filters locally.
    """

    serializer_class = StockSearchSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        return search_stocks()
