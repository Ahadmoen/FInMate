"""Redis cache layer.

Key strategy:
  embeddings  → sha256(text + model_name)           TTL: 30 days
  llm_news    → sha256(intent + query + tickers)    TTL: 5 min
  llm_filing  → sha256(intent + query + tickers)    TTL: 1 hour
  price       → never cached (must always be live)
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

import redis.asyncio as aioredis

from app.core.config import Settings
from app.core.logging import get_logger

log = get_logger(__name__)

_PREFIX = "aiva:"


class RedisCache:
    def __init__(self, client: aioredis.Redis, settings: Settings) -> None:
        self._r = client
        self._s = settings

    # ── Embeddings ────────────────────────────────────────────────────────────

    def _embedding_key(self, text: str) -> str:
        h = hashlib.sha256(
            f"{text}::{self._s.embedding_model}".encode()
        ).hexdigest()
        return f"{_PREFIX}emb:{h}"

    async def get_embedding(self, text: str) -> list[float] | None:
        key = self._embedding_key(text)
        raw = await self._r.get(key)
        if raw is None:
            return None
        return json.loads(raw)

    async def set_embedding(self, text: str, vector: list[float]) -> None:
        key = self._embedding_key(text)
        await self._r.setex(
            key, self._s.cache_embedding_ttl, json.dumps(vector)
        )

    async def get_embeddings_batch(
        self, texts: list[str]
    ) -> dict[str, list[float] | None]:
        keys = [self._embedding_key(t) for t in texts]
        values = await self._r.mget(*keys)
        return {
            text: json.loads(v) if v else None
            for text, v in zip(texts, values)
        }

    async def set_embeddings_batch(
        self, texts: list[str], vectors: list[list[float]]
    ) -> None:
        pipe = self._r.pipeline()
        for text, vec in zip(texts, vectors):
            key = self._embedding_key(text)
            pipe.setex(key, self._s.cache_embedding_ttl, json.dumps(vec))
        await pipe.execute()

    # ── LLM responses ─────────────────────────────────────────────────────────

    def _response_key(
        self,
        intent: str,
        query: str,
        tickers: list[str],
        sector: str | None = None,
        signal_filter: str | None = None,
    ) -> str:
        payload = (
            f"{intent}::{query}::"
            f"{'|'.join(sorted(tickers))}::"
            f"{sector or ''}::{signal_filter or ''}"
        )
        h = hashlib.sha256(payload.encode()).hexdigest()
        return f"{_PREFIX}resp:{h}"

    def _response_ttl(self, intent: str) -> int | None:
        """Return TTL in seconds, or None to skip caching."""
        if intent in ("PRICE_LOOKUP", "FUNDAMENTALS"):
            return None   # never cache — data changes continuously
        if intent == "NEWS_QA":
            return self._s.cache_news_response_ttl
        return self._s.cache_filing_response_ttl

    async def get_response(
        self,
        intent: str,
        query: str,
        tickers: list[str],
        sector: str | None = None,
        signal_filter: str | None = None,
    ) -> dict[str, Any] | None:
        ttl = self._response_ttl(intent)
        if ttl is None:
            return None
        raw = await self._r.get(
            self._response_key(intent, query, tickers, sector, signal_filter)
        )
        if raw is None:
            return None
        log.debug("cache_hit", intent=intent, sector=sector)
        return json.loads(raw)

    async def set_response(
        self,
        intent: str,
        query: str,
        tickers: list[str],
        payload: dict[str, Any],
        sector: str | None = None,
        signal_filter: str | None = None,
    ) -> None:
        ttl = self._response_ttl(intent)
        if ttl is None:
            return
        key = self._response_key(intent, query, tickers, sector, signal_filter)
        await self._r.setex(key, ttl, json.dumps(payload, default=str))

    # ── Health ────────────────────────────────────────────────────────────────

    async def ping(self) -> bool:
        try:
            return await self._r.ping()
        except Exception:
            return False
