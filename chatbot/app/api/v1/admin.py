from fastapi import APIRouter, BackgroundTasks, Depends, Request

from app.core.deps import require_admin
from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.ingestion.workers.news import ingest_news_from_supabase
from app.retrieval.structured import StructuredStore

log = get_logger(__name__)
router = APIRouter()


@router.post("/reindex", dependencies=[Depends(require_admin)])
async def reindex(
    background_tasks: BackgroundTasks,
    request: Request,
    settings: Settings = Depends(get_settings),
):
    """Trigger a full re-ingestion of news_sentiment into Qdrant.
    Runs in the background; returns immediately.
    Idempotent — existing vectors with the same doc_id are overwritten.
    """
    pool    = getattr(request.app.state, "db_pool", None)
    sb      = getattr(request.app.state, "supabase", None)
    vector  = getattr(request.app.state, "vector_store", None)
    embedder = getattr(request.app.state, "embedder", None)
    structured = StructuredStore(settings, pool=pool, supabase=sb)

    async def _run():
        n = await ingest_news_from_supabase(
            structured_store=structured,
            vector_store=vector,
            embedder=embedder,
        )
        log.info("reindex_complete", chunks=n)

    background_tasks.add_task(_run)
    return {"status": "reindex_started", "note": "Check logs for progress"}
