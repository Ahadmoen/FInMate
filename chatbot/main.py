"""FastAPI application entry point.

Lifespan order:
  1. Configure logging
  2. Build asyncpg pool (or async Supabase client)
  3. Connect Qdrant, ensure collection exists
  4. Connect Redis
  5. Build embedding client + VectorStore + LLM, attach to app.state
  6. Warm up local ML models (embedding + reranker) so first request is fast
  7. Serve requests
  8. Cleanup on shutdown
"""
from __future__ import annotations

from contextlib import asynccontextmanager

import asyncpg
import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from qdrant_client import AsyncQdrantClient

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger

settings = get_settings()
configure_logging(settings.debug)
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────────────
    log.info("aiva_startup", app=settings.app_name)

    # Structured store
    if settings.use_asyncpg:
        pool = await asyncpg.create_pool(
            settings.supabase_db_url,
            min_size=2,
            max_size=10,
            command_timeout=30,
            statement_cache_size=0,
        )
        app.state.db_pool = pool
        app.state.supabase = None
        log.info("asyncpg_pool_ready")
    else:
        from supabase import acreate_client
        sb = await acreate_client(settings.supabase_url, settings.supabase_key)
        app.state.db_pool = None
        app.state.supabase = sb
        log.info("supabase_async_client_ready")

    # Qdrant
    qdrant = AsyncQdrantClient(
        url=settings.qdrant_url,
        api_key=settings.qdrant_api_key or None,
    )
    app.state.qdrant = qdrant

    # Redis
    redis_client = aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=False,
        max_connections=20,
    )
    app.state.redis = redis_client

    # Embedding + VectorStore + Cache + LLM
    from app.cache.redis_cache import RedisCache
    from app.generation.llm import LLMClient
    from app.ingestion.embeddings import EmbeddingClient
    from app.retrieval.vector import VectorStore, build_reranker

    cache    = RedisCache(redis_client, settings)
    embedder = EmbeddingClient(settings, cache=cache)
    reranker = build_reranker(settings)
    vs       = VectorStore(qdrant, embedder, settings, reranker=reranker)
    llm      = LLMClient(settings)

    await vs.ensure_collection()

    app.state.cache        = cache
    app.state.embedder     = embedder
    app.state.vector_store = vs
    app.state.llm          = llm

    # ── Load distinct sectors from stock_symbol for router prompt ─────────────
    try:
        from app.retrieval.structured import StructuredStore as _SS
        _store = _SS(settings, pool=app.state.db_pool, supabase=app.state.supabase)
        app.state.sectors = await _store.get_distinct_sectors()
        log.info("sectors_loaded", count=len(app.state.sectors))
    except Exception as _exc:
        app.state.sectors = []
        log.warning("sectors_load_failed", error=str(_exc))

    # ── Warmup: load local ML models now so first request never times out ─────
    import asyncio as _asyncio
    if settings.embedding_provider == "local":
        log.info("warming_up_embedding_model")
        await embedder.embed(["warmup"])
        log.info("embedding_model_ready")

    if settings.reranker_provider == "local":
        from app.retrieval.vector import LocalReranker
        if isinstance(reranker, LocalReranker):
            log.info("warming_up_reranker")
            await _asyncio.to_thread(reranker._load)
            log.info("reranker_ready")

    log.info("aiva_ready")

    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    log.info("aiva_shutdown")
    if settings.use_asyncpg and getattr(app.state, "db_pool", None):
        await app.state.db_pool.close()
    await qdrant.close()
    await redis_client.aclose()
    log.info("aiva_stopped")


app = FastAPI(
    title="AIVA FinMate",
    version="2.0.0",
    description="Production-grade RAG system for Pakistan Stock Exchange (PSX) financial data.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ────────────────────────────────────────────────────────────────────

from app.api.v1.query     import router as v1_query_router
from app.api.v1.tickers   import router as v1_tickers_router
from app.api.v1.health    import router as v1_health_router
from app.api.v1.admin     import router as v1_admin_router
from app.api.v1.portfolio import router as v1_portfolio_router
from app.api.v1.chat      import router as v1_chat_router
from app.api.chat         import router as legacy_chat_router
from app.api.ingest       import router as legacy_ingest_router

app.include_router(v1_query_router,      prefix="/v1",            tags=["v1 query"])
app.include_router(v1_tickers_router,    prefix="/v1/tickers",    tags=["v1 tickers"])
app.include_router(v1_health_router,     prefix="/v1/health",     tags=["v1 health"])
app.include_router(v1_admin_router,      prefix="/v1/admin",      tags=["v1 admin"])
app.include_router(v1_portfolio_router,  prefix="/v1/portfolio",  tags=["v1 portfolio"])
app.include_router(v1_chat_router,       prefix="/v1/chat",       tags=["v1 chat"])
app.include_router(legacy_chat_router,   prefix="/chat",          tags=["legacy"])
app.include_router(legacy_ingest_router, prefix="/ingest",        tags=["legacy"])


@app.get("/", tags=["health"])
async def root():
    return {"service": settings.app_name, "version": "2.0.0", "status": "ok"}
