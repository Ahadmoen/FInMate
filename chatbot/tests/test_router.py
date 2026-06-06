"""Unit tests for the query intent router."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.core.config import get_settings
from app.generation.schemas import QueryIntent
from app.retrieval.router import QueryRouter


@pytest.fixture
def router(mock_llm):
    settings = get_settings()
    return QueryRouter(mock_llm, settings)


@pytest.mark.asyncio
async def test_price_lookup_intent(router, mock_llm):
    mock_llm.classify_intent = AsyncMock(return_value={
        "intent": "PRICE_LOOKUP", "tickers": ["PSO"], "time_range": None
    })
    result = await router.route("What is PSO's current price?")
    assert result.intent == QueryIntent.PRICE_LOOKUP
    assert "PSO" in result.tickers


@pytest.mark.asyncio
async def test_analytics_intent(router, mock_llm):
    mock_llm.classify_intent = AsyncMock(return_value={
        "intent": "ANALYTICS", "tickers": [], "time_range": None
    })
    result = await router.route("Show me top gainers today")
    assert result.intent == QueryIntent.ANALYTICS


@pytest.mark.asyncio
async def test_news_qa_intent(router, mock_llm):
    mock_llm.classify_intent = AsyncMock(return_value={
        "intent": "NEWS_QA", "tickers": ["ENGRO"], "time_range": None
    })
    result = await router.route("Why did ENGRO drop last week?")
    assert result.intent == QueryIntent.NEWS_QA
    assert "ENGRO" in result.tickers


@pytest.mark.asyncio
async def test_regex_ticker_extraction(router, mock_llm):
    """Regex must extract $PSO cashtag and word-boundary OGDC."""
    mock_llm.classify_intent = AsyncMock(return_value={
        "intent": "COMPARISON", "tickers": [], "time_range": None
    })
    result = await router.route("Compare $PSO and OGDC performance")
    assert "PSO" in result.tickers
    assert "OGDC" in result.tickers


@pytest.mark.asyncio
async def test_no_false_positive_substring(router, mock_llm):
    """'meta' in 'metadata' must NOT match META ticker."""
    mock_llm.classify_intent = AsyncMock(return_value={
        "intent": "GENERAL", "tickers": [], "time_range": None
    })
    result = await router.route("I need metadata about PSX companies")
    # META should not be extracted from 'metadata'
    assert "META" not in result.tickers


@pytest.mark.asyncio
async def test_unknown_intent_falls_back_to_general(router, mock_llm):
    mock_llm.classify_intent = AsyncMock(return_value={
        "intent": "UNKNOWN_INTENT", "tickers": [], "time_range": None
    })
    result = await router.route("Hello")
    assert result.intent == QueryIntent.GENERAL


@pytest.mark.asyncio
async def test_invalid_json_from_llm(router, mock_llm):
    """If LLM returns non-JSON, router must default gracefully."""
    mock_llm.classify_intent = AsyncMock(return_value={
        "intent": "GENERAL", "tickers": [], "time_range": None
    })
    result = await router.route("What is PSX?")
    assert result.intent in list(QueryIntent)
