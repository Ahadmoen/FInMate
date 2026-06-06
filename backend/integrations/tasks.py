"""
Scheduled data ingestion tasks. Triggered by Celery beat.
See config/celery_schedule.py for the cron schedule.
"""
import uuid
from datetime import datetime, timezone

from celery import shared_task
from django.utils.timezone import now

from core.models import (
    ForecastTrend,
    LiveMarketData,
    NewsSentiment,
    StockForecast,
    StockSignal,
    StockSymbol,
    StockTechnicals,
)
from integrations.models import ScrapeRun


def _next_run_time():
    """Next 06:00 PKT as UTC — used as valid_until for StockSignal."""
    from datetime import timedelta
    from zoneinfo import ZoneInfo
    pkt = ZoneInfo("Asia/Karachi")
    target = datetime.now(pkt).replace(hour=6, minute=0, second=0, microsecond=0)
    if datetime.now(pkt) >= target:
        target += timedelta(days=1)
    return target.astimezone(timezone.utc)


# Suggestion.Action values in stocks.json (post-directional-classifier
# decision) map 1:1 onto StockSignal.Signal — both use the same 5-class
# enum. This is the FINAL recommendation users see.
ACTION_TO_SIGNAL = {
    "STRONG_BUY": StockSignal.Signal.STRONG_BUY,
    "BUY": StockSignal.Signal.BUY,
    "HOLD": StockSignal.Signal.HOLD,
    "SELL": StockSignal.Signal.SELL,
    "STRONG_SELL": StockSignal.Signal.STRONG_SELL,
}


@shared_task
def morning_full_fetch():
    """
    Full daily pipeline — runs at 06:00 PKT on weekdays.
    Order: scrapers -> ML modules -> write to DB.
    """
    run = ScrapeRun.objects.create(source="HISTORICAL", status="PENDING", started_at=now())
    rows_processed = 0
    try:
        # 1. Scrapers
        from integrations.scrapers.historical_scraper import main as historical_main
        from integrations.scrapers.key_ratios_scraper import main as ratios_main
        from integrations.scrapers.news_scraper import main as news_main
        historical_main()
        ratios_main()
        news_main()

        # 2. ML modules
        from ml_services.forecasting import main as forecasting_main
        from ml_services.sentiment import main as sentiment_main
        from ml_services.stock_health import main as stock_health_main
        forecasting_main()
        sentiment_main()
        stock_health_main()

        # 3. Write to DB
        rows_processed += _ingest_stocks()
        rows_processed += _ingest_news_sentiment()

        run.status = "SUCCESS"
        run.rows_processed = rows_processed
    except Exception as exc:
        run.status = "FAILED"
        run.notes = str(exc)
        raise
    finally:
        run.finished_at = now()
        run.save()


@shared_task
def hourly_refresh():
    """
    Intraday price refresh — runs hourly 09:00-15:00 PKT on weekdays.
    Runs live_scraper and updates LiveMarketData + MarketDataCache price fields.
    """
    run = ScrapeRun.objects.create(source="LIVE", status="PENDING", started_at=now())
    rows_processed = 0
    try:
        from integrations.scrapers.live_scraper import main as live_main
        live_main()
        rows_processed += _ingest_live_data()
        run.status = "SUCCESS"
        run.rows_processed = rows_processed
    except Exception as exc:
        run.status = "FAILED"
        run.notes = str(exc)
        raise
    finally:
        run.finished_at = now()
        run.save()


@shared_task
def run_registry_scraper():
    """
    Monthly symbol refresh — runs on 1st of each month at 02:00 PKT.
    Refreshes symbols.py from PSX listing then syncs to StockSymbol table.
    """
    run = ScrapeRun.objects.create(source="HISTORICAL", status="PENDING", started_at=now())
    try:
        from integrations.scrapers.registry_scraper import main as registry_main
        registry_main()
        _sync_symbols()
        run.status = "SUCCESS"
    except Exception as exc:
        run.status = "FAILED"
        run.notes = str(exc)
        raise
    finally:
        run.finished_at = now()
        run.save()


# ---------------------------------------------------------------------- #
# Private helpers — shared between management command and tasks
# ---------------------------------------------------------------------- #

def _ingest_stocks():
    """Load stocks.json -> StockSymbol, StockTechnicals, StockForecast, StockSignal.

    StockSignal is SNAPSHOT mode — previous signal rows for the same
    tickers are deleted before this run's signals are inserted, so each
    ticker has exactly one row reflecting today's call (horizon included).
    """
    import json
    from pathlib import Path
    path = Path(__file__).resolve().parent / "data" / "stocks.json"
    if not path.exists():
        return 0

    rows = json.loads(path.read_text())
    signal_valid_until = _next_run_time()
    today = now()

    # Build bulk lists
    symbols, technicals_rows, forecasts, signals = [], [], [], []

    for r in rows:
        ticker = r["Symbol"]
        technicals = r.get("Ratios", {}).get("Technicals", {})
        last_close = r.get("LastClose")
        forecast = r.get("Forecast", {})
        health = r.get("Health", {})
        suggestion = r.get("Suggestion", {})

        symbols.append(StockSymbol(
            id=uuid.uuid4(),
            ticker=ticker,
            company_name=r.get("Name", ""),
            sector=r.get("Industry", ""),
            is_active=True,
        ))

        # StockTechnicals — daily indicators (replaces the technicals
        # half of the deprecated MarketDataCache table). Live price
        # lives only in LiveMarketData now.
        if technicals or last_close is not None:
            fundamentals = r.get("Ratios", {}).get("Fundamentals", {})
            technicals_rows.append(StockTechnicals(
                id=uuid.uuid4(),
                ticker=ticker,
                rsi14=technicals.get("RSI14"),
                ma20=technicals.get("MA20"),
                ma50=technicals.get("MA50"),
                ma200=technicals.get("MA200"),
                volatility20d=technicals.get("Volatility20d"),
                volume_ratio=technicals.get("VolumeRatio"),
                eps=fundamentals.get("EPS"),
                computed_at=today,
            ))

        model_used = forecast.get("Model")
        predicted_price = forecast.get("PredictedPrice")
        if model_used and predicted_price is not None:
            forecasts.append(StockForecast(
                id=uuid.uuid4(),
                ticker=ticker,
                forecast_date=today.date(),
                model_used=model_used,
                direction=forecast.get("Direction", "STABLE"),
                confidence=forecast.get("Confidence", 0.0),
                mape=forecast.get("MAPE"),
                predicted_price=predicted_price,
                expected_change_pct=forecast.get("ExpectedChangePct"),
            ))

        # FINAL signal = Suggestion.Action (post-directional-classifier).
        # Health.Label is kept alongside as a diagnostic field so we can
        # see when the directional classifier overrode the fusion.
        signal_value = ACTION_TO_SIGNAL.get(suggestion.get("Action"))
        if signal_value:
            components = health.get("Components", {})
            weights = health.get("Weights", {})
            # Pull the directional horizon (1 / 5 / 20) backing this call.
            directional_check = suggestion.get("DirectionalCheck") or {}
            horizon_val = directional_check.get("Horizon")
            news_block = r.get("News") or {}
            signals.append(StockSignal(
                id=uuid.uuid4(),
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
                    f"Primary driver: {health.get('PrimaryDriver', '')}. "
                    f"Forecast weight {weights.get('Forecast', 0):.0%}, "
                    f"Sentiment weight {weights.get('Sentiment', 0):.0%}, "
                    f"Technicals weight {weights.get('Technicals', 0):.0%}."
                ),
                valid_until=signal_valid_until,
            ))

    # One DB round-trip per table
    StockSymbol.objects.bulk_create(
        symbols, update_conflicts=True,
        unique_fields=["ticker"],
        update_fields=["company_name", "sector", "is_active"],
    )
    StockTechnicals.objects.bulk_create(
        technicals_rows, update_conflicts=True,
        unique_fields=["ticker"],
        update_fields=["rsi14", "ma20", "ma50", "ma200",
                       "volatility20d", "volume_ratio", "eps", "computed_at"],
    )
    StockForecast.objects.bulk_create(
        forecasts, update_conflicts=True,
        unique_fields=["ticker", "forecast_date", "model_used"],
        update_fields=["direction", "confidence", "mape",
                       "predicted_price", "expected_change_pct"],
    )
    # StockSignal — SNAPSHOT mode: delete prior rows for these tickers,
    # then insert this run's. One row per ticker, no history accumulation.
    if signals:
        tickers_in_batch = list({s.ticker for s in signals})
        StockSignal.objects.filter(ticker__in=tickers_in_batch).delete()
        StockSignal.objects.bulk_create(signals)

    # Active-symbols filter — drop unforecastable tickers from the universe.
    #
    # Anything in symbols.py SYMBOLS but not in this run's stocks.json is
    # dead weight for the downstream scrapers (live / news / warm-1) that
    # iterate symbols sequentially and were timing out on the full 738
    # PSX universe. We mark those tickers `is_active=False` in StockSymbol
    # AND write a JSON list to integrations/data/active_symbols.json so
    # the scraper-side filter (symbols.py) can intersect on next run.
    forecasted = {r["Symbol"] for r in rows}
    _write_active_symbols(forecasted)

    return len(rows)


def _write_active_symbols(forecasted_tickers):
    """Persist the active-symbol set both to DB and to disk."""
    import json
    from pathlib import Path
    from integrations.scrapers.symbols import SYMBOLS as ALL_SYMBOLS
    full_universe = set(ALL_SYMBOLS)
    inactive = full_universe - set(forecasted_tickers)
    if inactive:
        StockSymbol.objects.filter(ticker__in=list(inactive)).update(is_active=False)
    StockSymbol.objects.filter(
        ticker__in=list(forecasted_tickers)
    ).update(is_active=True)

    out_path = Path(__file__).resolve().parent / "data" / "active_symbols.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(sorted(forecasted_tickers), indent=2))


def _ingest_forecast_trend():
    """Load forecasting_trend.json -> ForecastTrend.

    SNAPSHOT mode: delete prior rows for the tickers in this batch,
    then insert the new ~30-day forward curve. One curve per ticker
    per run; the table holds 'today's outlook only', not history.
    """
    import json
    from datetime import date as date_cls
    from pathlib import Path
    path = Path(__file__).resolve().parent / "data" / "forecasting_trend.json"
    if not path.exists():
        return 0

    rows = json.loads(path.read_text())
    objs = []
    for r in rows:
        ticker = r.get("Symbol")
        days_ahead = r.get("DaysAhead")
        predicted = r.get("PredictedClose")
        anchor = r.get("BasedOnLastClose")
        if not ticker or days_ahead is None or predicted is None or anchor is None:
            continue
        # Date may be either ISO string or already a date — handle the common case.
        date_str = r.get("Date", "")
        try:
            d = datetime.fromisoformat(date_str.replace("Z", "+00:00")).date()
        except (ValueError, AttributeError):
            d = date_cls.today()
        objs.append(ForecastTrend(
            id=uuid.uuid4(),
            ticker=ticker,
            date=d,
            days_ahead=days_ahead,
            predicted_close=predicted,
            direction=r.get("Direction", "STABLE"),
            model_used=r.get("Model", "ARIMA"),
            based_on_last_close=anchor,
            change_pct_from_anchor=r.get("ChangePctFromAnchor", 0.0),
        ))

    if objs:
        tickers_in_batch = list({o.ticker for o in objs})
        ForecastTrend.objects.filter(ticker__in=tickers_in_batch).delete()
        ForecastTrend.objects.bulk_create(objs)
    return len(objs)


NEWS_RETENTION_DAYS = 30


def _ingest_news_sentiment():
    """Load news_sentiment.json -> NewsSentiment, skipping already-stored links.

    30-DAY RETENTION: rows older than `NEWS_RETENTION_DAYS` (by published_at)
    are deleted at the start of each run. Keeps the table small for a 738-symbol
    universe — typical daily news volume × 30 days × 738 tickers ≈ tens of
    thousands of rows, manageable on the Supabase free tier.
    """
    import json
    from datetime import timedelta
    from pathlib import Path
    path = Path(__file__).resolve().parent / "data" / "news_sentiment.json"
    if not path.exists():
        return 0

    cutoff = now() - timedelta(days=NEWS_RETENTION_DAYS)
    NewsSentiment.objects.filter(published_at__lt=cutoff).delete()

    rows = json.loads(path.read_text())
    existing_links = set(NewsSentiment.objects.values_list("link", flat=True))
    objs = []
    for r in rows:
        link = r.get("Link", "")
        if link in existing_links:
            continue
        existing_links.add(link)
        published = datetime.fromisoformat(r["Date"].replace("Z", "+00:00"))
        # Skip articles already older than retention — no point inserting
        # what the next run will immediately delete.
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
    if objs:
        NewsSentiment.objects.bulk_create(objs, ignore_conflicts=True)
    return len(objs)


def _ingest_live_data():
    """Load live_data.json -> LiveMarketData.

    FULL-SNAPSHOT mode: every hourly run wipes the entire
    live_market_data table and writes one row per ticker — either
    the latest real hourly bar (for tickers that traded this session)
    or a last-close stub (for tickers that didn't). Frontend always
    reads exactly one row per ticker for "current price".
    """
    import json
    from pathlib import Path
    path = Path(__file__).resolve().parent / "data" / "live_data.json"
    if not path.exists():
        return 0

    rows = json.loads(path.read_text())

    # Wipe the table — snapshot mode, no history within or across days.
    if rows:
        LiveMarketData.objects.all().delete()

    # Bulk insert one row per ticker
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
    if objs:
        LiveMarketData.objects.bulk_create(
            objs,
            update_conflicts=True,
            unique_fields=["ticker", "date"],
            update_fields=["open_price", "high", "low", "close", "volume"],
        )

    # MarketDataCache mirror-update removed — live price now lives only
    # in LiveMarketData. Frontend should query the latest LiveMarketData
    # row per ticker (highest `date`) for the current/today values.

    return len(objs)


def _sync_symbols():
    """Sync symbols.py SYMBOLS + COMPANIES -> StockSymbol table."""
    from integrations.scrapers.symbols import COMPANIES, SYMBOLS
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
