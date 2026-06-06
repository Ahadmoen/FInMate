"""Batched embedding client.

Providers:
  local  (default) — sentence-transformers all-MiniLM-L6-v2, 384-dim, runs on CPU.
                     No API key needed. Already installed in venv.
  openai           — text-embedding-3-large, 3072-dim. Requires OPENAI_API_KEY.

The active provider is set via EMBEDDING_PROVIDER env var (default: "local").
All embeddings are Redis-cached (30-day TTL) keyed by sha256(text + model_name).
"""
from __future__ import annotations

import asyncio
import math
import re
from typing import TYPE_CHECKING

from app.core.config import Settings
from app.core.logging import get_logger

if TYPE_CHECKING:
    from app.cache.redis_cache import RedisCache

log = get_logger(__name__)

# Lazy-loaded local model — loaded on first embed call, not at import time
_local_model = None
_local_model_name: str | None = None


def _get_local_model(model_name: str):
    global _local_model, _local_model_name
    if _local_model is None or _local_model_name != model_name:
        import contextlib
        import io
        from sentence_transformers import SentenceTransformer
        log.info("loading_local_embedding_model", model=model_name)
        # Redirect stderr so tqdm progress bars don't hit the Windows OSError
        # ([Errno 22] Invalid argument) when run inside asyncio.to_thread.
        with contextlib.redirect_stderr(io.StringIO()):
            _local_model = SentenceTransformer(model_name)
        _local_model_name = model_name
        log.info("local_embedding_model_ready", model=model_name)
    return _local_model


class EmbeddingClient:
    def __init__(self, settings: Settings, cache: "RedisCache | None" = None) -> None:
        self._settings = settings
        self._cache = cache
        self._provider = settings.embedding_provider
        self._model_name = settings.embedding_model
        self._batch = settings.embedding_batch_size
        self._dim = settings.embedding_dimensions

        # OpenAI client is only built if the provider is openai
        self._openai_client = None
        if self._provider == "openai":
            import openai
            self._openai_client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Return embeddings for all texts. Cache hits are served from Redis."""
        if not texts:
            return []

        cached: dict[str, list[float] | None] = {}
        if self._cache:
            cached = await self._cache.get_embeddings_batch(texts)

        miss_texts = [t for t in texts if cached.get(t) is None]
        miss_vectors: list[list[float]] = []

        if miss_texts:
            if self._provider == "openai":
                miss_vectors = await self._embed_openai(miss_texts)
            else:
                miss_vectors = await self._embed_local(miss_texts)

            if self._cache:
                await self._cache.set_embeddings_batch(miss_texts, miss_vectors)
            for t, v in zip(miss_texts, miss_vectors):
                cached[t] = v

        return [cached[t] for t in texts]  # type: ignore[return-value]

    async def embed_query(self, text: str) -> list[float]:
        results = await self.embed([text])
        return results[0]

    # ── Local sentence-transformers ───────────────────────────────────────────

    async def _embed_local(self, texts: list[str]) -> list[list[float]]:
        """Run SentenceTransformer.encode() in a thread pool to avoid blocking."""
        model_name = self._model_name
        batch = self._batch

        def _load_and_encode():
            model = _get_local_model(model_name)
            vecs = model.encode(texts, batch_size=batch, show_progress_bar=False)
            return [v.tolist() for v in vecs]

        vectors = await asyncio.to_thread(_load_and_encode)
        log.debug("local_embed_done", count=len(texts))
        return vectors

    # ── OpenAI API ────────────────────────────────────────────────────────────

    async def _embed_openai(self, texts: list[str]) -> list[list[float]]:
        results: list[list[float]] = []
        for i in range(0, len(texts), self._batch):
            batch = texts[i : i + self._batch]
            resp = await self._openai_client.embeddings.create(
                model=self._model_name,
                input=batch,
                dimensions=self._dim,
            )
            for item in sorted(resp.data, key=lambda x: x.index):
                results.append(item.embedding)
            log.debug("openai_embed_batch_done", size=len(batch), offset=i)
        return results


# ── BM25 sparse vector (local, no API needed) ─────────────────────────────────

def compute_sparse_vector(text: str) -> dict[str, list[int] | list[float]]:
    """Return {indices, values} for a lightweight BM25-style sparse vector."""
    tokens = re.findall(r"[a-zA-Z0-9]+", text.lower())
    tf: dict[int, int] = {}
    for token in tokens:
        idx = abs(hash(token)) % 30000
        tf[idx] = tf.get(idx, 0) + 1

    total = len(tokens) or 1
    indices = list(tf.keys())
    values = [round(math.log(1 + count / total), 6) for count in tf.values()]
    return {"indices": indices, "values": values}
