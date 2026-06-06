"""Unit tests for retrieval fusion: RRF and recency boosting."""
import math
import pytest
from datetime import datetime, timedelta, timezone

from app.retrieval.fusion import (
    apply_recency_boost,
    fuse_and_boost,
    reciprocal_rank_fusion,
)


def _doc(id: str, score: float = 1.0, age_days: int = 0) -> dict:
    published = (
        (datetime.now(timezone.utc) - timedelta(days=age_days)).isoformat()
    )
    return {
        "id": id,
        "score": score,
        "text": f"doc {id}",
        "metadata": {"published_at": published},
    }


def test_rrf_merges_two_lists():
    dense  = [_doc("A"), _doc("B"), _doc("C")]
    sparse = [_doc("B"), _doc("A"), _doc("D")]
    result = reciprocal_rank_fusion(dense, sparse)
    ids = [r["id"] for r in result]
    # A and B appear in both lists → should rank above C and D
    assert ids.index("A") < ids.index("D")
    assert ids.index("B") < ids.index("D")


def test_rrf_deduplicates():
    dense  = [_doc("A"), _doc("B")]
    sparse = [_doc("A"), _doc("C")]
    result = reciprocal_rank_fusion(dense, sparse)
    ids = [r["id"] for r in result]
    assert ids.count("A") == 1


def test_rrf_empty_lists():
    result = reciprocal_rank_fusion([], [])
    assert result == []


def test_rrf_single_list():
    docs = [_doc("X"), _doc("Y")]
    result = reciprocal_rank_fusion(docs)
    assert [r["id"] for r in result] == ["X", "Y"]


def test_recency_boost_reduces_old_docs():
    fresh = _doc("new", age_days=0)
    old   = _doc("old", age_days=60)
    both  = [fresh, old]
    boosted = apply_recency_boost(both, half_life_days=14)
    ids = [b["id"] for b in boosted]
    assert ids[0] == "new"   # fresh doc should rank higher


def test_recency_boost_half_life_math():
    """After half_life_days days, multiplier should be exp(-1) ≈ 0.368."""
    doc = _doc("x", score=1.0, age_days=14)
    result = apply_recency_boost([doc], half_life_days=14)
    expected_mult = math.exp(-1.0)
    assert abs(result[0]["recency_multiplier"] - expected_mult) < 0.01


def test_recency_boost_missing_timestamp():
    """Docs without timestamp should not be penalised (multiplier=1.0)."""
    doc = {"id": "x", "score": 1.0, "text": "x", "metadata": {}}
    result = apply_recency_boost([doc], half_life_days=14)
    assert result[0]["recency_multiplier"] == 1.0


def test_fuse_and_boost_pipeline():
    dense  = [_doc("A", age_days=1), _doc("B", age_days=30)]
    sparse = [_doc("B", age_days=30), _doc("A", age_days=1)]
    result = fuse_and_boost(dense, sparse, half_life_days=14)
    assert len(result) == 2
    # A (newer) should score higher than B (older) after recency boosting
    ids = [r["id"] for r in result]
    assert ids[0] == "A"
