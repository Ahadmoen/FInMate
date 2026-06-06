from supabase import create_client, Client
from app.utils.logger import logger
from typing import Optional, Dict, List
from dotenv import load_dotenv
import os

load_dotenv()

# ── Initialize Supabase Client ────────────────────────────────
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def get_stock_data(ticker: str) -> Optional[Dict]:
    """
    Fetch latest OHLCV data from live_market_data table.
    Returns open, high, low, close, volume for the ticker.
    """
    try:
        logger.info(f"Fetching live market data for {ticker}")

        response = supabase.table("live_market_data")\
            .select("*")\
            .eq("ticker", ticker.upper())\
            .order("date", desc=True)\
            .limit(1)\
            .execute()

        if response.data and len(response.data) > 0:
            row = response.data[0]
            logger.info(f"Found live data for {ticker}: {row}")
            return row

        logger.warning(f"No data found in live_market_data for ticker='{ticker}'")
        return None

    except Exception as e:
        logger.error(f"Error fetching stock data for {ticker}: {e}", exc_info=True)
        return None


def get_stock_signal(ticker: str) -> Optional[Dict]:
    """
    Fetch latest BUY/SELL/HOLD signal for a stock.
    """
    try:
        logger.info(f"Fetching signal for {ticker}")

        response = supabase.table("stock_signal")\
            .select("*")\
            .eq("ticker", ticker.upper())\
            .order("generated_at", desc=True)\
            .limit(1)\
            .execute()

        if response.data and len(response.data) > 0:
            return response.data[0]

        return None

    except Exception as e:
        logger.error(f"Error fetching signal: {e}")
        return None


def get_stock_forecast(ticker: str) -> Optional[Dict]:
    """
    Fetch latest AI price forecast for a stock.
    Returns predicted price, direction, confidence.
    """
    try:
        logger.info(f"Fetching forecast for {ticker}")

        response = supabase.table("stock_forecast")\
            .select("*")\
            .eq("ticker", ticker.upper())\
            .order("forecast_date", desc=True)\
            .limit(1)\
            .execute()

        if response.data and len(response.data) > 0:
            return response.data[0]

        return None

    except Exception as e:
        logger.error(f"Error fetching forecast: {e}")
        return None


def get_stock_news(ticker: str, limit: int = 3) -> List[Dict]:
    """
    Fetch latest news and sentiment for a stock.
    """
    try:
        logger.info(f"Fetching news for {ticker}")

        response = supabase.table("news_sentiment")\
            .select("headline, sentiment, source, published_at, score")\
            .eq("ticker", ticker.upper())\
            .order("published_at", desc=True)\
            .limit(limit)\
            .execute()

        return response.data if response.data else []

    except Exception as e:
        logger.error(f"Error fetching news: {e}")
        return []


def get_top_gainers(limit: int = 5) -> List[Dict]:
    """
    Fetch top gaining stocks by comparing close vs open price.
    """
    try:
        logger.info("Fetching top gainers from live_market_data")

        response = supabase.table("live_market_data")\
            .select("ticker, open_price, close, high, low, volume, date")\
            .order("date", desc=True)\
            .limit(100)\
            .execute()
                

        if not response.data:
            return []

        # Calculate change % and sort
        stocks = []
        seen = set()
        for row in response.data:
            ticker = row["ticker"]
            if ticker in seen:
                continue
            seen.add(ticker)
            open_price = row.get("open_price", 0)
            close = row.get("close", 0)
            if open_price and open_price > 0:
                change_pct = ((close - open_price) / open_price) * 100
                stocks.append({
                    "ticker": ticker,
                    "open_price": open_price,
                    "close": close,
                    "change_pct": round(change_pct, 2),
                    "volume": row.get("volume")
                })

        # Sort by change_pct descending
        stocks.sort(key=lambda x: x["change_pct"], reverse=True)
       
        return stocks[:limit]

    except Exception as e:
        logger.error(f"Error fetching top gainers: {e}")
        return []


def get_top_losers(limit: int = 5) -> List[Dict]:
    """
    Fetch top losing stocks by comparing close vs open price.
    """
    try:
        gainers = get_top_gainers(100)
        gainers.sort(key=lambda x: x["change_pct"])
        return gainers[:limit]

    except Exception as e:
        logger.error(f"Error fetching top losers: {e}")
        return []


def get_buy_signals(limit: int = 5) -> List[Dict]:
    """
    Fetch current BUY and STRONG_BUY signals, STRONG_BUY first then by confidence.
    """
    try:
        response = supabase.table("stock_signal")\
            .select("ticker, signal, confidence, reason, dominant_sentiment")\
            .in_("signal", ["BUY", "STRONG_BUY"])\
            .order("confidence", desc=True)\
            .limit(limit * 2)\
            .execute()

        data = response.data or []
        data.sort(key=lambda x: (0 if x["signal"] == "STRONG_BUY" else 1, -x.get("confidence", 0)))
        return data[:limit]

    except Exception as e:
        logger.error(f"Error fetching buy signals: {e}")
        return []
