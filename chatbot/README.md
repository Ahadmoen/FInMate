# AIVA FinMate — Production RAG System for PSX

Production-grade Retrieval-Augmented Generation (RAG) system for Pakistan Stock Exchange (PSX) financial data.

## Quick Start

### 1. Prerequisites
- Docker + Docker Compose
- Python 3.13
- API keys: Anthropic (or OpenAI), OpenAI (for embeddings), Supabase

### 2. Environment Setup

```bash
cp .env.example .env
# Fill in your API keys in .env
```

Required keys:
| Variable | Where to get it |
|---|---|
| `ANTHROPIC_API_KEY` | console.anthropic.com |
| `OPENAI_API_KEY` | platform.openai.com (used for text-embedding-3-large) |
| `SUPABASE_URL` + `SUPABASE_KEY` | Supabase dashboard |
| `SUPABASE_DB_URL` | Supabase → Settings → Database → Connection string → URI |
| `COHERE_API_KEY` | dashboard.cohere.com (for reranking) |

### 3. Start Infrastructure

```bash
make up      # Starts Qdrant + Redis in Docker
```

### 4. Bootstrap News Vectors

On first run, ingest existing `news_sentiment` rows into Qdrant:

```bash
make ingest-news
```

### 5. Run the API

```bash
make dev     # uvicorn with hot reload
```

API available at `http://localhost:8000`. Docs at `http://localhost:8000/docs`.

---

## API Endpoints

### New v1 Surface

| Method | Path | Description |
|---|---|---|
| POST | `/v1/query/sync` | Non-streaming RAG query |
| POST | `/v1/query` | Streaming SSE RAG query |
| GET | `/v1/tickers/{symbol}/snapshot` | Full snapshot for one ticker |
| GET | `/v1/health/freshness` | Data freshness + Qdrant/Redis health |
| POST | `/v1/admin/reindex` | Re-ingest news into Qdrant (auth required) |

### Legacy (unchanged for backward compat)

| Method | Path | Description |
|---|---|---|
| POST | `/chat/` | Original chat endpoint |
| POST | `/ingest/` | Manual text ingestion |
| GET | `/ingest/stats` | Vector DB statistics |
| GET | `/chat/health` | Health check |

### Example Requests

**Price lookup (no LLM, returns structured JSON):**
```bash
curl -s -X POST http://localhost:8000/v1/query/sync \
  -H "Content-Type: application/json" \
  -d '{"query": "What is PSO current price?", "user_name": "Ahmed"}'
```

**News QA (vector search + LLM):**
```bash
curl -s -X POST http://localhost:8000/v1/query/sync \
  -H "Content-Type: application/json" \
  -d '{"query": "Why did OGDC drop last week?", "user_name": "Sara"}'
```

**Ticker snapshot:**
```bash
curl http://localhost:8000/v1/tickers/PSO/snapshot
```

**Admin reindex:**
```bash
curl -X POST http://localhost:8000/v1/admin/reindex \
  -H "X-Admin-Key: your-admin-key"
```

---

## Running Tests

```bash
make test              # Full test suite with coverage
```

## Running Eval Harness

```bash
make eval              # Full 24-case golden dataset (needs running server)
make eval-smoke        # 8 smoke cases only (suitable for CI)
```

---

## Project Structure

```
app/
  api/              FastAPI routers
    v1/             New endpoints
    chat.py         Backward-compat /chat/
    ingest.py       Backward-compat /ingest/
  core/             Config, logging, dependencies
  generation/
    schemas.py      Pydantic v2 response models (per intent)
    prompts.py      Versioned system prompts + grounding contract
    llm.py          Provider-agnostic async LLM client
  retrieval/
    router.py       LLM-based intent classifier
    structured.py   asyncpg / Supabase queries
    vector.py       Qdrant hybrid search + reranking
    fusion.py       Reciprocal Rank Fusion + recency boost
  ingestion/
    chunking.py     Section-aware semantic chunking
    embeddings.py   Batched OpenAI embeddings + Redis cache
    workers/        Arq background jobs (news, market, arq_worker)
  cache/
    redis_cache.py  TTL-aware Redis cache
  models/           Backward-compat schema aliases
eval/               Golden dataset + metrics + runner
tests/              pytest unit + integration tests
```

---

## Key Design Decisions

See [ARCHITECTURE.md](ARCHITECTURE.md) for full rationale. The short version:

1. **Never put price data in Qdrant.** Numbers belong in SQL.
2. **Route before retrieving.** `PRICE_LOOKUP` never touches the vector store.
3. **Hybrid search is non-optional.** BM25 + dense fusion handles tickers and exact phrases better than dense alone.
4. **Every LLM call has a grounding contract.** The model formats data; it does not generate it.
