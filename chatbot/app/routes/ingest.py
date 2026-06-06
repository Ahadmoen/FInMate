from fastapi import APIRouter, HTTPException
from app.models.schemas import IngestRequest, IngestResponse
from app.services.rag_service import ingest_text
from app.services.vector_store import get_collection_count
from app.utils.logger import logger

router = APIRouter()

@router.post("/", response_model=IngestResponse)
async def ingest(request: IngestRequest):
    """
    Ingest documents into the vector database.
    
    Use this endpoint to add knowledge to AIVA:
    - Company profiles
    - Financial reports
    - Market analysis
    - Any text data
    
    Accepts:
    - text: The document text to ingest
    - source: Source name (e.g. 'company_profile')
    - metadata: Extra info like ticker, sector etc.
    
    Returns:
    - success: True/False
    - message: Status message
    - chunks_added: Number of chunks added
    """
    try:
        logger.info(f"Ingesting document from source: {request.source}")

        if not request.text or len(request.text.strip()) == 0:
            raise HTTPException(
                status_code=400,
                detail="Text cannot be empty"
            )

        if len(request.text) < 10:
            raise HTTPException(
                status_code=400,
                detail="Text is too short. Please provide meaningful content."
            )

        # Ingest into vector store
        success, chunks_added = await ingest_text(
            text=request.text,
            source=request.source,
            metadata=request.metadata
        )

        if success:
            total_docs = get_collection_count()
            return IngestResponse(
                success=True,
                message=f"Successfully added {chunks_added} chunks to AIVA knowledge base. Total documents: {total_docs}",
                chunks_added=chunks_added
            )
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to ingest document"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ingest error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Ingest error: {str(e)}"
        )


@router.get("/stats")
async def stats():
    """Get vector database statistics."""
    total = get_collection_count()
    return {
        "total_documents": total,
        "status": "healthy",
        "message": f"AIVA knowledge base has {total} document chunks"
    }