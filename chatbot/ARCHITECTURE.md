# ARCHITECTURE.md

## The Two-Store Decision

The most important architectural choice in this system is **never putting numeric price data into the vector store**.

Vector similarity is the right tool for retrieving semantically related text ("which news articles discuss PSO's revenue outlook?"). It is the wrong tool for exact numeric lookups ("what was PSO's closing price on 2026-05-10?") because:

1. **Similarity ≠ correctness.** A vector store may return a chunk that says "PSO closed near 315" when the actual value was 315.0 — semantically close, factually imprecise.
2. **No ordering semantics.** "Latest" or "highest" have no meaning in cosine-similarity space.
3. **Numerical drift.** Embedding models compress numbers; 315 and 3150 may be closer in embedding space than intended.

### Structured store (Supabase PostgreSQL)
Holds: OHLCV, signals, forecasts, news sentiment scores.
Queried with exact SQL. Numbers come out exactly as stored. No LLM in the path for pure numeric queries.

### Vector store (Qdrant)
Holds: news article chunks, earnings transcripts, filing excerpts.
Never holds raw price rows.

---

## Query Router

Every request passes through a lightweight LLM classifier (claude-haiku, fast+cheap) that returns one of:

| Intent | Route |
|---|---|
| `PRICE_LOOKUP` | Supabase SQL → formatted response. **No LLM.** |
| `FUNDAMENTALS` | Supabase SQL → formatted response. **No LLM.** |
| `ANALYTICS` | Supabase SQL → LLM formats narrative |
| `NEWS_QA` | Qdrant hybrid search → LLM synthesises with citations |
| `COMPARISON` | Supabase SQL (multi-ticker) → LLM compares |
| `MULTI_STEP` | Agent loop: LLM calls tools (SQL + vector) up to 5× |
| `GENERAL` | LLM with grounding contract, no retrieval |

Skipping the LLM for `PRICE_LOOKUP` and `FUNDAMENTALS` is what gives the system sub-800ms p50 for those query classes.

---

## Hybrid Vector Search

Pure dense (cosine similarity) retrieval underperforms on:
- Ticker symbols ("PSO" → close match to "PS-O", "PSOS")
- Exact phrases from filings
- Numeric strings

The solution is **Reciprocal Rank Fusion** of dense + sparse (BM25) results:

```
score(doc) = Σ 1/(k + rank_i)  for each ranked list i
```

Both lists are retrieved in parallel from Qdrant (named vectors), fused in `fusion.py`, then recency-boosted before the cross-encoder reranker re-orders the top-50 candidates to top-8.

**Mandatory metadata filters** are applied on every Qdrant query — never a full-collection scan:
- `ticker` in expected tickers
- `published_at >= cutoff` (90 days for news, none for filings)
- `doc_type` where intent-specific

---

## Grounding Contract

The system prompt injected into every LLM call includes hard rules:
1. Every number must come verbatim from `<context>`.
2. Missing data → `INSUFFICIENT_CONTEXT`, never a guess.
3. No invented tickers or dates.
4. Every factual claim must cite `doc_id + published_at`.

This means the LLM is a **formatter**, not a fact generator, for all numeric queries.

---

## Data Flow

```
User query
    │
    ▼
QueryRouter (LLM classifier + regex NER)
    │
    ├─ PRICE_LOOKUP/FUNDAMENTALS ──► Supabase SQL ──► PriceLookupResponse
    │
    ├─ ANALYTICS/COMPARISON ────────► Supabase SQL ──► LLM format ──► response
    │
    ├─ NEWS_QA ──────────────────────► Qdrant hybrid
    │                                       │
    │                                  RRF + recency boost
    │                                       │
    │                                  Cross-encoder rerank (top-8)
    │                                       │
    │                                   LLM synthesis + citations
    │                                       │
    │                                  NewsQAResponse
    │
    └─ MULTI_STEP ────────────────────► Agent loop (max 5 tool calls)
                                             │
                                         MultiStepResponse
```

---

## Caching Strategy

| Data | TTL | Key |
|---|---|---|
| Embeddings | 30 days | sha256(text + model_name) |
| NEWS_QA responses | 5 min | sha256(intent + query + tickers) |
| ANALYTICS/filing responses | 1 hour | same |
| PRICE_LOOKUP/FUNDAMENTALS | **Never** | — |

Prices are never cached because they change intraday.

---

## For the Next Engineer

- To add a new PSX ticker: add to `psx_tickers` in `app/core/config.py`.
- To change the LLM: set `LLM_PROVIDER=openai` and `LLM_MODEL=gpt-4o` in `.env`.
- To migrate to TimescaleDB: replace `SUPABASE_DB_URL` with a TimescaleDB DSN; the asyncpg queries in `app/retrieval/structured.py` are standard SQL and work without modification.
- To add a new query intent: add to `QueryIntent` enum in `schemas.py`, add a system prompt in `prompts.py`, add a handler branch in `app/api/v1/query.py`, add eval cases in `eval/golden_dataset.json`.
- All prompts are versioned via `PROMPT_VERSION` in `prompts.py`. Increment it when the grounding contract changes to invalidate Redis caches.
