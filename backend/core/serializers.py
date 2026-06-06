from rest_framework import serializers

from .models import ForecastTrend, LiveMarketData, StockSignal, StockSymbol, StockTechnicals


class StockSymbolSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockSymbol
        fields = ["id", "ticker", "company_name", "sector", "is_active"]


class StockTechnicalsSerializer(serializers.ModelSerializer):
    """Daily-refreshed technical indicators (MA/RSI/EPS/etc.)."""

    class Meta:
        model = StockTechnicals
        fields = [
            "id",
            "ticker",
            "rsi14",
            "ma20",
            "ma50",
            "ma200",
            "volatility20d",
            "volume_ratio",
            "eps",
            "computed_at",
        ]


class LiveMarketDataSerializer(serializers.ModelSerializer):
    """Snapshot row per ticker — current price, change_pct, and the
    daily-derived technicals (re-stamped each hourly run)."""

    class Meta:
        model = LiveMarketData
        fields = [
            "id",
            "ticker",
            "date",
            "open_price",
            "high",
            "low",
            "close",
            "volume",
            "change_pct",
            "rsi14",
            "ma20",
            "ma50",
            "ma200",
            "volatility20d",
            "volume_ratio",
            "eps",
        ]


class ForecastTrendSerializer(serializers.ModelSerializer):
    """Multi-step ARIMA forward curve — 30 business days of predicted closes."""

    class Meta:
        model = ForecastTrend
        fields = [
            "id",
            "ticker",
            "date",
            "days_ahead",
            "predicted_close",
            "direction",
            "model_used",
            "based_on_last_close",
            "change_pct_from_anchor",
        ]


class StockSignalSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockSignal
        fields = [
            "id",
            "ticker",
            "signal",
            "health_label",
            "horizon",
            "dominant_sentiment",
            "contributions",
            "confidence",
            "suggestion_confidence",
            "blended_score",
            "forecast_signed_score",
            "signal_strength",
            "reason",
            "forecast_score",
            "sentiment_score",
            "generated_at",
            "valid_until",
        ]


class StockSearchSerializer(serializers.Serializer):
    """Flat read-only shape used by GET /api/v1/core/stock-search/.

    Joins StockSymbol metadata with the latest LiveMarketData snapshot so
    the portfolio "Add Stock" screen gets everything it needs in a single
    request — symbol, name, industry, current price, today's change %, and
    last close (derived so the helper text can be rendered immediately).

    ``last_close`` is back-calculated from the live bar's close price and
    change_pct using:
        last_close = close / (1 + change_pct / 100)
    This avoids a second subquery and is accurate because LiveMarketData
    stores change_pct relative to the prior close.
    """

    symbol_id = serializers.UUIDField(source="id", read_only=True)
    symbol = serializers.CharField(source="ticker")
    name = serializers.CharField(source="company_name")
    industry = serializers.CharField(source="sector")
    current_price = serializers.DecimalField(
        max_digits=12, decimal_places=4, allow_null=True
    )
    change_percent = serializers.FloatField(source="live_change_pct", allow_null=True)
    last_close = serializers.SerializerMethodField()
    price_updated_at = serializers.SerializerMethodField()

    def get_price_updated_at(self, obj) -> str | None:
        from core.market_utils import live_snapshot_updated_iso

        raw = getattr(obj, "live_price_updated_at", None)
        return live_snapshot_updated_iso(raw)

    def get_last_close(self, obj) -> float | None:
        price = obj.current_price
        pct = obj.live_change_pct
        if price is None or pct is None:
            return None
        try:
            return round(float(price) / (1 + float(pct) / 100), 4)
        except ZeroDivisionError:
            return float(price)
