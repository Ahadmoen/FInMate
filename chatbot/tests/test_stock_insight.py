"""Unit tests for the Stock Insight Card module."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.stock_insight import is_stock_query, extract_ticker, build_insight_card
from app.core.config import Settings


def _settings() -> Settings:
    return Settings()


# ── is_stock_query ────────────────────────────────────────────────────────────

def test_stock_query_price_keyword():
    assert is_stock_query("What is Apple stock price?") is True

def test_stock_query_psx_ticker():
    assert is_stock_query("Tell me about OGDC") is True

def test_stock_query_pkr_keyword():
    assert is_stock_query("PSX market today in PKR") is True

def test_non_stock_query_founder():
    assert is_stock_query("Who founded Apple?") is False

def test_non_stock_query_greeting():
    assert is_stock_query("Hello, how are you?") is False

def test_non_stock_query_general():
    assert is_stock_query("What is the weather like today?") is False


# ── extract_ticker ────────────────────────────────────────────────────────────

def test_extract_ticker_bare_symbol():
    settings = _settings()
    assert extract_ticker("What is OGDC price?", settings) == "OGDC"

def test_extract_ticker_cashtag():
    settings = _settings()
    assert extract_ticker("Buy $HBL now?", settings) == "HBL"

def test_extract_ticker_company_name():
    settings = _settings()
    assert extract_ticker("Tell me about Habib Bank Limited", settings) == "HBL"

def test_extract_ticker_unknown_company():
    settings = _settings()
    assert extract_ticker("Tell me about Apple Inc", settings) is None

def test_extract_ticker_prefers_longer_name():
    # "Engro Fertilizers" is longer than "Engro" alone — should match EFERT not ENGRO
    settings = _settings()
    result = extract_ticker("What about Engro Fertilizers?", settings)
    assert result == "EFERT"


# ── build_insight_card ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_build_insight_card_returns_card_for_stock_query():
    settings = _settings()
    mock_store = MagicMock()
    mock_store.get_latest_price = AsyncMock(return_value={
        "ticker": "OGDC",
        "open_price": 150.5,
        "close": 155.0,
        "high": 157.0,
        "low": 149.0,
        "volume": 500000,
        "date": "2026-05-15",
    })
    card = await build_insight_card("What is OGDC stock price?", mock_store, settings)
    assert card is not None
    assert card["symbol"] == "OGDC"
    assert card["company_name"] == "Oil & Gas Development Company"
    assert card["current_price"] == 155.0
    assert card["currency"] == "PKR"
    assert card["updated_at"] == "2026-05-15"


@pytest.mark.asyncio
async def test_build_insight_card_none_for_non_stock_query():
    settings = _settings()
    mock_store = MagicMock()
    card = await build_insight_card("Who founded Apple?", mock_store, settings)
    assert card is None


@pytest.mark.asyncio
async def test_build_insight_card_none_when_no_data():
    settings = _settings()
    mock_store = MagicMock()
    mock_store.get_latest_price = AsyncMock(return_value=None)
    card = await build_insight_card("What is OGDC price?", mock_store, settings)
    assert card is None


@pytest.mark.asyncio
async def test_build_insight_card_none_for_unknown_ticker():
    settings = _settings()
    mock_store = MagicMock()
    # "Apple stock" has keyword "stock" so is_stock_query passes,
    # but extract_ticker should return None (Apple is not a PSX ticker)
    card = await build_insight_card("Apple stock price today", mock_store, settings)
    assert card is None
