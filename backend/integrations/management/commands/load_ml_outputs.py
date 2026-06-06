"""
One-time seed command + daily ingestion helper.

Loads final ML pipeline outputs from JSON files into the database.

Usage:
    python manage.py load_ml_outputs
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from django.core.management.base import BaseCommand
from django.utils.timezone import now

from core.models import (
    LiveMarketData,
    NewsSentiment,
    StockForecast,
    StockSignal,
    StockSymbol,
    StockTechnicals,
)
from integrations.scrapers.symbols import COMPANIES, SYMBOLS

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "integrations" / "data"

# stocks.json Suggestion.Action values — already 5-class, map 1:1 to
# StockSignal.Signal. This is the FINAL post-directional recommendation.
ACTION_TO_SIGNAL = {
    "STRONG_BUY": StockSignal.Signal.STRONG_BUY,
    "BUY": StockSignal.Signal.BUY,
    "HOLD": StockSignal.Signal.HOLD,
    "SELL": StockSignal.Signal.SELL,
    "STRONG_SELL": StockSignal.Signal.STRONG_SELL,
}


class Command(BaseCommand):
    help = "Seed DB from existing ML pipeline JSON outputs."

    def handle(self, *args, **opts):
        self.stdout.write("=== load_ml_outputs ===")
        self._load_symbols()
        self._load_stocks()
        self._load_news_sentiment()
        self._load_live_data()
        self.stdout.write(self.style.SUCCESS("Done."))

    # ---------------------------------------------------------------------- #

    def _load_symbols(self):
        self.stdout.write("Loading symbols.py -> StockSymbol...")
        import uuid
        objs = [
            StockSymbol(
                id=uuid.uuid4(),
                ticker=ticker,
                company_name=COMPANIES.get(ticker, {}).get("name", ""),
                sector=COMPANIES.get(ticker, {}).get("industry", ""),
                is_active=True,
            )
            for ticker in SYMBOLS
        ]
        StockSymbol.objects.bulk_create(
            objs,
            update_conflicts=True,
            unique_fields=["ticker"],
            update_fields=["company_name", "sector", "is_active"],
        )
        self.stdout.write(f"  StockSymbol: {len(objs)} upserted")

    def _load_stocks(self):
        self.stdout.write("Loading stocks.json -> StockSymbol, MarketDataCache, StockForecast, StockSignal...")
        path = DATA_DIR / "stocks.json"
        if not path.exists():
            self.stdout.write(self.style.WARNING("  stocks.json not found, skipping."))
            return

        rows = json.loads(path.read_text())
        sym_updated = tech_updated = forecast_updated = signal_created = 0
        signal_valid_until = self._next_run_time()

        # SNAPSHOT mode for StockSignal — wipe prior rows for the tickers
        # we're about to write so each ticker has exactly one signal row.
        incoming_signal_tickers = [
            r["Symbol"]
            for r in rows
            if ACTION_TO_SIGNAL.get(r.get("Suggestion", {}).get("Action"))
        ]
        if incoming_signal_tickers:
            StockSignal.objects.filter(ticker__in=incoming_signal_tickers).delete()

        for r in rows:
            ticker = r["Symbol"]

            # StockSymbol
            StockSymbol.objects.update_or_create(
                ticker=ticker,
                defaults={
                    "company_name": r.get("Name", ""),
                    "sector": r.get("Industry", ""),
                    "is_active": True,
                },
            )
            sym_updated += 1

            # StockTechnicals — daily indicators (replaces the technicals
            # half of the deprecated MarketDataCache table). Live price
            # lives only in LiveMarketData now.
            technicals = r.get("Ratios", {}).get("Technicals", {})
            fundamentals = r.get("Ratios", {}).get("Fundamentals", {})
            if technicals or r.get("LastClose") is not None:
                StockTechnicals.objects.update_or_create(
                    ticker=ticker,
                    defaults={
                        "rsi14": technicals.get("RSI14"),
                        "ma20": technicals.get("MA20"),
                        "ma50": technicals.get("MA50"),
                        "ma200": technicals.get("MA200"),
                        "volatility20d": technicals.get("Volatility20d"),
                        "volume_ratio": technicals.get("VolumeRatio"),
                        "eps": fundamentals.get("EPS"),
                        "computed_at": now(),
                    },
                )
                tech_updated += 1

            # StockForecast — best model only
            forecast = r.get("Forecast", {})
            model_used = forecast.get("Model")
            predicted_price = forecast.get("PredictedPrice")
            if model_used and predicted_price is not None:
                StockForecast.objects.update_or_create(
                    ticker=ticker,
                    forecast_date=now().date(),
                    model_used=model_used,
                    defaults={
                        "direction": forecast.get("Direction", "STABLE"),
                        "confidence": forecast.get("Confidence", 0.0),
                        "mape": forecast.get("MAPE"),
                        "predicted_price": predicted_price,
                        "expected_change_pct": forecast.get("ExpectedChangePct"),
                    },
                )
                forecast_updated += 1

            # StockSignal — snapshot row (one per ticker, replaces prior).
            # FINAL signal = Suggestion.Action (post-directional-classifier);
            # Health.Label kept alongside as `health_label` for diagnostics.
            health = r.get("Health", {})
            suggestion = r.get("Suggestion", {})
            news_block = r.get("News") or {}
            signal_value = ACTION_TO_SIGNAL.get(suggestion.get("Action"))
            if signal_value:
                components = health.get("Components", {})
                primary_driver = health.get("PrimaryDriver", "")
                weights = health.get("Weights", {})
                # Pull the directional horizon (1 / 5 / 20) backing this call.
                directional_check = suggestion.get("DirectionalCheck") or {}
                horizon_val = directional_check.get("Horizon")
                StockSignal.objects.create(
                    ticker=ticker,
                    signal=signal_value,
                    health_label=health.get("Label"),
                    confidence=abs(health.get("Score", 0.0)),
                    suggestion_confidence=suggestion.get("Confidence"),
                    blended_score=suggestion.get("BlendedScore"),
                    forecast_signed_score=suggestion.get("ForecastSignedScore"),
                    signal_strength=suggestion.get("SignalStrength"),
                    forecast_score=components.get("Forecast", 0.0),
                    sentiment_score=components.get("Sentiment", 0.0),
                    horizon=horizon_val,
                    dominant_sentiment=news_block.get("DominantSentiment"),
                    contributions=health.get("Contributions") or None,
                    reason=(
                        f"Primary driver: {primary_driver}. "
                        f"Forecast weight {weights.get('Forecast', 0):.0%}, "
                        f"Sentiment weight {weights.get('Sentiment', 0):.0%}, "
                        f"Technicals weight {weights.get('Technicals', 0):.0%}."
                    ),
                    valid_until=signal_valid_until,
                )
                signal_created += 1

        self.stdout.write(
            f"  StockSymbol: {sym_updated} upserted | "
            f"StockTechnicals: {tech_updated} upserted | "
            f"StockForecast: {forecast_updated} upserted | "
            f"StockSignal: {signal_created} created (snapshot mode)"
        )

    def _load_news_sentiment(self):
        self.stdout.write("Loading news_sentiment.json -> NewsSentiment...")
        path = DATA_DIR / "news_sentiment.json"
        if not path.exists():
            self.stdout.write(self.style.WARNING("  news_sentiment.json not found, skipping."))
            return

        import uuid
        from datetime import timedelta

        # 30-DAY RETENTION: drop articles older than 30 days first.
        cutoff = now() - timedelta(days=30)
        deleted = NewsSentiment.objects.filter(published_at__lt=cutoff).delete()
        deleted_count = deleted[0] if deleted else 0
        self.stdout.write(f"  pruned {deleted_count} articles older than 30 days")

        rows = json.loads(path.read_text())
        existing_links = set(NewsSentiment.objects.values_list("link", flat=True))
        objs = []
        for r in rows:
            link = r.get("Link", "")
            if link in existing_links:
                continue
            existing_links.add(link)
            published = datetime.fromisoformat(r["Date"].replace("Z", "+00:00"))
            # Skip articles already past retention.
            if published < cutoff:
                continue
            objs.append(NewsSentiment(
                id=uuid.uuid4(),
                ticker=r.get("Symbol", ""),
                industry=r.get("Market", ""),
                industry_wise=r.get("IndustryWise", ""),
                headline=r.get("Heading", ""),
                link=link,
                source=r.get("Platform", ""),
                sentiment=r.get("Sentiment", "NEUTRAL"),
                score=r.get("SentimentScore", 0.0),
                published_at=published,
            ))
        NewsSentiment.objects.bulk_create(objs, ignore_conflicts=True)
        self.stdout.write(
            f"  NewsSentiment: {len(objs)} created, "
            f"{len(rows) - len(objs)} skipped (duplicates or too-old)"
        )

    def _load_live_data(self):
        self.stdout.write("Loading live_data.json -> LiveMarketData...")
        path = DATA_DIR / "live_data.json"
        if not path.exists():
            self.stdout.write(self.style.WARNING("  live_data.json not found, skipping."))
            return

        import uuid
        rows = json.loads(path.read_text())

        # FULL-SNAPSHOT mode: every run wipes the table — one row per
        # ticker, replaced each hour with either the latest real bar
        # or a last-close stub.
        if rows:
            deleted = LiveMarketData.objects.all().delete()
            self.stdout.write(f"  wiped {deleted[0] if deleted else 0} prior rows (snapshot mode)")

        objs = [
            LiveMarketData(
                id=uuid.uuid4(),
                ticker=r["Symbol"],
                date=datetime.fromisoformat(r["Date"].replace("Z", "+00:00")),
                open_price=r["Open"],
                high=r["High"],
                low=r["Low"],
                close=r["Close"],
                volume=r["Volume"],
                change_pct=r.get("ChangePct"),
                rsi14=r.get("RSI14"),
                ma20=r.get("MA20"),
                ma50=r.get("MA50"),
                ma200=r.get("MA200"),
                volatility20d=r.get("Volatility20d"),
                volume_ratio=r.get("VolumeRatio"),
                eps=r.get("EPS"),
            )
            for r in rows
        ]
        LiveMarketData.objects.bulk_create(
            objs,
            update_conflicts=True,
            unique_fields=["ticker", "date"],
            update_fields=[
                "open_price", "high", "low", "close", "volume",
                "change_pct", "rsi14", "ma20", "ma50", "ma200",
                "volatility20d", "volume_ratio", "eps",
            ],
        )
        self.stdout.write(f"  LiveMarketData: {len(objs)} upserted")

    def _next_run_time(self):
        """Next 06:00 PKT — used as valid_until for StockSignal."""
        from zoneinfo import ZoneInfo
        pkt = ZoneInfo("Asia/Karachi")
        today = datetime.now(pkt).replace(hour=6, minute=0, second=0, microsecond=0)
        if datetime.now(pkt) >= today:
            from datetime import timedelta
            today += timedelta(days=1)
        return today.astimezone(timezone.utc)
