from fastapi import APIRouter, Request

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.generation.schemas import FreshnessEntry, HealthFreshnessResponse
from app.ingestion.workers.market import check_freshness
from app.retrieval.structured import StructuredStore
from fastapi import Depends

log = get_logger(__name__)
router = APIRouter()


@router.get("/freshness", response_model=HealthFreshnessResponse)
async def health_freshness(
    request: Request,
    settings: Settings = Depends(get_settings),
):
    pool = getattr(request.app.state, "db_pool", None)
    sb   = getattr(request.app.state, "supabase", None)
    structured = StructuredStore(settings, pool=pool, supabase=sb)
    vector = getattr(request.app.state, "vector_store", None)
    cache  = getattr(request.app.state, "cache", None)

    freshness_rows = await check_freshness(structured)
    entries = [FreshnessEntry(**r) for r in freshness_rows]

    qdrant_count = 0
    if vector:
        try:
            qdrant_count = await vector.collection_count()
        except Exception:
            pass

    redis_ok = False
    if cache:
        try:
            redis_ok = await cache.ping()
        except Exception:
            pass

    stale = sum(1 for e in entries if e.is_stale)
    status = "degraded" if stale > 0 else "healthy"

    return HealthFreshnessResponse(
        status=status,
        entries=entries,
        qdrant_vectors=qdrant_count,
        redis_connected=redis_ok,
    )
