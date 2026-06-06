from django.contrib import admin

from .models import (
    ForecastTrend,
    LiveMarketData,
    NewsSentiment,
    StockForecast,
    StockSignal,
    StockSymbol,
    StockTechnicals,
)


@admin.register(StockSymbol)
class StockSymbolAdmin(admin.ModelAdmin):
    list_display = ("ticker", "company_name", "sector", "is_active", "updated_at")
    list_filter = ("is_active", "sector")
    search_fields = ("ticker", "company_name", "sector")


@admin.register(StockTechnicals)
class StockTechnicalsAdmin(admin.ModelAdmin):
    list_display = ("ticker", "rsi14", "ma20", "ma50", "ma200", "eps", "computed_at")
    search_fields = ("ticker",)


@admin.register(LiveMarketData)
class LiveMarketDataAdmin(admin.ModelAdmin):
    list_display = ("ticker", "date", "open_price", "high", "low", "close", "volume")
    list_filter = ("date",)
    search_fields = ("ticker",)


@admin.register(StockForecast)
class StockForecastAdmin(admin.ModelAdmin):
    list_display = (
        "ticker",
        "forecast_date",
        "direction",
        "predicted_price",
        "confidence",
        "mape",
        "model_used",
    )
    list_filter = ("direction", "model_used")
    search_fields = ("ticker",)


@admin.register(ForecastTrend)
class ForecastTrendAdmin(admin.ModelAdmin):
    list_display = (
        "ticker",
        "days_ahead",
        "date",
        "predicted_close",
        "direction",
        "based_on_last_close",
        "change_pct_from_anchor",
        "model_used",
    )
    list_filter = ("direction", "model_used")
    search_fields = ("ticker",)


@admin.register(NewsSentiment)
class NewsSentimentAdmin(admin.ModelAdmin):
    list_display = ("ticker", "source", "sentiment", "score", "published_at")
    list_filter = ("sentiment", "source")
    search_fields = ("ticker", "headline", "source")


@admin.register(StockSignal)
class StockSignalAdmin(admin.ModelAdmin):
    list_display = (
        "ticker",
        "signal",
        "health_label",
        "horizon",
        "confidence",
        "forecast_score",
        "sentiment_score",
        "generated_at",
        "valid_until",
    )
    list_filter = ("signal", "health_label")
    search_fields = ("ticker", "reason")
