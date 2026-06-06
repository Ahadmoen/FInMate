from fastapi import APIRouter, HTTPException, Request

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.generation.schemas import TickerSnapshotResponse, SignalData, ForecastData
from app.api.v1.query import _row_to_snapshot
from app.retrieval.structured import StructuredStore
from fastapi import Depends

log = get_logger(__name__)
router = APIRouter()


@router.get("/{symbol}/snapshot", response_model=TickerSnapshotResponse)
async def ticker_snapshot(
    symbol: str,
    request: Request,
    settings: Settings = Depends(get_settings),
):
    symbol = symbol.upper()
    if symbol not in settings.psx_tickers:
        raise HTTPException(status_code=404, detail=f"Ticker {symbol} not in PSX corpus")

    pool = getattr(request.app.state, "db_pool", None)
    sb   = getattr(request.app.state, "supabase", None)
    structured = StructuredStore(settings, pool=pool, supabase=sb)

    price_row = await structured.get_latest_price(symbol)
    sig_row   = await structured.get_signal(symbol)
    fore_row  = await structured.get_forecast(symbol)
    news_rows = await structured.get_news(symbol, limit=3)

    price_snap = _row_to_snapshot(symbol, price_row, settings) if price_row else None

    sig = None
    if sig_row:
        sig = SignalData(
            ticker=symbol,
            signal=sig_row.get("signal", ""),
            confidence=sig_row.get("confidence"),
            reason=sig_row.get("reason"),
            dominant_sentiment=sig_row.get("dominant_sentiment"),
        )

    fore = None
    if fore_row:
        fore = ForecastData(
            ticker=symbol,
            direction=fore_row.get("direction"),
            predicted_price=fore_row.get("predicted_price"),
            expected_change_pct=fore_row.get("expected_change_pct"),
            confidence=fore_row.get("confidence"),
            model_used=fore_row.get("model_used"),
            forecast_date=str(fore_row.get("forecast_date", "")),
        )

    # Freshness in seconds
    freshness = None
    if price_row and price_row.get("date"):
        from datetime import datetime, timezone
        try:
            raw = price_row["date"]
            if isinstance(raw, str):
                dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            else:
                dt = datetime.combine(raw, datetime.min.time(), tzinfo=timezone.utc)
            freshness = int((datetime.now(timezone.utc) - dt).total_seconds())
        except Exception:
            pass

    return TickerSnapshotResponse(
        ticker=symbol,
        company_name=settings.get_company_name(symbol),
        price=price_snap,
        signal=sig,
        forecast=fore,
        news=news_rows,
        freshness_seconds=freshness,
    )
