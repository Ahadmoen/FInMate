from django.urls import path

from .views import (
    ForecastTrendListView,
    LiveMarketDataDetailView,
    StockSearchView,
    StockSignalDetailView,
    StockSignalListView,
    StockSymbolListView,
    StockTechnicalsDetailView,
    StockTechnicalsListView,
)


urlpatterns = [
    path("symbols/", StockSymbolListView.as_view(), name="core-symbols"),

    path("signals/", StockSignalListView.as_view(), name="core-signals"),
    path("signals/<str:ticker>/", StockSignalDetailView.as_view(), name="core-signal-detail"),

    # Daily technical indicators (MA/RSI/EPS/etc.) — refreshed by warm-1.
    path("technicals/", StockTechnicalsListView.as_view(), name="core-technicals"),
    path("technicals/<str:ticker>/", StockTechnicalsDetailView.as_view(), name="core-technicals-detail"),

    # Live intraday price snapshot (single most recent hourly bar) — refreshed
    # by finmate-live every hour during market hours. Replaces the live-price
    # half of the deprecated /market-data/<ticker>/ route.
    path("live/<str:ticker>/", LiveMarketDataDetailView.as_view(), name="core-live-detail"),

    # Multi-step ARIMA forward curve — 30 business days of predicted closes
    # per ticker. Frontend uses this to draw the long-term prediction line.
    path("forecast-trend/<str:ticker>/", ForecastTrendListView.as_view(), name="core-forecast-trend"),

    # Portfolio "Add Stock" search — StockSymbol + LiveMarketData joined.
    # Supports ?q=<query> for ticker / name / industry filtering.
    path("stock-search/", StockSearchView.as_view(), name="core-stock-search"),
]
