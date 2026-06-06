import uuid

from django.db import models


class TimestampMixin(models.Model):
    """Abstract base providing `created_at` and `updated_at` columns."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class StockSymbol(TimestampMixin):
    ticker = models.CharField(max_length=10, unique=True)
    company_name = models.CharField(max_length=200)
    sector = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "stock_symbol"
        ordering = ["ticker"]

    def __str__(self) -> str:
        return f"{self.ticker} — {self.company_name}"


class StockTechnicals(TimestampMixin):
    """Daily-refreshed technical indicators per ticker.

    Replaces the technicals half of the old `MarketDataCache` table —
    that one mixed daily technicals with hourly price data and led to
    duplication with `LiveMarketData`. Live price now lives only in
    `LiveMarketData`; this table is purely indicators.
    """

    ticker = models.CharField(max_length=10, unique=True)
    rsi14 = models.FloatField(null=True, blank=True)
    ma20 = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    ma50 = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    ma200 = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    volatility20d = models.FloatField(null=True, blank=True)
    volume_ratio = models.FloatField(null=True, blank=True)
    eps = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True,
        help_text=(
            "Earnings per share, sourced from stocks.json "
            "Ratios.Fundamentals.EPS. Refreshed quarterly by "
            "finmate-quarterly-fundamentals — typically only changes "
            "on quarterly company filings."
        ),
    )
    computed_at = models.DateTimeField(
        help_text="When stock_health.py wrote stocks.json that produced these values.",
    )

    class Meta:
        db_table = "stock_technicals"
        ordering = ["ticker"]

    def __str__(self) -> str:
        return f"{self.ticker} technicals @ {self.computed_at}"


class StockForecast(TimestampMixin):
    class Direction(models.TextChoices):
        UP = "UP", "Up"
        DOWN = "DOWN", "Down"
        STABLE = "STABLE", "Stable"

    class Model(models.TextChoices):
        LSTM = "LSTM", "LSTM"
        ARIMA = "ARIMA", "ARIMA"

    ticker = models.CharField(max_length=10)
    forecast_date = models.DateField()
    direction = models.CharField(max_length=10, choices=Direction.choices)
    confidence = models.FloatField(
        help_text="1 - MAPE, in [0, 1]. Higher = more accurate model.",
    )
    mape = models.FloatField(
        null=True, blank=True,
        help_text=(
            "Raw mean absolute percentage error of the winning model on "
            "the 60-day backtest. Sourced from stocks.json Forecast.MAPE. "
            "Frontend can use this to filter low-quality forecasts (e.g. "
            "ignore predictions where mape > 0.10)."
        ),
    )
    predicted_price = models.DecimalField(max_digits=12, decimal_places=4)
    model_used = models.CharField(max_length=10, choices=Model.choices)
    expected_change_pct = models.FloatField(null=True, blank=True)

    class Meta:
        db_table = "stock_forecast"
        unique_together = ("ticker", "forecast_date", "model_used")
        ordering = ["-forecast_date", "ticker"]
        indexes = [
            models.Index(fields=["ticker", "-forecast_date"], name="idx_forecast_ticker_date"),
        ]

    def __str__(self) -> str:
        return f"{self.ticker} {self.forecast_date} [{self.model_used}] {self.direction}"


class ForecastTrend(TimestampMixin):
    """Multi-step ARIMA trend forecast — 30 business days of forward
    predictions per ticker.

    Sourced from forecasting_trend.json (produced by warm-3 alongside
    stocks.json's single-day Forecast block). Whereas StockForecast
    stores one prediction per (ticker, date, model), this table stores
    the full forward curve so the frontend can draw a "long-term
    prediction line" overlay on the chart.

    SNAPSHOT mode: each warm-4 run wipes prior rows for the tickers
    in the batch and inserts the new curve. One curve per ticker; no
    history accumulation here (StockForecast is the historical table).
    """

    class Direction(models.TextChoices):
        UP = "UP", "Up"
        DOWN = "DOWN", "Down"
        STABLE = "STABLE", "Stable"

    class Model(models.TextChoices):
        LSTM = "LSTM", "LSTM"
        ARIMA = "ARIMA", "ARIMA"

    ticker = models.CharField(max_length=10)
    date = models.DateField(
        help_text="The date being predicted (anchor date + DaysAhead business days).",
    )
    days_ahead = models.IntegerField(
        help_text="Business-day offset from anchor (1..30). Sourced from forecasting_trend.json DaysAhead.",
    )
    predicted_close = models.DecimalField(max_digits=12, decimal_places=4)
    direction = models.CharField(max_length=10, choices=Direction.choices)
    model_used = models.CharField(max_length=10, choices=Model.choices)
    based_on_last_close = models.DecimalField(
        max_digits=12, decimal_places=4,
        help_text="The anchor close price the curve is built off of.",
    )
    change_pct_from_anchor = models.FloatField(
        help_text="(predicted_close - based_on_last_close) / based_on_last_close, in percent.",
    )

    class Meta:
        db_table = "forecast_trend"
        unique_together = ("ticker", "days_ahead")
        ordering = ["ticker", "days_ahead"]

    def __str__(self) -> str:
        return f"{self.ticker} +{self.days_ahead}d → {self.predicted_close}"


class NewsSentiment(TimestampMixin):
    class Sentiment(models.TextChoices):
        VERY_BAD = "VERY_BAD", "Very Bad"
        BAD = "BAD", "Bad"
        NEUTRAL = "NEUTRAL", "Neutral"
        GOOD = "GOOD", "Good"
        EXCELLENT = "EXCELLENT", "Excellent"

    ticker = models.CharField(max_length=10)
    industry = models.CharField(
        max_length=80,
        blank=True,
        default="",
        help_text=(
            "Raw industry/market label from the source. May contain noisy "
            "values like 'World / Markets', 'Sector / COMMERCIAL BANKS', "
            "'Macro / PK Policy'. Use industry_wise for clean values."
        ),
    )
    industry_wise = models.CharField(
        max_length=40,
        blank=True,
        default="",
        help_text=(
            "Normalized industry classifier — one of: Cement, Banking, "
            "Oil & Gas, Power, Pharmaceuticals, Fertilizer, Textile, "
            "Automobile, Chemicals, Food, Insurance, Steel, IT, "
            "Agriculture, Politics, Macro. Empty if no classification "
            "could be derived. Use this for filtering ('all Cement "
            "news') regardless of whether the row is per-ticker, GENERAL, "
            "or from a noisy world/sector raw label."
        ),
    )
    headline = models.TextField()
    link = models.TextField(blank=True)
    source = models.CharField(max_length=100)
    sentiment = models.CharField(max_length=10, choices=Sentiment.choices)
    score = models.FloatField(
        default=0.0,
        help_text=(
            "FinBERT/VADER compound score in [-1, 1]. "
            "Negative = bearish, positive = bullish."
        ),
    )
    published_at = models.DateTimeField()
    analyzed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "news_sentiment"
        ordering = ["-published_at"]
        indexes = [
            models.Index(fields=["ticker", "published_at"], name="idx_news_ticker_pub"),
            models.Index(fields=["industry", "published_at"], name="idx_news_industry_pub"),
            models.Index(fields=["industry_wise", "published_at"], name="idx_news_indwise_pub"),
        ]

    def __str__(self) -> str:
        return f"{self.ticker} [{self.sentiment}] {self.source}"


class StockSignal(TimestampMixin):
    class Signal(models.TextChoices):
        STRONG_BUY = "STRONG_BUY", "Strong Buy"
        BUY = "BUY", "Buy"
        HOLD = "HOLD", "Hold"
        SELL = "SELL", "Sell"
        STRONG_SELL = "STRONG_SELL", "Strong Sell"

    class HealthLabel(models.TextChoices):
        VERY_BAD = "VERY_BAD", "Very Bad"
        BAD = "BAD", "Bad"
        NEUTRAL = "NEUTRAL", "Neutral"
        GOOD = "GOOD", "Good"
        EXCELLENT = "EXCELLENT", "Excellent"

    ticker = models.CharField(max_length=10)
    signal = models.CharField(
        max_length=15, choices=Signal.choices,
        help_text=(
            "Final BUY/HOLD/SELL recommendation. Sourced from stocks.json "
            "Suggestion.Action — i.e. AFTER the directional classifier "
            "has had a chance to upgrade confidence to HIGH or veto a "
            "BUY/SELL down to HOLD. This is the value users see."
        ),
    )
    health_label = models.CharField(
        max_length=10, choices=HealthLabel.choices, null=True, blank=True,
        help_text=(
            "Intermediate fused-score label (5-class) BEFORE the "
            "directional classifier modifier. Sourced from stocks.json "
            "Health.Label. Kept alongside `signal` for diagnostics — "
            "lets you see when the directional classifier overrode the "
            "fusion's call."
        ),
    )
    confidence = models.FloatField(
        help_text=(
            "Magnitude of the fused Health score in [0, 1]. "
            "= abs(stocks.json Health.Score). NOT the same as "
            "`suggestion_confidence` — that's the categorical bucket."
        ),
    )
    suggestion_confidence = models.CharField(
        max_length=10, null=True, blank=True,
        choices=[("HIGH", "High"), ("MEDIUM", "Medium"), ("LOW", "Low")],
        help_text=(
            "Categorical confidence in the BUY/HOLD/SELL recommendation. "
            "Sourced from stocks.json Suggestion.Confidence."
        ),
    )
    blended_score = models.FloatField(
        null=True, blank=True,
        help_text=(
            "0.5·Health.Score + 0.5·forecast-signed score, in roughly "
            "[-1, 1]. Sourced from stocks.json Suggestion.BlendedScore. "
            "The decision metric the Suggestion logic uses to pick the action."
        ),
    )
    forecast_signed_score = models.FloatField(
        null=True, blank=True,
        help_text=(
            "Forecast component as a signed score in [-1, 1], scaled by "
            "model confidence. Sourced from stocks.json "
            "Suggestion.ForecastSignedScore."
        ),
    )
    signal_strength = models.FloatField(
        null=True, blank=True,
        help_text=(
            "max(|Health.Score|, |forecast_signed_score|). Sourced from "
            "stocks.json Suggestion.SignalStrength. Roughly: how confident "
            "is the strongest single component."
        ),
    )
    reason = models.TextField()
    forecast_score = models.FloatField()
    sentiment_score = models.FloatField()
    horizon = models.IntegerField(
        null=True, blank=True,
        help_text=(
            "Directional horizon for this signal in days (1, 5, or 20). "
            "Sourced from stocks.json Suggestion.DirectionalCheck.Horizon — "
            "i.e. which directional-classifier horizon backed the call."
        ),
    )
    dominant_sentiment = models.CharField(
        max_length=10, null=True, blank=True,
        choices=NewsSentiment.Sentiment.choices,
        help_text=(
            "Most-frequent news sentiment label across this ticker's "
            "articles. Sourced from stocks.json News.DominantSentiment."
        ),
    )
    contributions = models.JSONField(
        null=True, blank=True,
        help_text=(
            "Per-component contribution % to the fused Health score, "
            "shape: {Forecast: 69.76, Sentiment: 15.41, Technicals: 14.83}. "
            "Sourced from stocks.json Health.Contributions."
        ),
    )
    generated_at = models.DateTimeField(auto_now_add=True)
    valid_until = models.DateTimeField()

    class Meta:
        db_table = "stock_signal"
        ordering = ["-generated_at"]
        get_latest_by = "generated_at"
        indexes = [
            models.Index(fields=["ticker", "-generated_at"], name="idx_signal_ticker_gen_desc"),
        ]

    def __str__(self) -> str:
        return f"{self.ticker} {self.signal} ({self.confidence:.2f})"


class LiveMarketData(TimestampMixin):
    """Snapshot row per ticker — replaced every hour by finmate-live.

    The single source of truth for "current price + current technicals".
    One row per ticker; each hourly run wipes the table and writes a
    fresh snapshot. Tickers that didn't trade this session fall back
    to last real bar (from last_bars.json) — change_pct is 0 in that
    case since price didn't move.

    Technicals (rsi14, MAs, volatility, volume_ratio, eps) are sourced
    from stocks.json's Ratios block (computed daily by warm-3) and
    re-stamped on every hourly snapshot so the frontend can render
    "RSI: 65.97, MA50: 10.96" alongside the current price without a
    second query.
    """

    ticker = models.CharField(max_length=10)
    date = models.DateTimeField()
    open_price = models.DecimalField(max_digits=12, decimal_places=4)
    high = models.DecimalField(max_digits=12, decimal_places=4)
    low = models.DecimalField(max_digits=12, decimal_places=4)
    close = models.DecimalField(max_digits=12, decimal_places=4)
    volume = models.BigIntegerField()
    change_pct = models.FloatField(
        null=True, blank=True,
        help_text=(
            "Percent change vs prior close (from last_bars.json). "
            "(close - prior_close) / prior_close * 100. NULL when no "
            "prior close is known."
        ),
    )
    rsi14 = models.FloatField(null=True, blank=True)
    ma20 = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    ma50 = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    ma200 = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    volatility20d = models.FloatField(null=True, blank=True)
    volume_ratio = models.FloatField(null=True, blank=True)
    eps = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)

    class Meta:
        db_table = "live_market_data"
        unique_together = ("ticker", "date")
        ordering = ["ticker", "-date"]

    def __str__(self) -> str:
        return f"{self.ticker} @ {self.date} close={self.close}"
