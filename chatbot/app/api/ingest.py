"""Backward-compatible /ingest/ endpoint."""
from fastapi import APIRouter, HTTPException, Request, Depends

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.generation.schemas import LegacyIngestRequest, LegacyIngestResponse
from app.ingestion.workers.news import ingest_manual_text

log = get_logger(__name__)
router = APIRouter()


@router.post("/", response_model=LegacyIngestResponse)
async def ingest(
    body: LegacyIngestRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
):
    vector   = getattr(request.app.state, "vector_store", None)
    embedder = getattr(request.app.state, "embedder", None)

    if not vector or not embedder:
        raise HTTPException(status_code=503, detail="Vector store not ready")

    try:
        count = await ingest_manual_text(
            text=body.text,
            source=body.source,
            metadata=body.metadata or {},
            vector_store=vector,
            embedder=embedder,
            settings=settings,
        )
        total = await vector.collection_count()
        return LegacyIngestResponse(
            success=True,
            message=f"Added {count} chunks. Total vectors: {total}",
            chunks_added=count,
        )
    except Exception as exc:
        log.error("ingest_error", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/stats")
async def stats(request: Request):
    vector = getattr(request.app.state, "vector_store", None)
    count = await vector.collection_count() if vector else 0
    return {"total_documents": count, "status": "healthy"}
