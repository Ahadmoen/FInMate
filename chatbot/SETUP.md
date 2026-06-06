# AIVA FinMate — Setup Guide

Complete setup instructions for a fresh Windows machine.

---

## Prerequisites

### 1. Python 3.13
Download and install from https://python.org/downloads

During installation:
- Check **"Add Python to PATH"**
- Check **"Install pip"**

Verify:
```powershell
python --version   # should show 3.13.x
pip --version
```

### 2. Git
Download from https://git-scm.com/download/win

Verify:
```powershell
git --version
```

### 3. VS Code (recommended)
Download from https://code.visualstudio.com

---

## Step 1 — Clone the Repository

```powershell
git clone <your-repo-url>
cd finmate-aiva
```

---

## Step 2 — Create a Virtual Environment

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

> If you get a scripts execution error, run this first:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

---

## Step 3 — Install Python Packages

```powershell
pip install -r requirements.txt
```

This installs:

| Package | Purpose |
|---|---|
| `fastapi` | Web framework |
| `uvicorn[standard]` | ASGI server |
| `pydantic`, `pydantic-settings` | Data validation & config |
| `httpx` | Async HTTP client |
| `supabase` | Supabase REST client |
| `asyncpg` | Direct PostgreSQL async driver |
| `qdrant-client` | Vector database client |
| `redis` | Redis cache client |
| `openai` | Groq LLM (OpenAI-compatible SDK) |
| `sentence-transformers` | Local embeddings (free, no API key) |
| `torch` | Required by sentence-transformers |
| `arq` | Background job worker |
| `structlog`, `loguru` | Logging |
| `python-dotenv` | Load `.env` file |

> First install takes 5–10 minutes — `torch` and `sentence-transformers` are large.

---

## Step 4 — Download Service Binaries

The app needs **Qdrant** (vector database) and **Redis** (cache) running locally.

### Qdrant
1. Download the Windows binary from:
   https://github.com/qdrant/qdrant/releases/latest
   → download `qdrant-x86_64-pc-windows-msvc.zip`
2. Extract and place `qdrant.exe` into:
   ```
   finmate-aiva/qdrant/qdrant.exe
   ```

### Redis
1. Download the Windows port from:
   https://github.com/tporadowski/redis/releases
   → download the `.zip` file
2. Extract and place `redis-server.exe` and `redis-cli.exe` into:
   ```
   finmate-aiva/redis/redis-server.exe
   finmate-aiva/redis/redis-cli.exe
   ```

Your folder structure should look like:
```
finmate-aiva/
├── qdrant/
│   └── qdrant.exe
├── redis/
│   ├── redis-server.exe
│   └── redis-cli.exe
├── venv/
├── app/
├── main.py
└── ...
```

---

## Step 5 — Configure Environment Variables

Create a `.env` file in the project root:

```powershell
copy .env.example .env
```

Then fill in your values:

```env
# Supabase — get from supabase.com → your project → Settings → API
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key

# Optional — faster than REST, get from Settings → Database → Connection string → URI
SUPABASE_DB_URL=postgresql://postgres:password@db.your-project.supabase.co:5432/postgres

# Groq (free) — get from console.groq.com
GROQ_API_KEY=your-groq-key

APP_NAME=AIVA

# LLM
LLM_PROVIDER=groq
LLM_MODEL=llama-3.3-70b-versatile
ROUTER_MODEL=llama-3.1-8b-instant

# Embeddings (local, no API key needed)
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=all-MiniLM-L6-v2
EMBEDDING_DIMENSIONS=384

# Reranker (local, no API key needed)
RERANKER_PROVIDER=local
LOCAL_RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
```

### Where to get API keys

| Key | Where to get it |
|---|---|
| `GROQ_API_KEY` | https://console.groq.com → API Keys (free) |
| `SUPABASE_URL` | Supabase Dashboard → Settings → API |
| `SUPABASE_KEY` | Supabase Dashboard → Settings → API → anon key |
| `SUPABASE_DB_URL` | Supabase Dashboard → Settings → Database → URI |

---

## Step 6 — Supabase Database Setup

Run the following in **Supabase SQL Editor**
(Dashboard → SQL Editor → New query):

### Portfolio tables
```sql
-- Create stock symbol reference table
CREATE TABLE IF NOT EXISTS symbols (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticker       TEXT NOT NULL UNIQUE,
    company_name TEXT,
    sector       TEXT,
    exchange     TEXT NOT NULL DEFAULT 'PSX',
    is_active    BOOLEAN NOT NULL DEFAULT true,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Create portfolio holdings table
CREATE TABLE IF NOT EXISTS portfolio_holdings (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL,
    symbol_id     UUID NOT NULL REFERENCES stock_symbol(id),
    quantity      NUMERIC(20, 4) NOT NULL CHECK (quantity > 0),
    avg_buy_price NUMERIC(20, 4) NOT NULL CHECK (avg_buy_price > 0),
    added_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, symbol_id)
);

CREATE INDEX IF NOT EXISTS idx_portfolio_holdings_user_id
    ON portfolio_holdings (user_id);
```

### Permissions (required for the API to read data)
```sql
GRANT SELECT ON stock_symbol TO anon;

ALTER TABLE portfolio_holdings ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "anon_read_all_dev" ON portfolio_holdings;
CREATE POLICY "anon_read_all_dev" ON portfolio_holdings
    FOR SELECT TO anon USING (true);

GRANT SELECT ON portfolio_holdings TO anon;
```

---

## Step 7 — Start the Services

Every time you start working, run these in VS Code terminal (`` Ctrl+` ``):

**Terminal 1 — start Qdrant + Redis, then the API:**
```powershell
.\start_services.ps1
venv\Scripts\uvicorn main:app --reload --port 8000
```

**Terminal 2 — test the API:**
```powershell
# Health check
curl.exe http://localhost:8000/

# Price lookup
curl.exe -X POST http://localhost:8000/v1/query/sync `
  -H "Content-Type: application/json" `
  -d '{\"query\":\"What is the price of OGDC?\"}'
```

Or open the interactive docs in your browser:
```
http://localhost:8000/docs
```

---

## Step 8 — (Optional) Populate Vector Database with News

Run this once to embed existing news from Supabase into Qdrant:

```powershell
venv\Scripts\python -c "
import asyncio
from app.ingestion.workers.news import ingest_news_from_supabase
asyncio.run(ingest_news_from_supabase())
"
```

---

## Stock Insight Card

Every `/v1/query/sync` response automatically includes an `insight_card` field
whenever the user asks about a known PSX stock. No extra setup is required —
it uses the same Supabase data that powers the rest of the API.

**Example response for `"What is OGDC price?"`:**
```json
{
  "intent": "PRICE_LOOKUP",
  "answer": "OGDC closed at PKR 155.00 ...",
  "insight_card": {
    "symbol": "OGDC",
    "company_name": "Oil & Gas Development Company",
    "open": 150.5,
    "close": 155.0,
    "current_price": 155.0,
    "high": 157.0,
    "low": 149.0,
    "volume": 500000,
    "currency": "PKR",
    "updated_at": "2026-05-15"
  }
}
```

**When the card is omitted** (general or non-stock queries):
```json
{
  "intent": "GENERAL",
  "answer": "Pakistan was founded in 1947 ...",
  "insight_card": null
}
```

The card is built in parallel with intent routing so it adds **zero latency**
to stock queries.

---

## Daily Workflow

```powershell
# 1. Activate virtual environment
venv\Scripts\Activate.ps1

# 2. Start services + API (Terminal 1)
.\start_services.ps1
venv\Scripts\uvicorn main:app --reload --port 8000

# 3. Open browser
start http://localhost:8000/docs

# 4. Stop everything when done
# Ctrl+C to stop uvicorn
Stop-Process -Name qdrant,redis-server -ErrorAction SilentlyContinue
```

---

## API Endpoints Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Health check |
| `POST` | `/v1/query/sync` | Ask the chatbot (returns JSON) |
| `POST` | `/v1/query` | Ask the chatbot (streaming SSE) |
| `GET` | `/v1/tickers/{symbol}/snapshot` | Full ticker profile |
| `GET` | `/v1/portfolio/{user_id}` | Portfolio with live P&L |
| `GET` | `/v1/portfolio/{user_id}/summary` | Portfolio totals only |
| `GET` | `/v1/health/freshness` | Data freshness status |
| `POST` | `/v1/admin/reindex` | Re-embed news into Qdrant |
| `GET` | `/docs` | Interactive Swagger UI |

---

## Troubleshooting

| Error | Fix |
|---|---|
| `venv\Scripts\Activate.ps1` blocked | Run `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser` |
| `Qdrant: not responding` | Wait 5 seconds and retry, or check `qdrant/qdrant.exe` exists |
| `Redis: not responding` | Check `redis/redis-server.exe` exists |
| `permission denied for table portfolio_holdings` | Run the permissions SQL in Supabase SQL Editor (Step 6) |
| `[Errno 22] Invalid argument` on first NEWS_QA | Known Windows issue with tqdm — already patched in code, retry once |
| `500 Internal Server Error` on query | Check the uvicorn terminal for the full Python traceback |
