"""Stateful chat endpoints — session management + RAG pipeline.

Replaces the Django BE middleman so the frontend talks directly here.

POST /v1/chat/ask                    — send a message, get an answer
GET  /v1/chat/sessions               — list the authenticated user's sessions
GET  /v1/chat/sessions/{session_id}  — full message history for one session

Auth: Supabase JWT via Authorization: Bearer <token>
      The token comes from supabase.auth.getSession() on the frontend.
      The sub claim is used as user_id throughout.

Flow for /ask:
  1. Verify JWT → user_id
  2. get_or_create ChatSession
  3. Load last 10 messages as history
  4. Persist the user message
  5. Run the RAG pipeline (_handle_query from query.py)
  6. Persist the assistant message with citations and insight_card (if any)
  7. Touch session.last_active
  8. Return answer + session_id + insight_card
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.config import get_settings
from app.core.deps import get_current_user_id
from app.core.logging import get_logger
from app.generation.llm import LLMClient
from app.generation.schemas import (
    ChatAskRequest,
    ChatAskResponse,
    ChatMessageOut,
    ChatSessionDetailOut,
    ChatSessionOut,
    QueryRequest,
    StockInsightCard,
)
from app.retrieval.chat_store import ChatStore, truncate_session_title
from app.retrieval.router import QueryRouter
from app.retrieval.structured import StructuredStore

log = get_logger(__name__)
router = APIRouter()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _build_chat_store(request: Request) -> ChatStore:
    pool = getattr(request.app.state, "db_pool", None)
    sb   = getattr(request.app.state, "supabase", None)
    return ChatStore(pool=pool, supabase=sb)


def _build_structured(request: Request) -> StructuredStore:
    settings = get_settings()
    pool = getattr(request.app.state, "db_pool", None)
    sb   = getattr(request.app.state, "supabase", None)
    return StructuredStore(settings, pool=pool, supabase=sb)


# ── POST /v1/chat/ask ─────────────────────────────────────────────────────────

@router.post("/ask", response_model=ChatAskResponse)
async def ask(
    body: ChatAskRequest,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """Send a message and receive a grounded AI answer.

    Persists both the user message and the assistant reply to the
    chat_message table so history survives across requests.
    """
    settings   = get_settings()
    chat_store = _build_chat_store(request)
    structured = _build_structured(request)
    llm        = getattr(request.app.state, "llm", None) or LLMClient(settings)
    qrouter    = QueryRouter(llm, settings)
    vector     = getattr(request.app.state, "vector_store", None)
    embedder   = getattr(request.app.state, "embedder", None)
    cache      = getattr(request.app.state, "cache", None)
    sectors    = getattr(request.app.state, "sectors", None)

    # 1. Resolve session
    try:
        session = await chat_store.get_or_create_session(
            user_id,
            body.session_id,
            title=truncate_session_title(body.message),
        )
    except Exception as exc:
        log.error("session_error", user_id=user_id, error=str(exc))
        raise HTTPException(status_code=502, detail="Failed to resolve chat session.")

    session_id = session["id"]

    # 2. Load history (last 10 messages, chronological, lowercased roles)
    try:
        history = await chat_store.get_history(session_id, limit=10)
    except Exception as exc:
        log.warning("history_load_failed", session_id=session_id, error=str(exc))
        history = []

    # 3. Persist user message
    try:
        await chat_store.save_message(session_id, "USER", body.message)
    except Exception as exc:
        log.error("save_user_message_failed", session_id=session_id, error=str(exc))

    # 4. Run the RAG pipeline (reuse _handle_query from query.py)
    from app.api.v1.query import _handle_query

    rag_request = QueryRequest(
        query=body.message,
        user_name="User",
        user_id=user_id,
        stream=False,
        history=history,
    )

    try:
        rag_result = await _handle_query(
            rag_request, structured, llm, qrouter, vector, embedder, cache, settings,
            sectors=sectors,
        )
    except Exception as exc:
        log.error("rag_pipeline_error", session_id=session_id, error=str(exc))
        raise HTTPException(status_code=502, detail="AI service error. Please try again.")

    # Extract fields from the RAG response (all response types have .answer)
    if hasattr(rag_result, "model_dump"):
        result_dict = rag_result.model_dump()
    else:
        result_dict = dict(rag_result)

    answer      = result_dict.get("answer", "")
    citations   = result_dict.get("citations", [])
    insight_card_data = result_dict.get("insight_card")
    insight_card = StockInsightCard(**insight_card_data) if insight_card_data else None

    # 5. Persist assistant message with citations and insight card (when present)
    try:
        await chat_store.save_message(
            session_id, "ASSISTANT", answer,
            sources_used=[
                c if isinstance(c, dict) else c.model_dump()
                for c in (citations or [])
            ],
            insight_card=insight_card.model_dump() if insight_card else None,
        )
    except Exception as exc:
        log.error("save_assistant_message_failed", session_id=session_id, error=str(exc))

    # 6. Update session last_active
    try:
        await chat_store.touch_session(session_id)
    except Exception as exc:
        log.warning("touch_session_failed", session_id=session_id, error=str(exc))

    log.info("chat_ask_handled", session_id=session_id, user_id=user_id)

    return ChatAskResponse(
        answer=answer,
        session_id=session_id,
        insight_card=insight_card,
        citations=citations,
    )


# ── GET /v1/chat/sessions ─────────────────────────────────────────────────────

@router.get("/sessions", response_model=list[ChatSessionOut])
async def list_sessions(
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """Return all chat sessions for the authenticated user, most recent first."""
    chat_store = _build_chat_store(request)
    try:
        rows = await chat_store.list_sessions(user_id)
    except Exception as exc:
        log.error("list_sessions_failed", user_id=user_id, error=str(exc))
        raise HTTPException(status_code=502, detail="Failed to fetch sessions.")

    return [ChatSessionOut(**r) for r in rows]


# ── GET /v1/chat/sessions/{session_id} ───────────────────────────────────────

@router.get("/sessions/{session_id}", response_model=ChatSessionDetailOut)
async def get_session(
    session_id: str,
    request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """Return a session with its full message history.

    Returns 404 if the session doesn't exist or belongs to a different user.
    """
    chat_store = _build_chat_store(request)

    try:
        session = await chat_store.get_session(session_id, user_id)
    except Exception as exc:
        log.error("get_session_failed", session_id=session_id, error=str(exc))
        raise HTTPException(status_code=502, detail="Failed to fetch session.")

    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    try:
        messages = await chat_store.get_messages(session_id)
    except Exception as exc:
        log.error("get_messages_failed", session_id=session_id, error=str(exc))
        messages = []

    return ChatSessionDetailOut(
        **session,
        messages=[ChatMessageOut(**m) for m in messages],
    )
