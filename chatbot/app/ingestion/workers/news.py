"""News ingestion worker.

Reads from the existing Supabase news_sentiment table and upserts
chunks into Qdrant with full metadata payload.

Idempotency: each chunk gets a deterministic ID from
sha256(ticker + source + text[:256]) so re-runs are safe.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import asyncpg
from qdrant_client import AsyncQdrantClient
from supabase._async.client import AsyncClient

from app.core.config import get_settings
from app.core.logging import get_logger
from app.ingestion.chunking import chunk_document
from app.ingestion.embeddings import EmbeddingClient, compute_sparse_vector
from app.retrieval.vector import VectorStore, point_id_from_text

log = get_logger(__name__)


async def ingest_news_from_supabase(
    structured_store=None,
    vector_store: VectorStore | None = None,
    embedder: EmbeddingClient | None = None,
    after: str | None = None,
    batch_size: int = 100,
) -> int:
    """
    Pull news_sentiment rows from Supabase and upsert into Qdrant.
    Returns number of chunks ingested.

    Can be called standalone (bootstrapping) or from an Arq worker task.
    When called standalone it builds its own clients from settings.
    """
    settings = get_settings()
    own_clients = vector_store is None

    if own_clients:
        qdrant_client = AsyncQdrantClient(
            url=settings.qdrant_url,
            api_key=settings.qdrant_api_key or None,
        )
        embedder = EmbeddingClient(settings)
        vector_store = VectorStore(qdrant_client, embedder, settings)
        await vector_store.ensure_collection()

        if settings.use_asyncpg:
            pool = await asyncpg.create_pool(settings.supabase_db_url, min_size=1, max_size=3)
            from app.retrieval.structured import StructuredStore
            structured_store = StructuredStore(settings, pool=pool)
        else:
            from supabase import acreate_client
            sb = await acreate_client(settings.supabase_url, settings.supabase_key)
            from app.retrieval.structured import StructuredStore
            structured_store = StructuredStore(settings, supabase=sb)

    rows = await structured_store.get_unindexed_news(after=after, limit=batch_size)
    if not rows:
        log.info("news_ingest_nothing_to_do")
        return 0

    all_chunks = []
    for row in rows:
        ticker = row.get("ticker", "UNKNOWN")
        headline = row.get("headline", "")
        sentiment = row.get("sentiment", "")
        source = row.get("source", "")
        published_at = str(row.get("published_at", ""))
        score = row.get("score")

        # Compose a richer text for embedding
        full_text = (
            f"Headline: {headline}\n"
            f"Sentiment: {sentiment} (score: {score})\n"
            f"Source: {source}"
        )

        chunks = chunk_document(
            text=full_text,
            ticker=ticker,
            doc_type="news",
            source=source,
            published_at=published_at,
            embedding_model=settings.embedding_model,
        )
        all_chunks.extend(chunks)

    if not all_chunks:
        return 0

    # Batch embed
    texts = [c.text for c in all_chunks]
    dense_vectors = await embedder.embed(texts)

    points = []
    for chunk, dense_vec in zip(all_chunks, dense_vectors):
        sparse = compute_sparse_vector(chunk.text)
        pid = int(chunk.metadata["doc_id"][:15], 16) & 0x7FFFFFFFFFFFFFFF
        payload = {**chunk.metadata, "text": chunk.text}
        points.append({
            "id": pid,
            "dense_vector": dense_vec,
            "sparse_vector": sparse,
            "payload": payload,
        })

    await vector_store.upsert(points)
    log.info("news_ingested", chunks=len(points), rows=len(rows))

    if own_clients:
        await qdrant_client.close()
        if settings.use_asyncpg:
            await pool.close()

    return len(points)


# ── Manual text ingestion (used by /ingest/ endpoint) ────────────────────────

async def ingest_manual_text(
    text: str,
    source: str,
    metadata: dict[str, Any],
    vector_store: VectorStore,
    embedder: EmbeddingClient,
    settings,
) -> int:
    ticker = metadata.get("ticker", "MANUAL")
    doc_type = metadata.get("doc_type", "manual")
    published_at = metadata.get("published_at") or datetime.now(timezone.utc).isoformat()

    chunks = chunk_document(
        text=text,
        ticker=ticker,
        doc_type=doc_type,
        source=source,
        published_at=published_at,
        section=metadata.get("section", ""),
        embedding_model=settings.embedding_model,
    )
    if not chunks:
        return 0

    texts = [c.text for c in chunks]
    dense_vectors = await embedder.embed(texts)

    points = []
    for chunk, dense_vec in zip(chunks, dense_vectors):
        sparse = compute_sparse_vector(chunk.text)
        pid = int(chunk.metadata["doc_id"][:15], 16) & 0x7FFFFFFFFFFFFFFF
        payload = {**chunk.metadata, "text": chunk.text}
        points.append({
            "id": pid,
            "dense_vector": dense_vec,
            "sparse_vector": sparse,
            "payload": payload,
        })

    await vector_store.upsert(points)
    return len(points)
