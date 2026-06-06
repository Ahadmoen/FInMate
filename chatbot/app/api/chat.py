"""Backward-compatible /chat/ endpoint.

Wraps the new RAG pipeline and maps its output to the original
LegacyChatResponse schema so existing frontends continue to work.
"""
from __future__ import annotations

import uuid
from fastapi import APIRouter, HTTPException, Request, Depends

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.generation.llm import LLMClient
from app.generation.schemas import (
    LegacyChatRequest, LegacyChatResponse, LegacyStockCard,
    QueryIntent, QueryRequest,
)
from app.retrieval.router import QueryRouter
from app.retrieval.structured import StructuredStore
from app.api.v1.query import _handle_query, _row_to_snapshot

log = get_logger(__name__)
router = APIRouter()


@router.post("/", response_model=LegacyChatResponse)
async def chat(body: LegacyChatRequest, request: Request, settings: Settings = Depends(get_settings)):
    try:
        pool = getattr(request.app.state, "db_pool", None)
        sb   = getattr(request.app.state, "supabase", None)
        structured = StructuredStore(settings, pool=pool, supabase=sb)
        llm = LLMClient(settings)
        qrouter = QueryRouter(llm, settings)
        vector   = getattr(request.app.state, "vector_store", None)
        embedder = getattr(request.app.state, "embedder", None)
        cache    = getattr(request.app.state, "cache", None)

        qreq = QueryRequest(query=body.message, user_name=body.user_name, user_id=body.user_id)
        result = await _handle_query(qreq, structured, llm, qrouter, vector, embedder, cache, settings)

        # Build stock card from first ticker if present
        card = None
        route = await qrouter.route(body.message)
        if route.filters.tickers:
            ticker = route.filters.tickers[0]
            row = await structured.get_latest_price(ticker)
            sig = await structured.get_signal(ticker)
            fore = await structured.get_forecast(ticker)
            if row:
                snap = _row_to_snapshot(row, settings)
                card = LegacyStockCard(data={
                    "company_name": snap.company_name,
                    "symbol": ticker,
                    "open_price": snap.open_price,
                    "close_price": snap.close_price,
                    "high": snap.high,
                    "low": snap.low,
                    "volume": snap.volume,
                    "change_pct": snap.change_pct,
                    "signal": sig.get("signal") if sig else None,
                    "signal_confidence": round(sig.get("confidence", 0) * 100, 1) if sig else None,
                    "forecast_direction": fore.get("direction") if fore else None,
                    "predicted_price": fore.get("predicted_price") if fore else None,
                })

        # Extract answer text
        answer = getattr(result, "answer", None)
        if answer is None:
            # PRICE_LOOKUP / FUNDAMENTALS return structured data — format it
            answer = result.model_dump_json(indent=2)

        # Build sources from citations
        sources = [c.model_dump() for c in (result.citations or [])]

        return LegacyChatResponse(
            answer=answer,
            card=card,
            sources=sources,
            query_type=result.intent.value.lower(),
            trace_id=result.trace_id,
        )
    except Exception as exc:
        log.error("legacy_chat_error", error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/health")
async def health():
    return {"status": "healthy", "service": "AIVA Chat"}
