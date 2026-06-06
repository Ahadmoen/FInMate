"""Section-aware semantic chunking for PSX financial documents.

For news articles: sentence-boundary chunking at 400-600 tokens with 15% overlap.
For filings / structured reports: section-aware splitting — each section header
starts a new chunk boundary so Item 1 and MD&A content never mix.

Metadata payload (required on every chunk):
{
    "ticker": "PSO",
    "doc_type": "news | transcript | filing | analyst_report | manual",
    "published_at": "2024-03-14T13:30:00Z",
    "source": "dawn.com/...",
    "section": "...",
    "language": "en",
    "embedding_model": "text-embedding-3-large",
    "doc_id": "<sha256 hash>",
}
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

# Target token range; approximated as chars / 4
TARGET_CHARS_MIN = 1_200   # ~300 tokens
TARGET_CHARS_MAX = 2_400   # ~600 tokens
OVERLAP_RATIO    = 0.15

# PSX / SECP filing section patterns
_SECTION_RE = re.compile(
    r"^\s*(?:ITEM\s+\d[\dA-Z.]*|SECTION\s+\d|MD&A|"
    r"MANAGEMENT\s+DISCUSSION|RISK\s+FACTORS|"
    r"FINANCIAL\s+STATEMENTS|NOTES\s+TO\s+FINANCIAL|"
    r"DIRECTORS[''`]?\s+REPORT|CHAIRMAN[''`]?\s+REVIEW|"
    r"AUDITORS[''`]?\s+REPORT)",
    re.IGNORECASE | re.MULTILINE,
)

# Sentence boundary (simple; good enough for financial text)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"])")


@dataclass
class Chunk:
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


def chunk_document(
    text: str,
    ticker: str,
    doc_type: str,
    source: str,
    published_at: str | None = None,
    section: str = "",
    language: str = "en",
    embedding_model: str = "text-embedding-3-large",
) -> list[Chunk]:
    """Entry point: dispatch to the right chunking strategy."""
    text = text.strip()
    if not text:
        return []

    if doc_type in ("filing", "transcript", "analyst_report"):
        raw_chunks = _section_aware_split(text)
    else:
        raw_chunks = _sentence_boundary_split(text)

    if not published_at:
        published_at = datetime.now(timezone.utc).isoformat()

    chunks = []
    for section_name, chunk_text in raw_chunks:
        doc_id = _stable_id(ticker, source, chunk_text)
        chunks.append(Chunk(
            text=chunk_text,
            metadata={
                "ticker": ticker.upper(),
                "doc_type": doc_type,
                "published_at": published_at,
                "source": source,
                "section": section_name or section,
                "language": language,
                "embedding_model": embedding_model,
                "doc_id": doc_id,
            },
        ))
    return chunks


# ── Strategy: sentence-boundary ───────────────────────────────────────────────

def _sentence_boundary_split(text: str) -> list[tuple[str, str]]:
    sentences = _SENTENCE_END.split(text)
    chunks: list[tuple[str, str]] = []
    current: list[str] = []
    current_len = 0
    overlap_buf: list[str] = []

    for sent in sentences:
        sent_len = len(sent)
        if current_len + sent_len > TARGET_CHARS_MAX and current:
            chunk_text = " ".join(current).strip()
            chunks.append(("", chunk_text))
            # Carry over last OVERLAP_RATIO of content
            overlap_chars = int(TARGET_CHARS_MAX * OVERLAP_RATIO)
            overlap_buf = []
            consumed = 0
            for s in reversed(current):
                if consumed + len(s) <= overlap_chars:
                    overlap_buf.insert(0, s)
                    consumed += len(s)
                else:
                    break
            current = overlap_buf[:]
            current_len = sum(len(s) for s in current)
        current.append(sent)
        current_len += sent_len

    if current:
        chunks.append(("", " ".join(current).strip()))
    return chunks


# ── Strategy: section-aware ───────────────────────────────────────────────────

def _section_aware_split(text: str) -> list[tuple[str, str]]:
    """Split on section headers, then sub-split each section if too large."""
    lines = text.splitlines(keepends=True)
    sections: list[tuple[str, list[str]]] = []
    current_title = ""
    current_lines: list[str] = []

    for line in lines:
        m = _SECTION_RE.match(line)
        if m:
            if current_lines:
                sections.append((current_title, current_lines))
            current_title = line.strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        sections.append((current_title, current_lines))

    result: list[tuple[str, str]] = []
    for title, sect_lines in sections:
        body = "".join(sect_lines).strip()
        if not body:
            continue
        if len(body) <= TARGET_CHARS_MAX:
            result.append((title, body))
        else:
            sub = _sentence_boundary_split(body)
            for _, sub_text in sub:
                result.append((title, sub_text))
    return result


# ── Helpers ───────────────────────────────────────────────────────────────────

def _stable_id(ticker: str, source: str, text: str) -> str:
    raw = f"{ticker}::{source}::{text[:256]}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]
