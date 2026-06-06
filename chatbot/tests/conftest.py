"""Shared pytest fixtures.

External services (Qdrant, Redis, Supabase, OpenAI) are mocked so
unit tests run without network access.
Integration tests can opt into real services by setting
INTEGRATION_TESTS=1 in the environment.
"""
from __future__ import annotations

import os
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport


# ── Minimal settings override ──────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def override_settings(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://mock.supabase.co")
    monkeypatch.setenv("SUPABASE_KEY", "mock-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "mock-anthropic-key")
    monkeypatch.setenv("OPENAI_API_KEY", "mock-openai-key")
    monkeypatch.setenv("QDRANT_URL", "http://localhost:6333")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379")
    monkeypatch.setenv("ADMIN_API_KEY", "test-admin-key")


# ── Mock app state ─────────────────────────────────────────────────────────────

@pytest.fixture
def mock_vector_store():
    vs = MagicMock()
    vs.hybrid_search = AsyncMock(return_value=([], []))
    vs.rerank = AsyncMock(return_value=[])
    vs.upsert = AsyncMock()
    vs.collection_count = AsyncMock(return_value=42)
    vs.ensure_collection = AsyncMock()
    return vs


@pytest.fixture
def mock_structured_store():
    ss = MagicMock()
    ss.get_latest_price = AsyncMock(return_value={
        "ticker": "PSO",
        "open_price": 310.5,
        "close": 315.0,
        "high": 317.0,
        "low": 308.0,
        "volume": 1500000,
        "date": "2026-05-10",
    })
    ss.get_signal = AsyncMock(return_value={
        "ticker": "PSO",
        "signal": "BUY",
        "confidence": 0.87,
        "reason": "Strong momentum and positive sentiment",
        "dominant_sentiment": "positive",
    })
    ss.get_forecast = AsyncMock(return_value={
        "ticker": "PSO",
        "direction": "UP",
        "predicted_price": 325.0,
        "expected_change_pct": 3.17,
        "confidence": 0.75,
        "model_used": "xgboost_v2",
        "forecast_date": "2026-05-11",
    })
    ss.get_news = AsyncMock(return_value=[
        {"headline": "PSO reports strong quarterly results", "sentiment": "positive",
         "source": "dawn.com", "published_at": "2026-05-09T10:00:00Z", "score": 0.82},
    ])
    ss.get_top_movers = AsyncMock(return_value=[
        {"ticker": "PSO", "open_price": 310.5, "close": 315.0, "change_pct": 1.45, "volume": 1500000},
        {"ticker": "OGDC", "open_price": 185.0, "close": 189.0, "change_pct": 2.16, "volume": 800000},
    ])
    ss.get_buy_signals = AsyncMock(return_value=[
        {"ticker": "PSO", "signal": "BUY", "confidence": 0.87, "reason": "Momentum", "dominant_sentiment": "positive"},
    ])
    ss.get_all_latest_prices = AsyncMock(return_value=[
        {"ticker": "PSO", "date": "2026-05-10"},
    ])
    ss.get_unindexed_news = AsyncMock(return_value=[])
    return ss


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.classify_intent = AsyncMock(return_value={
        "intent": "PRICE_LOOKUP",
        "tickers": ["PSO"],
        "time_range": None,
    })
    llm.generate = AsyncMock(return_value="Test answer based on provided data.")
    llm._router_model = "claude-haiku-4-5-20251001"
    llm._provider = "anthropic"
    return llm


@pytest.fixture
def mock_embedder():
    emb = MagicMock()
    emb.embed = AsyncMock(return_value=[[0.1] * 3072])
    emb.embed_query = AsyncMock(return_value=[0.1] * 3072)
    return emb


@pytest.fixture
def mock_cache():
    cache = MagicMock()
    cache.get_response = AsyncMock(return_value=None)
    cache.set_response = AsyncMock()
    cache.get_embedding = AsyncMock(return_value=None)
    cache.set_embedding = AsyncMock()
    cache.get_embeddings_batch = AsyncMock(return_value={})
    cache.set_embeddings_batch = AsyncMock()
    cache.ping = AsyncMock(return_value=True)
    return cache


# ── Test app ───────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def async_client(mock_vector_store, mock_structured_store, mock_embedder, mock_cache):
    """AsyncClient with mocked app state — no real network calls."""
    from main import app

    app.state.db_pool = None
    app.state.supabase = None
    app.state.vector_store = mock_vector_store
    app.state.embedder = mock_embedder
    app.state.cache = mock_cache
    app.state.qdrant = MagicMock()
    app.state.redis = MagicMock()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
