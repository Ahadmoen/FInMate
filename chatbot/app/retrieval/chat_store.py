"""Chat session and message persistence.

Mirrors the Django BE's ChatSession + ChatMessage models.
Table names: chat_session, chat_message  (created by Django migrations).

Primary path: asyncpg (SUPABASE_DB_URL set).
Fallback:     Supabase REST client.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import asyncpg
from supabase._async.client import AsyncClient

from app.core.logging import get_logger

log = get_logger(__name__)

_ROLE_USER      = "USER"
_ROLE_ASSISTANT = "ASSISTANT"
_TITLE_MAX_LEN  = 60


def truncate_session_title(message: str, max_len: int = _TITLE_MAX_LEN) -> str:
    """Derive a sidebar title from the first user message."""
    text = " ".join(message.split())
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


class ChatStore:
    def __init__(
        self,
        pool: asyncpg.Pool | None = None,
        supabase: AsyncClient | None = None,
    ) -> None:
        self._pool = pool
        self._sb   = supabase

    # ── Sessions ──────────────────────────────────────────────────────────────

    async def create_session(
        self, user_id: str, title: str | None = None
    ) -> dict[str, Any]:
        """Create a new chat session for the given user and return its row."""
        now = datetime.now(timezone.utc).isoformat()
        new_id = str(uuid.uuid4())

        if self._pool:
            row = await self._pool.fetchrow(
                """
                INSERT INTO chat_session
                    (id, user_id, title, started_at, last_active, is_active, created_at, updated_at)
                VALUES ($1::uuid, $2::uuid, $3, NOW(), NOW(), TRUE, NOW(), NOW())
                RETURNING
                    id::text, user_id::text, title,
                    started_at::text, last_active::text,
                    is_active, created_at::text
                """,
                new_id, user_id, title,
            )
            return dict(row)

        payload: dict[str, Any] = {
            "id":          new_id,
            "user_id":     user_id,
            "is_active":   True,
            "started_at":  now,
            "last_active": now,
            "created_at":  now,
            "updated_at":  now,
        }
        if title is not None:
            payload["title"] = title
        resp = await self._sb.table("chat_session").insert(payload).execute()
        return resp.data[0]

    async def get_session(self, session_id: str, user_id: str) -> dict[str, Any] | None:
        """Return session only if it belongs to this user (security guard)."""
        if self._pool:
            row = await self._pool.fetchrow(
                """
                SELECT id::text, user_id::text, title,
                       started_at::text, last_active::text,
                       is_active, created_at::text
                FROM chat_session
                WHERE id = $1::uuid AND user_id = $2::uuid
                """,
                session_id, user_id,
            )
            return dict(row) if row else None

        resp = await self._sb.table("chat_session") \
            .select("id,user_id,title,started_at,last_active,is_active,created_at") \
            .eq("id", session_id) \
            .eq("user_id", user_id) \
            .limit(1) \
            .execute()
        return resp.data[0] if resp.data else None

    async def get_or_create_session(
        self, user_id: str, session_id: str | None, *, title: str | None = None
    ) -> dict[str, Any]:
        """Return existing session (verified to belong to user) or create a new one."""
        if session_id:
            session = await self.get_session(session_id, user_id)
            if session:
                return session
        return await self.create_session(user_id, title=title)

    async def touch_session(self, session_id: str) -> None:
        """Update last_active to now."""
        if self._pool:
            await self._pool.execute(
                "UPDATE chat_session SET last_active = NOW(), updated_at = NOW() WHERE id = $1::uuid",
                session_id,
            )
            return

        now = datetime.now(timezone.utc).isoformat()
        await self._sb.table("chat_session") \
            .update({"last_active": now, "updated_at": now}) \
            .eq("id", session_id) \
            .execute()

    async def list_sessions(self, user_id: str) -> list[dict[str, Any]]:
        """Return all sessions for a user, most recent first."""
        if self._pool:
            rows = await self._pool.fetch(
                """
                SELECT id::text, user_id::text, title,
                       started_at::text, last_active::text,
                       is_active, created_at::text
                FROM chat_session
                WHERE user_id = $1::uuid
                ORDER BY last_active DESC
                """,
                user_id,
            )
            return [dict(r) for r in rows]

        resp = await self._sb.table("chat_session") \
            .select("id,user_id,title,started_at,last_active,is_active,created_at") \
            .eq("user_id", user_id) \
            .order("last_active", desc=True) \
            .execute()
        return resp.data or []

    # ── Messages ──────────────────────────────────────────────────────────────

    async def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        sources_used: list | None = None,
        insight_card: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Persist a single message and return the saved row."""
        now     = datetime.now(timezone.utc).isoformat()
        new_id  = str(uuid.uuid4())
        sources = sources_used or []

        if self._pool:
            row = await self._pool.fetchrow(
                """
                INSERT INTO chat_message
                    (id, session_id, role, content, sources_used, insight_card,
                     created_at, updated_at)
                VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6::jsonb, NOW(), NOW())
                RETURNING
                    id::text, session_id::text,
                    role, content, sources_used, insight_card,
                    created_at::text
                """,
                new_id, session_id, role.upper(), content,
                json.dumps(sources),
                json.dumps(insight_card) if insight_card is not None else None,
            )
            return dict(row)

        payload: dict[str, Any] = {
            "id":           new_id,
            "session_id":   session_id,
            "role":         role.upper(),
            "content":      content,
            "sources_used": sources,
            "created_at":   now,
            "updated_at":   now,
        }
        if insight_card is not None:
            payload["insight_card"] = insight_card
        resp = await self._sb.table("chat_message").insert(payload).execute()
        return resp.data[0]

    async def get_history(
        self, session_id: str, limit: int = 10
    ) -> list[dict[str, str]]:
        """Return the last `limit` messages as {role, content} dicts for the LLM.

        Roles are lowercased ('user'/'assistant') to match the LLM API format.
        Messages are returned in chronological order (oldest first).
        """
        if self._pool:
            rows = await self._pool.fetch(
                """
                SELECT role, content
                FROM chat_message
                WHERE session_id = $1::uuid
                ORDER BY created_at DESC
                LIMIT $2
                """,
                session_id, limit,
            )
            # Reverse to chronological order
            return [
                {"role": r["role"].lower(), "content": r["content"]}
                for r in reversed(rows)
            ]

        resp = await self._sb.table("chat_message") \
            .select("role,content,created_at") \
            .eq("session_id", session_id) \
            .order("created_at", desc=True) \
            .limit(limit) \
            .execute()
        rows = list(reversed(resp.data or []))
        return [{"role": r["role"].lower(), "content": r["content"]} for r in rows]

    async def get_messages(self, session_id: str) -> list[dict[str, Any]]:
        """Return all messages for a session in chronological order (for session detail view)."""
        if self._pool:
            rows = await self._pool.fetch(
                """
                SELECT id::text, session_id::text,
                       role, content, sources_used, insight_card, created_at::text
                FROM chat_message
                WHERE session_id = $1::uuid
                ORDER BY created_at ASC
                """,
                session_id,
            )
            return [dict(r) for r in rows]

        resp = await self._sb.table("chat_message") \
            .select("id,session_id,role,content,sources_used,insight_card,created_at") \
            .eq("session_id", session_id) \
            .order("created_at") \
            .execute()
        return resp.data or []
