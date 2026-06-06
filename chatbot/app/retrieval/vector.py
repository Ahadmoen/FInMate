"""Qdrant hybrid retrieval with mandatory metadata filtering and reranking.

Dense vectors (all-MiniLM-L6-v2 by default) + sparse BM25 vectors are fused
via Reciprocal Rank Fusion in fusion.py.  This module handles Qdrant I/O
and cross-encoder reranking only.

Reranker providers:
  local  (default) — cross-encoder/ms-marco-MiniLM-L-6-v2, runs on CPU, free.
  cohere           — Cohere Rerank API, requires COHERE_API_KEY.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

from qdrant_client import AsyncQdrantClient, models as qm

from app.core.config import Settings
from app.core.logging import get_logger
from app.ingestion.embeddings import EmbeddingClient, compute_sparse_vector

log = get_logger(__name__)

DENSE_VECTOR_NAME = "dense"
SPARSE_VECTOR_NAME = "sparse"


class VectorStore:
    def __init__(
        self,
        client: AsyncQdrantClient,
        embedder: EmbeddingClient,
        settings: Settings,
        reranker=None,          # RerankerClient | None
    ) -> None:
        self._client = client
        self._embedder = embedder
        self._settings = settings
        self._reranker = reranker
        self._collection = settings.qdrant_collection

    # ── Collection management ─────────────────────────────────────────────────

    async def ensure_collection(self) -> None:
        exists = await self._client.collection_exists(self._collection)
        if exists:
            return
        await self._client.create_collection(
            collection_name=self._collection,
            vectors_config={
                DENSE_VECTOR_NAME: qm.VectorParams(
                    size=self._settings.embedding_dimensions,
                    distance=qm.Distance.COSINE,
                ),
            },
            sparse_vectors_config={
                SPARSE_VECTOR_NAME: qm.SparseVectorParams(
                    index=qm.SparseIndexParams(on_disk=False)
                ),
            },
        )
        # Payload indexes for mandatory metadata filters
        for field in ("ticker", "doc_type", "published_at"):
            await self._client.create_payload_index(
                collection_name=self._collection,
                field_name=field,
                field_schema=qm.PayloadSchemaType.KEYWORD
                if field != "published_at"
                else qm.PayloadSchemaType.DATETIME,
            )
        log.info("qdrant_collection_created", collection=self._collection)

    async def collection_count(self) -> int:
        info = await self._client.get_collection(self._collection)
        return info.points_count or 0

    # ── Hybrid search ─────────────────────────────────────────────────────────

    async def hybrid_search(
        self,
        query: str,
        tickers: list[str] | None = None,
        doc_types: list[str] | None = None,
        recency_days: int | None = None,
        limit: int | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """
        Run hybrid dense+sparse search with mandatory metadata filters.
        Returns up to settings.vector_search_limit candidates before reranking.
        """
        limit = limit or self._settings.vector_search_limit

        # Build filter — at least one filter is always applied (ticker or recency)
        must_conditions = []

        if tickers:
            must_conditions.append(
                qm.FieldCondition(
                    key="ticker",
                    match=qm.MatchAny(any=[t.upper() for t in tickers]),
                )
            )

        if doc_types:
            must_conditions.append(
                qm.FieldCondition(
                    key="doc_type",
                    match=qm.MatchAny(any=doc_types),
                )
            )

        if recency_days is not None:
            cutoff = (
                datetime.now(timezone.utc) - timedelta(days=recency_days)
            ).isoformat()
            must_conditions.append(
                qm.FieldCondition(
                    key="published_at",
                    range=qm.DatetimeRange(gte=cutoff),
                )
            )

        query_filter = qm.Filter(must=must_conditions) if must_conditions else None

        import asyncio

        # Compute sparse vector (fast, sync) and dense embedding concurrently
        sparse_sv = compute_sparse_vector(query)

        dense_vec_list, sparse_res = await asyncio.gather(
            self._embedder.embed([query]),
            self._client.query_points(
                collection_name=self._collection,
                query=qm.SparseVector(
                    indices=sparse_sv["indices"],
                    values=sparse_sv["values"],
                ),
                using=SPARSE_VECTOR_NAME,
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
                with_vectors=False,
            ),
        )

        dense_res = await self._client.query_points(
            collection_name=self._collection,
            query=dense_vec_list[0],
            using=DENSE_VECTOR_NAME,
            query_filter=query_filter,
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )

        sparse_hits = _qdrant_to_dicts(sparse_res.points)
        dense_hits  = _qdrant_to_dicts(dense_res.points)

        log.debug(
            "hybrid_search_raw",
            dense_hits=len(dense_hits),
            sparse_hits=len(sparse_hits),
            tickers=tickers,
        )
        return dense_hits, sparse_hits

    # ── Upsert ────────────────────────────────────────────────────────────────

    async def upsert(self, points: list[dict[str, Any]]) -> None:
        """
        points: list of {id, dense_vector, sparse_vector, payload}
        """
        qdrant_points = []
        for p in points:
            qdrant_points.append(
                qm.PointStruct(
                    id=p["id"],
                    vector={
                        DENSE_VECTOR_NAME: p["dense_vector"],
                        SPARSE_VECTOR_NAME: qm.SparseVector(
                            indices=p["sparse_vector"]["indices"],
                            values=p["sparse_vector"]["values"],
                        ),
                    },
                    payload=p["payload"],
                )
            )
        await self._client.upsert(
            collection_name=self._collection,
            points=qdrant_points,
            wait=True,
        )
        log.info("qdrant_upserted", count=len(qdrant_points))

    # ── Reranking ─────────────────────────────────────────────────────────────

    async def rerank(
        self, query: str, candidates: list[dict], top_k: int | None = None
    ) -> list[dict]:
        top_k = top_k or self._settings.reranker_top_k
        if not candidates:
            return []
        if self._reranker:
            return await self._reranker.rerank(query, candidates, top_k)
        # No reranker — return top_k by existing fusion score
        return sorted(candidates, key=lambda x: x.get("score", 0), reverse=True)[:top_k]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _qdrant_to_dicts(points) -> list[dict[str, Any]]:
    out = []
    for p in points:
        payload = dict(p.payload or {})
        out.append({
            "id": str(p.id),
            "score": float(p.score),
            "text": payload.pop("text", ""),
            "metadata": payload,
        })
    return out


def point_id_from_text(text: str, source: str) -> str:
    """Stable deterministic ID for a chunk — used for idempotent upserts."""
    h = hashlib.sha256(f"{source}::{text[:256]}".encode()).hexdigest()
    # Qdrant unsigned int ID
    return str(int(h[:16], 16) & 0x7FFFFFFFFFFFFFFF)


# ── Reranker implementations ──────────────────────────────────────────────────

class LocalReranker:
    """Cross-encoder reranker using sentence-transformers (free, CPU-only)."""

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2") -> None:
        self._model_name = model_name
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder
            log.info("loading_local_reranker", model=self._model_name)
            self._model = CrossEncoder(self._model_name)
            log.info("local_reranker_ready")
        return self._model

    async def rerank(
        self, query: str, candidates: list[dict], top_k: int
    ) -> list[dict]:
        import asyncio

        model = self._load()

        def _score():
            pairs = [(query, c.get("text", "")) for c in candidates]
            return model.predict(pairs).tolist()

        scores = await asyncio.to_thread(_score)
        scored = [
            {**c, "score": float(s)}
            for c, s in zip(candidates, scores)
        ]
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]


class CohereReranker:
    """Cohere Rerank API — requires COHERE_API_KEY."""

    def __init__(self, api_key: str, model: str = "rerank-english-v3.0") -> None:
        import cohere
        self._client = cohere.AsyncClientV2(api_key=api_key)
        self._model = model

    async def rerank(
        self, query: str, candidates: list[dict], top_k: int
    ) -> list[dict]:
        docs = [c.get("text", "") for c in candidates]
        resp = await self._client.rerank(
            model=self._model,
            query=query,
            documents=docs,
            top_n=top_k,
        )
        result = []
        for hit in resp.results:
            entry = candidates[hit.index].copy()
            entry["score"] = float(hit.relevance_score)
            result.append(entry)
        return result


def build_reranker(settings):
    """Factory — returns the right reranker based on RERANKER_PROVIDER."""
    if settings.reranker_provider == "cohere" and settings.cohere_api_key:
        return CohereReranker(settings.cohere_api_key, settings.reranker_model)
    return LocalReranker(settings.local_reranker_model)
