# FinMate Chatbot — Issues, Fixes & Enhancements

This document covers every bug found, every fix applied, and every new feature
added during the review and improvement session. Each issue includes the exact
prompt that triggered it, the observed behaviour, the root cause, and the fix.

---

## 1. Bugs Fixed

---

### 1.1 Cache Always Missed — Every Request Re-ran the Full LLM Pipeline
**File:** `app/api/v1/query.py`

**Trigger:** Any query.

**Observed:** Every request took full LLM latency even for identical repeated queries. Caching had no effect.

**Root cause:** The cache lookup ran *before* routing, passing an empty intent string `""` and an empty tickers list `[]`. The cache key was built from those empty values, so it could never match what was stored (which used the real intent and tickers after routing).

```python
# Before — always a miss, intent="" tickers=[]
cached = await cache.get_response("", body.query, [])

# After — runs after routing, uses real values
cached = await cache.get_response(route.intent.value, body.query, f.tickers, ...)
```

**Fix:** Moved the cache check to after routing.

---

### 1.2 Stale Cache Returned Wrong Answer After a Fix Was Applied
**File:** `app/cache/redis_cache.py`, `app/api/v1/query.py`

**Trigger:** `"tell me about stocks in the IT field"` — after the sector routing fix was deployed, the chatbot still returned `"I don't have any data on IT stocks"`.

**Observed (from logs):**
```
query_routed  sector="TECHNOLOGY & COMMUNICATION"   ← routing correct now
query_handled ...
POST /chat_message                                   ← answer saved immediately
                                                     ← NO Supabase stock_symbol call
                                                     ← NO Groq generation call
```

**Root cause:** The first (wrong) response had been cached under the key `ANALYTICS::<query>::`. The new routing correctly identified the sector but the cache returned the old "no data" response without hitting the DB or running the LLM. Cache TTL for ANALYTICS was 1 hour.

Additionally, the cache key did not include `sector` or `signal_filter`, so `"IT stocks"` and `"cement stocks"` could theoretically collide if the query text was similar.

**Fix:**
1. Cache key now includes `sector` and `signal_filter` so different filter combinations never share an entry.
2. Redis must be flushed (`redis-cli FLUSHDB`) after deploying a routing fix to clear stale entries.

```python
# Cache key now includes all dimensions that affect the response
payload = f"{intent}::{query}::{'|'.join(sorted(tickers))}::{sector or ''}::{signal_filter or ''}"
```

---

### 1.3 "Which stocks should I sell?" — No Sell Logic Existed
**File:** `app/api/v1/query.py`, `app/retrieval/structured.py`

**Trigger:** `"which stocks should I sell?"`

**Observed:** The chatbot answered only the buy half of a buy+sell query, or gave generic portfolio P&L with no sell recommendation.

**Root cause:** Two separate problems:
1. The `_fetch_analytics()` function used `if "gainer" / "loser" / "buy signal" in query_lower` keyword matching. The word `"sell"` matched no branch, so it silently fell through to the gainers default.
2. There was no `get_sell_signals` or `get_signals_for_tickers` method in `StructuredStore`. Even if "sell" were caught, there was no DB call to back it up.

**Fix:**
- Added `get_signals_for_tickers(tickers)` to `StructuredStore` — fetches BUY/SELL/HOLD for exactly the stocks a user holds in one batched query (`WHERE ticker = ANY($1)`).
- Replaced keyword matching entirely with the new filter-based router (see Enhancement 2.1).
- The router now correctly routes "which stocks should I sell?" to `PORTFOLIO` intent with `needs_portfolio=true` and fetches signals scoped to holdings.

---

### 1.4 "How is my portfolio doing?" — Returned Someone Else's Stocks
**File:** `app/api/v1/query.py`

**Trigger:** `"how is my portfolio doing?"`

**Observed:** The chatbot returned data for random stocks, not the user's actual holdings.

**Root cause:** `user_id` existed on the `QueryRequest` schema but was never used in `_handle_query`. Portfolio queries routed to `GENERAL` (since `PORTFOLIO` was not a recognised intent), which simply asked the LLM to answer without fetching any user-specific data.

**Fix:**
- Added `PORTFOLIO` as a first-class `QueryIntent`.
- `user_id` is now passed through the entire pipeline.
- When `needs_portfolio=true`, Phase 1 of `_execute_filters` calls `get_portfolio(user_id)` to fetch the user's actual holdings before any other data is fetched.

---

### 1.5 "Should I leave this one?" — Resolved as Portfolio Query Instead of Specific Stock
**File:** `app/generation/llm.py`, `app/retrieval/router.py`

**Trigger:** Mid-conversation after discussing Systems Limited (SYS):
> User: "how is systems limited performing?"
> Assistant: "SYS is up 3.2% today..."
> User: "should I leave this one?"

**Observed:** The chatbot routed to `PORTFOLIO` and asked about the user's holdings instead of giving a sell/hold recommendation for SYS.

**Root cause:** The router (`llama-3.1-8b-instant`) received only the current message `"should I leave this one?"` in isolation — no conversation history. It saw "leave" → sell/exit → PORTFOLIO, with no way to know "this one" referred to SYS.

**Fix:**
- The last 3 turns of conversation history (6 messages) are now passed to the router alongside the current query.
- The router prompt includes explicit instructions to resolve pronouns (`"this one"`, `"it"`, `"that stock"`) using the conversation context before classifying.
- Routing rules now distinguish: "sell + resolvable ticker from context → FUNDAMENTALS" vs "sell + no ticker → PORTFOLIO".

```
RECENT CONVERSATION CONTEXT:
  User: how is systems limited performing?
  Assistant: Systems Limited (SYS) is up 3.2% today, trading at PKR 412.

IMPORTANT: resolve pronouns like 'this one', 'it' to the ticker above.

CURRENT QUERY TO CLASSIFY: should I leave this one
```

Result: Router now correctly outputs `intent=FUNDAMENTALS, tickers=["SYS"]`.

---

### 1.6 "Which stocks should I sell?" — Signal Data Ignored Despite Being in Context
**File:** `app/generation/prompts.py`

**Trigger:** `"which stocks should I sell?"` after portfolio fetch succeeded.

**Observed (confirmed via logs):**
```
portfolio_fetched  holdings=2  (IBFL, FZCM)
stock_signal queried → 200 OK  (IBFL: STRONG BUY, FZCM: HOLD)
```
Answer: *"IBFL is your worst performer, down 9.98%..."* — no mention of signals.

**Root cause:** The PORTFOLIO system prompt said:
> *"lead with P&L, highlight best and worst performers"*

The LLM had the signal data in context but followed the prompt instruction to focus on P&L. It never mentioned `STRONG BUY` or `HOLD` because the prompt never asked it to use signals.

**Fix:** Rewrote the PORTFOLIO prompt to explicitly instruct the LLM to:
- Use `SIGNALS FOR YOUR HOLDINGS` when the user asks about selling or buying.
- Treat `SELL`/`STRONG_SELL` as a reason to exit; `BUY`/`HOLD` as a reason not to sell.
- Fall back to P&L narrative only for "how is my portfolio doing?" queries.

Expected answer after fix:
> *"Based on signals for your holdings, you should NOT sell either stock. IBFL has a STRONG BUY signal (0.87 confidence) — even though it's down 9.98%, the model sees a recovery case. FZCM has a HOLD signal — maintain your position."*

---

### 1.7 "Tell me about IT stocks" — Returned Top Gainers Instead
**File:** `app/generation/llm.py`, `app/retrieval/structured.py`

**Trigger:** `"tell me about the stocks that are companies in the field of information technology"`

**Observed:** Returned AATM (+16%) and ASIC (+14%) — the top gainers — with a note that they might be IT companies. The DB has a sector called `"Technology & Communication"` but it was never queried.

**Root cause:** Three compounding problems:
1. No `fetch_market_data(sector=...)` method existed — there was no way to query stocks by sector.
2. The `get_distinct_sectors()` REST fallback used `.not_.is_("sector", "null")` — invalid Supabase Python syntax — which silently returned `[]`. So `app.state.sectors` was always empty.
3. Because sectors were empty, the router prompt used a hardcoded fallback list (`"Information Technology"`) instead of the real DB value (`"Technology & Communication"`). The SQL exact match then found zero rows.

**Fix:**
1. Fixed `get_distinct_sectors()` REST path — removed the broken `.not_.is_()` call, now fetches all and filters in Python.
2. Changed `fetch_market_data` SQL from exact match to `ILIKE '%sector%'` so partial matches work as a safety net.
3. Sectors now load correctly at startup into `app.state.sectors` and are injected into every router prompt.
4. `chat.py` was also missing the sectors pass-through — fixed so `/v1/chat/ask` gets the same sector list as `/v1/query/sync`.

---

### 1.8 Incomplete Signal Data — Performance Queries Got Shallow Answers
**File:** `app/retrieval/structured.py`

**Trigger:** `"how well is PSO performing?"`

**Observed:** Answer mentioned `signal=BUY` and `confidence=0.82` but nothing else.

**Root cause:** The `get_signal` query only fetched 6 columns:
```sql
SELECT ticker, signal, confidence, reason, dominant_sentiment, generated_at
```
But the `stock_signal` table has rich performance data that was never fetched:
- `health_label` (VERY_BAD → EXCELLENT)
- `blended_score` (combined decision score)
- `signal_strength`
- `forecast_signed_score`
- `contributions` (what factors drove the signal)

**Fix:** `fetch_market_data` now selects all signal columns. `SignalData` schema updated to include `health_label`, `blended_score`, `signal_strength`, `forecast_signed_score`.

Expected answer after fix:
> *"PSO has a BUY signal with 0.82 confidence. Its health label is GOOD and the blended score is 0.74. The main contributors are strong volume and positive sentiment..."*

---

### 1.9 First Vector Search Request Timed Out
**File:** `main.py`

**Trigger:** First query involving news after server restart (e.g. `"what is the news regarding the oil industry?"`).

**Observed:**
```json
{"answer": "The assistant is taking too long to respond. Please try again."}
```

**From logs:**
```
query_handled       → 09:35:13
loading_local_embedding_model → 09:36:15   ← 62 seconds later
```

**Root cause:** The local embedding model (`all-MiniLM-L6-v2`) and reranker (`cross-encoder/ms-marco-MiniLM-L-6-v2`) were lazy-loaded on the first request that needed them. Model loading took 62 seconds, exceeding the client timeout.

**Fix:** Both models now warm up at server startup:
```
warming_up_embedding_model  → loads in ~30s on cold start
warming_up_reranker         → loads in ~5s
aiva_ready                  → first request is instant
```

---

### 1.10 N+1 Database Calls
**File:** `app/api/v1/query.py`

**Trigger:** Any FUNDAMENTALS query with multiple tickers.

**Root cause:** `_fetch_fundamentals()` looped over tickers with sequential `await` calls:
```python
for ticker in tickers:
    row = await structured.get_latest_price(ticker)   # await 1
    sig = await structured.get_signal(ticker)          # await 2
    fore = await structured.get_forecast(ticker)       # await 3
```
3 tickers = 9 sequential DB round-trips.

**Fix:** Replaced with the unified `fetch_market_data()` which executes a single SQL query using LATERAL joins across `live_market_data` and `stock_signal` for all tickers at once.

---

### 1.11 MULTI_STEP Intent Broken in Streaming Mode
**File:** `app/api/v1/query.py`

**Root cause:** The streaming endpoint's `MULTI_STEP` branch fell through to `llm.generate_stream()` — a single-shot LLM call — instead of `llm.run_agent()`. The agent loop with tool calls (get_price, get_signal, get_news) never executed.

**Fix:** Streaming endpoint now calls `run_agent()` for `MULTI_STEP` and emits the final answer as a single token event.

---

### 1.12 `LLMClient` Recreated on Every Request
**File:** `app/api/v1/query.py`

**Root cause:** `_services()` instantiated a new `LLMClient` — and its underlying HTTP connection pool — on every incoming request.

**Fix:** `LLMClient` initialised once in the FastAPI lifespan, stored in `app.state.llm`, and read from state on each request.

---

### 1.13 `python-jose` Not Installed
**File:** `requirements.txt`

**Observed:** `ModuleNotFoundError: No module named 'jose'` at runtime when auth dependency tried to verify JWT tokens.

**Fix:** Added to `requirements.txt` and ran `pip install "python-jose[cryptography]"`.

---

### 1.14 Supabase RLS Blocked Chat Table Writes
**File:** `.env`

**Observed (from logs):**
```
"error": "{'code': '42501', 'message': 'permission denied for table chat_session'}"
502 Bad Gateway
```

**Root cause:** `SUPABASE_KEY` was the **anon key**, which is subject to Row Level Security. The `chat_session` table had no RLS policy permitting inserts.

**Fix:** Changed `SUPABASE_KEY` to the **service role key** (Supabase Dashboard → Settings → API → service_role). The service role key bypasses RLS and is appropriate for trusted backend services.

---

## 2. Architecture Enhancements

---

### 2.1 Filter-Based Router Replaces Keyword Matching
**Files:** `app/generation/llm.py`, `app/retrieval/router.py`, `app/generation/schemas.py`, `app/api/v1/query.py`

**Problem:** Sub-routing used `if "gainer" in query_lower / "loser" in query_lower / "buy signal" in query_lower` chains. Any synonym, paraphrase, or multi-intent query failed silently.

**Before (fragile):**
```python
if "gainer" in query_lower or "top" in query_lower:
    rows = await structured.get_top_movers(5, ascending=False)
elif "loser" in query_lower or "worst" in query_lower:
    rows = await structured.get_top_movers(5, ascending=True)
elif "buy signal" in query_lower:
    rows = await structured.get_buy_signals(5)
# "sell" → no match → silently returned gainers
```

**After (filter-based):** The LLM router outputs a declarative filter plan instead of operation names:

```json
{
  "intent": "ANALYTICS",
  "filters": {
    "tickers": [],
    "sector": "Technology & Communication",
    "signal_filter": null,
    "include_price": true,
    "include_signal": true,
    "include_news": false,
    "limit": 10
  },
  "needs_portfolio": false,
  "specialized_ops": []
}
```

A single `fetch_market_data(tickers, sector, signal_filter, ...)` method executes the right SQL using whichever filters are non-null. No new functions needed for new query types — just new filter combinations.

**Queries handled with zero new code:**

| Query | Filter combination |
|---|---|
| "IT sector stocks" | `sector="Technology & Communication"` |
| "stocks with SELL signals" | `signal_filter="SELL"` |
| "IT stocks with BUY signals" | `sector="Technology & Communication", signal_filter="BUY"` |
| "how is PSO performing?" | `tickers=["PSO"], include_signal=True` |
| "news on OGDC" | `tickers=["OGDC"], include_news=True` |

---

### 2.2 Two-Phase Execution — Portfolio Scoping
**File:** `app/api/v1/query.py` → `_execute_filters()`

**Phase 1** — When `needs_portfolio=true`, the user's holdings are fetched first. This gives `holding_tickers` — the list of stocks the user actually owns.

**Phase 2** — All other operations run concurrently with `asyncio.gather`. For portfolio queries, `fetch_market_data` is scoped to `holding_tickers` so signals and prices are only fetched for stocks the user holds.

This correctly answers "which stocks should I sell?" — the sell recommendation only applies to stocks the user owns, not the entire PSX universe.

---

### 2.3 Sector-Aware Routing with Live DB Sectors
**Files:** `main.py`, `app/retrieval/structured.py`, `app/generation/llm.py`, `app/api/v1/chat.py`

At startup, distinct sector values are fetched from `stock_symbol` and cached in `app.state.sectors`. These are injected into every router prompt so the LLM maps user phrases to exact DB values:

```
Known sectors: Technology & Communication, Banking, Cement, Oil & Gas Exploration, ...
User says "IT companies" → router outputs sector="Technology & Communication"
```

If a new sector is added to the DB, it automatically appears in the router prompt at next restart — zero code changes needed.

---

### 2.4 Direct Chat Endpoints — Django BE Middleman Removed
**Files:** `app/api/v1/chat.py`, `app/retrieval/chat_store.py`, `app/core/deps.py`

Previously: Frontend → Django BE → this service (two hops, extra latency, extra failure point).

Now: Frontend → this service directly.

**New endpoints:**

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/v1/chat/ask` | Send message, get grounded answer |
| `GET` | `/v1/chat/sessions` | List user's chat sessions |
| `GET` | `/v1/chat/sessions/{id}` | Full session with message history |

**Session flow:**
```
1st message  →  session_id omitted  →  server creates session  →  returns session_id
2nd message  →  session_id sent     →  server loads history    →  contextual answer
```

**Auth:** Django Simple JWT. Frontend sends `Authorization: Bearer <access_token>` from the Django login response. The `user_id` claim is extracted and used for all DB operations.

`ChatStore` (`app/retrieval/chat_store.py`) manages `chat_session` and `chat_message` with both asyncpg and Supabase REST fallback, matching the table schema from the Django BE migrations.

---

### 2.5 Startup Model Warmup
**File:** `main.py`

Both local ML models now load at startup instead of on first request:

```
1. Configure logging
2. Connect Supabase (asyncpg pool or REST client)
3. Connect Qdrant, ensure collection exists
4. Connect Redis
5. Build EmbeddingClient, VectorStore, RedisCache, LLMClient
6. Fetch distinct sectors from stock_symbol → app.state.sectors
7. Warm up embedding model (all-MiniLM-L6-v2)
8. Warm up reranker (cross-encoder/ms-marco-MiniLM-L-6-v2)
9. aiva_ready — server accepts requests
```

Steps 6–8 are new. Cold startup takes ~60s longer but every subsequent request is fast.

---

### 2.6 Conversation History in Router for Pronoun Resolution
**Files:** `app/generation/llm.py`, `app/retrieval/router.py`, `app/api/v1/query.py`

The last 3 conversation turns are now passed to the router alongside the current query. This allows the 8B router model to resolve pronouns (`"this one"`, `"it"`, `"that stock"`) back to the named ticker before classifying intent.

---

### 2.7 Rich Signal Data in All Responses
**Files:** `app/retrieval/structured.py`, `app/generation/schemas.py`

`fetch_market_data` now selects all signal columns previously ignored:

| Column | Meaning |
|---|---|
| `health_label` | VERY_BAD / BAD / NEUTRAL / GOOD / EXCELLENT |
| `blended_score` | Combined numeric decision score |
| `signal_strength` | Magnitude of the signal |
| `forecast_signed_score` | Directional forecast component |
| `contributions` | What factors drove the signal |
| `reason` | Human-readable explanation |

---

## 3. Configuration Changes

### New `.env` Variables

| Variable | Purpose |
|---|---|
| `DJANGO_SECRET_KEY` | Must match `SECRET_KEY` in Django BE — used to verify Simple JWT tokens |
| `SUPABASE_KEY` | Must be the **service role key**, not the anon key |

### `.env` Formatting Warning

Django's `SECRET_KEY` often contains `#` and `$` characters. In `.env` files, `#` is treated as a comment start. Always wrap the value in double quotes:

```env
# Wrong — truncated at #
DJANGO_SECRET_KEY=django-insecure-abc#xyz

# Correct
DJANGO_SECRET_KEY="django-insecure-abc#xyz"
```

---

## 4. New Files

| File | Purpose |
|---|---|
| `app/api/v1/chat.py` | Stateful chat endpoints replacing Django BE middleman |
| `app/retrieval/chat_store.py` | `chat_session` + `chat_message` DB operations |
| `CHANGES.md` | This document |
