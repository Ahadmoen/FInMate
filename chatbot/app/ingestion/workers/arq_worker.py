"""Arq worker settings.

Run with: python -m arq app.ingestion.workers.arq_worker.WorkerSettings
"""
from __future__ import annotations

import asyncpg
from arq import cron
from arq.connections import RedisSettings

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.ingestion.workers.news import ingest_news_from_supabase

log = get_logger(__name__)


async def task_ingest_news(ctx: dict) -> str:
    structured = ctx.get("structured_store")
    vector = ctx.get("vector_store")
    embedder = ctx.get("embedder")
    n = await ingest_news_from_supabase(
        structured_store=structured,
        vector_store=vector,
        embedder=embedder,
    )
    return f"ingested {n} news chunks"


async def startup(ctx: dict) -> None:
    settings = get_settings()
    configure_logging(settings.debug)
    log.info("arq_worker_starting")

    from qdrant_client import AsyncQdrantClient
    from app.ingestion.embeddings import EmbeddingClient
    from app.retrieval.vector import VectorStore
    from app.retrieval.structured import StructuredStore

    qdrant = AsyncQdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
    )
    embedder = EmbeddingClient(settings)
    vs = VectorStore(qdrant, embedder, settings)
    await vs.ensure_collection()

    if settings.use_asyncpg:
        pool = await asyncpg.create_pool(settings.supabase_db_url, min_size=1, max_size=5)
        ss = StructuredStore(settings, pool=pool)
    else:
        from supabase import acreate_client
        sb = await acreate_client(settings.supabase_url, settings.supabase_key)
        ss = StructuredStore(settings, supabase=sb)

    ctx["qdrant"] = qdrant
    ctx["structured_store"] = ss
    ctx["vector_store"] = vs
    ctx["embedder"] = embedder
    if settings.use_asyncpg:
        ctx["db_pool"] = pool


async def shutdown(ctx: dict) -> None:
    if "qdrant" in ctx:
        await ctx["qdrant"].close()
    if "db_pool" in ctx:
        await ctx["db_pool"].close()
    log.info("arq_worker_stopped")


class WorkerSettings:
    functions = [task_ingest_news]
    cron_jobs = [
        cron(task_ingest_news, hour={0, 6, 12, 18}, minute=15)  # 4× daily
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(
        __import__("os").getenv("REDIS_URL", "redis://localhost:6379")
    )
    max_jobs = 4
    job_timeout = 600
