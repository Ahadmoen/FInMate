"""Retrieval fusion utilities.

Reciprocal Rank Fusion (RRF) merges dense and sparse ranked lists.
Recency boosting applies an exponential decay to news-type scores.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any


# ── Reciprocal Rank Fusion ────────────────────────────────────────────────────

def reciprocal_rank_fusion(
    *ranked_lists: list[dict[str, Any]],
    k: int = 60,
) -> list[dict[str, Any]]:
    """
    Fuse multiple ranked lists via RRF.

    Each list item must have an "id" key. The merged list is scored and
    sorted descending. Original scores are preserved on the winning entry
    under the "dense_score" / "sparse_score" keys.
    """
    scores: dict[str, float] = {}
    merged: dict[str, dict] = {}

    for ranked in ranked_lists:
        for rank, doc in enumerate(ranked, start=1):
            doc_id = doc["id"]
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (k + rank)
            if doc_id not in merged:
                merged[doc_id] = doc.copy()

    result = []
    for doc_id, rrf_score in scores.items():
        entry = merged[doc_id].copy()
        entry["rrf_score"] = rrf_score
        entry["score"] = rrf_score          # unified score field for downstream
        result.append(entry)

    result.sort(key=lambda x: x["rrf_score"], reverse=True)
    return result


# ── Recency boosting ──────────────────────────────────────────────────────────

def apply_recency_boost(
    docs: list[dict[str, Any]],
    half_life_days: float,
    timestamp_field: str = "published_at",
) -> list[dict[str, Any]]:
    """
    Multiply each document's score by exp(-age_days / half_life_days).

    Documents without a parseable timestamp are not penalised (multiplier = 1.0).
    """
    now = datetime.now(timezone.utc)
    boosted = []
    for doc in docs:
        meta = doc.get("metadata", {})
        ts_raw = meta.get(timestamp_field)
        multiplier = 1.0
        if ts_raw:
            try:
                ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                age_days = (now - ts).total_seconds() / 86400
                multiplier = math.exp(-age_days / half_life_days)
            except (ValueError, TypeError):
                pass
        entry = doc.copy()
        entry["score"] = doc.get("score", 0.0) * multiplier
        entry["recency_multiplier"] = multiplier
        boosted.append(entry)
    boosted.sort(key=lambda x: x["score"], reverse=True)
    return boosted


# ── Convenience: full retrieval pipeline ─────────────────────────────────────

def fuse_and_boost(
    dense_hits: list[dict],
    sparse_hits: list[dict],
    half_life_days: float | None = None,
    rrf_k: int = 60,
) -> list[dict]:
    fused = reciprocal_rank_fusion(dense_hits, sparse_hits, k=rrf_k)
    if half_life_days:
        fused = apply_recency_boost(fused, half_life_days)
    return fused
