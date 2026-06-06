"""Stock Insight Card — structured snapshot attached to stock-related responses.

Triggered when a user query mentions a known PSX ticker or stock keyword.
Data is pulled from the existing StructuredStore (Supabase live_market_data).
"""
from __future__ import annotations

import re
from typing import Any

from app.core.config import Settings
from app.core.logging import get_logger
from app.retrieval.structured import StructuredStore

log = get_logger(__name__)

_STOCK_KEYWORDS = {
    "price", "stock", "share", "ticker", "market", "trading", "trade",
    "buy", "sell", "signal", "forecast", "volume", "close", "open",
    "high", "low", "gain", "loss", "chart", "invest", "portfolio",
    "dividend", "equity", "psx", "pkr", "ohlcv", "holding",
}

# Matches $PSO or bare ALL-CAPS words like OGDC (2–8 letters, word-boundary)
_CASHTAG = re.compile(r"\$([A-Z]{2,8})|(?<!\w)([A-Z]{2,8})(?!\w)")


def is_stock_query(message: str) -> bool:
    """Return True if the message appears to be asking about a stock."""
    if any(kw in message.lower() for kw in _STOCK_KEYWORDS):
        return True
    if _CASHTAG.search(message):
        return True
    return False


def extract_ticker(message: str, settings: Settings) -> str | None:
    """Extract the first recognisable PSX ticker from message text."""
    # 1. Cashtag or bare uppercase word that is a known ticker
    for m in _CASHTAG.finditer(message):
        candidate = (m.group(1) or m.group(2)).upper()
        if candidate in settings.psx_tickers:
            return candidate
    # 2. Company name match (longest match wins)
    best: tuple[int, str | None] = (0, None)
    lower_msg = message.lower()
    for ticker, name in settings.psx_company_names.items():
        name_lower = name.lower()
        if name_lower in lower_msg and len(name_lower) > best[0]:
            best = (len(name_lower), ticker)
    return best[1]


async def fetch_stock_data(
    ticker: str, structured: StructuredStore
) -> dict[str, Any] | None:
    """Fetch the latest price row for a PSX ticker."""
    try:
        return await structured.get_latest_price(ticker)
    except Exception as exc:
        log.warning("stock_insight_fetch_failed", ticker=ticker, error=str(exc))
        return None


async def build_insight_card(
    message: str,
    structured: StructuredStore,
    settings: Settings,
    ticker: str | None = None,
) -> dict[str, Any] | None:
    """
    Return a dict suitable for StockInsightCard if live price data exists.

    Pass `ticker` to skip text extraction (used when the router has already
    identified the primary ticker). Otherwise falls back to regex NER on message.
    Returns None if no ticker is found or no data exists in Supabase.
    """
    if ticker is None:
        if not is_stock_query(message):
            return None
        ticker = extract_ticker(message, settings)
    if not ticker:
        return None

    row = await fetch_stock_data(ticker, structured)
    if not row:
        return None

    open_p  = row.get("open_price")
    close_p = row.get("close")
    high_p  = row.get("high")
    low_p   = row.get("low")
    date_v  = row.get("date")

    return {
        "symbol":        ticker,
        "company_name":  settings.get_company_name(ticker),
        "open":          float(open_p)  if open_p  is not None else None,
        "current_price": float(close_p) if close_p is not None else None,
        "high":          float(high_p)  if high_p  is not None else None,
        "low":           float(low_p)   if low_p   is not None else None,
        "volume":        row.get("volume"),
        "currency":      "PKR",
        "updated_at":    str(date_v) if date_v is not None else None,
    }
