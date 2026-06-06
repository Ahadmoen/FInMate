"""Unit tests for semantic chunking."""
import pytest
from app.ingestion.chunking import chunk_document, _sentence_boundary_split, _section_aware_split


def test_basic_news_chunking():
    text = "PSO reported strong Q3 results. Revenue grew 15% year-over-year. " * 20
    chunks = chunk_document(text, ticker="PSO", doc_type="news", source="test.com")
    assert len(chunks) >= 1
    for c in chunks:
        assert c.metadata["ticker"] == "PSO"
        assert c.metadata["doc_type"] == "news"
        assert c.metadata["embedding_model"] == "text-embedding-3-large"
        assert "doc_id" in c.metadata


def test_metadata_payload_complete():
    chunks = chunk_document(
        "OGDC announced new oil discovery in Sindh. " * 10,
        ticker="OGDC",
        doc_type="news",
        source="dawn.com",
        published_at="2026-05-10T09:00:00Z",
    )
    meta = chunks[0].metadata
    assert meta["ticker"] == "OGDC"
    assert meta["published_at"] == "2026-05-10T09:00:00Z"
    assert meta["source"] == "dawn.com"
    assert meta["language"] == "en"


def test_section_aware_filing_chunking():
    text = """
DIRECTORS' REPORT
The board is pleased to present results for FY2025.

RISK FACTORS
Key risks include commodity price volatility and currency depreciation.

MD&A
Revenue increased by 18% driven by higher oil prices.
""" * 3
    chunks = chunk_document(text, ticker="PSO", doc_type="filing", source="secp.gov.pk")
    sections = {c.metadata.get("section", "") for c in chunks}
    # At least one section header should be captured
    assert any(s for s in sections)


def test_chunk_idempotency():
    text = "PSO quarterly report. " * 30
    chunks1 = chunk_document(text, ticker="PSO", doc_type="news", source="test")
    chunks2 = chunk_document(text, ticker="PSO", doc_type="news", source="test")
    ids1 = [c.metadata["doc_id"] for c in chunks1]
    ids2 = [c.metadata["doc_id"] for c in chunks2]
    assert ids1 == ids2


def test_empty_text_returns_empty():
    chunks = chunk_document("", ticker="PSO", doc_type="news", source="test")
    assert chunks == []


def test_short_text_single_chunk():
    text = "PSO is Pakistan's largest oil marketing company."
    chunks = chunk_document(text, ticker="PSO", doc_type="news", source="test")
    assert len(chunks) == 1
    assert chunks[0].text == text
