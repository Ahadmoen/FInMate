"""Main RAG query endpoints.

POST /v1/query       — streaming SSE
POST /v1/query/sync  — non-streaming, returns full JSON

Architecture:
  The LLM router outputs a declarative filter plan (tickers, sector,
  signal_filter, include_price, include_signal, include_news) instead of
  a list of function names.  _execute_filters() translates that plan into
  DB calls via a single fetch_market_data() method, so new query types need
  zero new functions — just new filter combinations.

  Phase 1 — portfolio fetch (when needs_portfolio=True).
  Phase 2 — fetch_market_data + specialised ops, all concurrent.
"""
from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any, AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.generation.llm import LLMClient
from app.generation.prompts import build_general_prompt, build_mixed_context_prompt
from app.generation.schemas import (
    AnalyticsResponse,
    Citation,
    ComparisonResponse,
    ForecastData,
    FundamentalsResponse,
    GeneralResponse,
    MultiStepResponse,
    NewsQAResponse,
    PortfolioQueryResponse,
    PriceLookupResponse,
    PriceSnapshot,
    QueryIntent,
    QueryRequest,
    RouterOutput,
    SignalData,
    StockInsightCard,
)
from app.retrieval.fusion import fuse_and_boost
from app.retrieval.router import QueryRouter
from app.retrieval.structured import StructuredStore
from app.stock_insight import build_insight_card

log = get_logger(__name__)
router = APIRouter()


# ── Dependency helpers ────────────────────────────────────────────────────────

def _get_structured(request: Request) -> StructuredStore:
    settings = get_settings()
    pool = getattr(request.app.state, "db_pool", None)
    sb   = getattr(request.app.state, "supabase", None)
    return StructuredStore(settings, pool=pool, supabase=sb)


def _services(request: Request):
    settings   = get_settings()
    structured = _get_structured(request)
    llm        = getattr(request.app.state, "llm", None) or LLMClient(settings)
    sectors    = getattr(request.app.state, "sectors", None)
    qrouter    = QueryRouter(llm, settings)
    vector     = getattr(request.app.state, "vector_store", None)
    embedder   = getattr(request.app.state, "embedder", None)
    cache      = getattr(request.app.state, "cache", None)
    return structured, llm, qrouter, vector, embedder, cache, settings, sectors


# ── Streaming endpoint ────────────────────────────────────────────────────────

@router.post("/query")
async def query_stream(body: QueryRequest, request: Request):
    structured, llm, qrouter, vector, embedder, cache, settings, sectors = _services(request)

    if not body.stream:
        return await _handle_query(
            body, structured, llm, qrouter, vector, embedder, cache, settings, sectors
        )

    trace_id = str(uuid.uuid4())

    async def _event_stream() -> AsyncIterator[str]:
        route = await qrouter.route(body.query, history=body.history, sectors=sectors)
        yield _sse_event("route", {
            "intent":          route.intent.value,
            "tickers":         route.filters.tickers,
            "sector":          route.filters.sector,
            "specialized_ops": route.specialized_ops,
            "needs_portfolio": route.needs_portfolio,
            "trace_id":        trace_id,
        })

        if route.intent == QueryIntent.MULTI_STEP:
            tools        = _build_tools()
            executor, _  = _build_executor(structured, vector, embedder, settings)
            messages     = (body.history or []) + [{"role": "user", "content": body.query}]
            answer, _    = await llm.run_agent(route.intent.value, messages, tools, executor)
            yield _sse_event("token", {"text": answer})
            yield _sse_event("done",  {"trace_id": trace_id})
            return

        if route.intent == QueryIntent.GENERAL and not route.filters.tickers \
                and not route.filters.sector and not route.specialized_ops:
            messages = build_general_prompt(body.query, body.user_name, history=body.history)
            async for token in llm.generate_stream("GENERAL", messages):
                yield _sse_event("token", {"text": token})
            yield _sse_event("done", {"trace_id": trace_id})
            return

        context_data = await _execute_filters(
            route, structured, vector, embedder, body.user_id, body.query, settings
        )
        yield _sse_event("context", {"keys": list(context_data.keys())})

        messages = build_mixed_context_prompt(
            body.query, body.user_name, context_data, body.history
        )
        async for token in llm.generate_stream(route.intent.value, messages):
            yield _sse_event("token", {"text": token})

        yield _sse_event("done", {"trace_id": trace_id})

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Trace-Id": trace_id},
    )


# ── Sync endpoint ─────────────────────────────────────────────────────────────

@router.post("/query/sync")
async def query_sync(body: QueryRequest, request: Request):
    structured, llm, qrouter, vector, embedder, cache, settings, sectors = _services(request)
    return await _handle_query(
        body, structured, llm, qrouter, vector, embedder, cache, settings, sectors
    )


# ── Core orchestration ────────────────────────────────────────────────────────

async def _handle_query(
    body: QueryRequest,
    structured: StructuredStore,
    llm: LLMClient,
    qrouter: QueryRouter,
    vector,
    embedder,
    cache,
    settings: Settings,
    sectors: list[str] | None = None,
):
    trace_id = str(uuid.uuid4())

    route, card_data = await asyncio.gather(
        qrouter.route(body.query, history=body.history, sectors=sectors),
        build_insight_card(body.query, structured, settings),
    )

    # Only override insight card with router ticker if that ticker is actually present
    # in the current query text (not just resolved from history / pronoun references).
    if route.filters.tickers and not card_data:
        from app.stock_insight import extract_ticker as _extract_ticker
        if _extract_ticker(body.query, settings) == route.filters.tickers[0]:
            card_data = await build_insight_card(
                body.query, structured, settings, ticker=route.filters.tickers[0]
            )

    insight_card = StockInsightCard(**card_data) if card_data else None

    f = route.filters
    log.info(
        "query_handled",
        trace_id=trace_id,
        intent=route.intent.value,
        tickers=f.tickers,
        sector=f.sector,
        signal_filter=f.signal_filter,
        specialized_ops=route.specialized_ops,
        needs_portfolio=route.needs_portfolio,
    )

    # Cache check — keyed on intent + query + tickers + sector + signal_filter
    if cache:
        cached = await cache.get_response(
            route.intent.value, body.query, f.tickers,
            sector=f.sector, signal_filter=f.signal_filter,
        )
        if cached:
            cached["trace_id"] = trace_id
            return cached

    history = body.history or []

    # ── MULTI_STEP ────────────────────────────────────────────────────────────
    if route.intent == QueryIntent.MULTI_STEP:
        tools              = _build_tools()
        executor, tool_log = _build_executor(structured, vector, embedder, settings)
        messages           = history + [{"role": "user", "content": body.query}]
        answer, iters      = await llm.run_agent("MULTI_STEP", messages, tools, executor)
        ms_citations = [
            Citation(ticker=tc["ticker"], doc_type="news", source="get_news")
            for tc in tool_log if tc["tool"] == "get_news" and tc.get("ticker")
        ]
        return MultiStepResponse(
            trace_id=trace_id, answer=answer, tool_calls_made=iters,
            insufficient_context="INSUFFICIENT_CONTEXT" in answer,
            insight_card=insight_card, citations=ms_citations,
        )

    # ── GENERAL with no data filters ──────────────────────────────────────────
    if route.intent == QueryIntent.GENERAL and not f.tickers \
            and not f.sector and not route.specialized_ops:
        messages = build_general_prompt(body.query, body.user_name, history=history)
        answer   = await llm.generate("GENERAL", messages)
        return GeneralResponse(trace_id=trace_id, answer=answer, insight_card=insight_card)

    # ── Execute filter plan ───────────────────────────────────────────────────
    context_data = await _execute_filters(
        route, structured, vector, embedder, body.user_id, body.query, settings
    )

    messages  = build_mixed_context_prompt(body.query, body.user_name, context_data, history)
    answer    = await llm.generate(route.intent.value, messages)
    citations = _build_citations(route, context_data)
    has_data  = any(bool(v) for v in context_data.values())
    market    = context_data.get("market_data", [])

    # ── PRICE_LOOKUP ──────────────────────────────────────────────────────────
    if route.intent == QueryIntent.PRICE_LOOKUP:
        snapshots = [_row_to_snapshot(r, settings) for r in market]
        return PriceLookupResponse(
            trace_id=trace_id, data=snapshots, answer=answer,
            insufficient_context=not snapshots, citations=citations,
            insight_card=insight_card,
        )

    # ── FUNDAMENTALS ─────────────────────────────────────────────────────────
    if route.intent == QueryIntent.FUNDAMENTALS:
        snapshots = [_row_to_snapshot(r, settings) for r in market]
        signals   = [_row_to_signal(r) for r in market if r.get("signal")]
        return FundamentalsResponse(
            trace_id=trace_id, prices=snapshots, signals=signals, forecasts=[],
            answer=answer, insufficient_context=not has_data,
            citations=citations, insight_card=insight_card,
        )

    # ── NEWS_QA ───────────────────────────────────────────────────────────────
    if route.intent == QueryIntent.NEWS_QA:
        chunks = context_data.get("news", [])
        resp   = NewsQAResponse(
            trace_id=trace_id, answer=answer,
            citations=_chunks_to_citations(chunks),
            insufficient_context="INSUFFICIENT_CONTEXT" in answer,
            insight_card=insight_card,
        )
        if cache:
            await cache.set_response(
                route.intent.value, body.query, f.tickers, resp.model_dump(),
                sector=f.sector, signal_filter=f.signal_filter,
            )
        return resp

    # ── COMPARISON ────────────────────────────────────────────────────────────
    if route.intent == QueryIntent.COMPARISON:
        return ComparisonResponse(
            trace_id=trace_id, answer=answer,
            structured_data=market, citations=citations,
            insight_card=insight_card,
        )

    # ── PORTFOLIO ─────────────────────────────────────────────────────────────
    if route.intent == QueryIntent.PORTFOLIO:
        rows = (context_data.get("portfolio") or []) + market
        return PortfolioQueryResponse(
            trace_id=trace_id, answer=answer, structured_data=rows,
            citations=citations, insufficient_context=not has_data,
            insight_card=insight_card,
        )

    # ── ANALYTICS + fallback ──────────────────────────────────────────────────
    rows = (
        market
        + context_data.get("top_gainers", [])
        + context_data.get("top_losers", [])
        + context_data.get("buy_signals", [])
        + context_data.get("sell_signals", [])
    )
    resp = AnalyticsResponse(
        trace_id=trace_id, answer=answer, structured_data=rows,
        citations=citations, intent=route.intent, insight_card=insight_card,
    )
    if cache and route.intent == QueryIntent.ANALYTICS:
        await cache.set_response(
            route.intent.value, body.query, f.tickers, resp.model_dump(),
            sector=f.sector, signal_filter=f.signal_filter,
        )
    return resp


# ── Two-phase filter executor ─────────────────────────────────────────────────

async def _execute_filters(
    route: RouterOutput,
    structured: StructuredStore,
    vector,
    embedder,
    user_id: str | None,
    query: str,
    settings: Settings,
) -> dict[str, Any]:
    """
    Phase 1 — portfolio (when needs_portfolio=True).
              Provides holding_tickers for the data fetch phase.
    Phase 2 — fetch_market_data + specialised ops, all concurrent.
    """
    context: dict[str, Any] = {}
    holding_tickers: list[str] = []
    f = route.filters

    # ── Phase 1: portfolio ────────────────────────────────────────────────────
    if route.needs_portfolio:
        if not user_id:
            log.warning("portfolio_requested_no_user_id", query=query[:80])
            context["portfolio_error"] = (
                "I can't access your portfolio because no user ID was provided."
            )
        else:
            try:
                rows = await structured.get_portfolio(user_id)
                context["portfolio"] = rows
                holding_tickers = [r["ticker"] for r in rows if r.get("ticker")]
                log.info("portfolio_fetched", user_id=user_id, holdings=len(holding_tickers))
            except Exception as exc:
                log.error("portfolio_fetch_error", user_id=user_id, error=str(exc))
                context["portfolio_error"] = "Failed to fetch portfolio data."

    # ── Phase 2: all concurrent ───────────────────────────────────────────────
    # For portfolio queries, scope the data fetch to held tickers
    effective_tickers = holding_tickers if (route.needs_portfolio and holding_tickers) else f.tickers

    async def _fetch_market():
        if effective_tickers or f.sector or f.signal_filter:
            return await structured.fetch_market_data(
                tickers=effective_tickers,
                sector=f.sector,
                signal_filter=f.signal_filter,
                include_price=f.include_price,
                include_signal=f.include_signal,
                limit=f.limit,
            )
        return []

    async def _fetch_signal_group(sig: str):
        return await structured.fetch_market_data(
            signal_filter=sig,
            include_price=f.include_price,
            include_signal=True,
            limit=f.limit,
        )

    async def _fetch_gainers():
        return await structured.get_top_movers(f.limit, ascending=False)

    async def _fetch_losers():
        return await structured.get_top_movers(f.limit, ascending=True)

    async def _fetch_news():
        news_tickers = effective_tickers or f.tickers or None
        return await _fetch_vector_context(query, vector, embedder, settings, tickers=news_tickers)

    tasks: dict[str, Any] = {"market_data": _fetch_market()}

    # Separate fetches for each signal type when the user asks about multiple signals
    # (e.g. "which stocks should I buy AND sell?" → signal_filters=["BUY","SELL"])
    for sig in f.signal_filters:
        sig_upper = sig.upper()
        if sig_upper in ("BUY", "STRONG_BUY"):
            tasks["buy_signals"] = _fetch_signal_group("BUY")
        elif sig_upper in ("SELL", "STRONG_SELL"):
            tasks["sell_signals"] = _fetch_signal_group("SELL")

    if "get_top_gainers" in route.specialized_ops:
        tasks["top_gainers"] = _fetch_gainers()
    if "get_top_losers" in route.specialized_ops:
        tasks["top_losers"] = _fetch_losers()
    if f.include_news:
        tasks["news"] = _fetch_news()

    keys    = list(tasks.keys())
    results = await asyncio.gather(*tasks.values(), return_exceptions=True)

    for key, result in zip(keys, results):
        if isinstance(result, Exception):
            log.error("filter_op_failed", key=key, error=str(result))
        elif result:
            context[key] = result

    return context


async def _fetch_vector_context(
    query: str,
    vector,
    embedder,
    settings: Settings,
    tickers: list[str] | None = None,
) -> list[dict]:
    if vector is None or embedder is None:
        return []
    dense_hits, sparse_hits = await vector.hybrid_search(
        query=query,
        tickers=tickers,
        doc_types=["news", "filing", "transcript"],
        recency_days=settings.news_recency_days,
    )
    fused = fuse_and_boost(dense_hits, sparse_hits, half_life_days=settings.news_half_life_days)
    return await vector.rerank(query, fused)


# ── Tool calling for MULTI_STEP ───────────────────────────────────────────────

def _build_tools() -> list[dict]:
    return [
        {
            "name": "get_latest_price",
            "description": "Get current OHLCV data for a PSX ticker symbol.",
            "parameters": {
                "type": "object",
                "properties": {"ticker": {"type": "string"}},
                "required": ["ticker"],
            },
        },
        {
            "name": "get_signal_and_forecast",
            "description": "Get the AI trading signal and price forecast for a ticker.",
            "parameters": {
                "type": "object",
                "properties": {"ticker": {"type": "string"}},
                "required": ["ticker"],
            },
        },
        {
            "name": "get_news",
            "description": "Get recent news headlines and sentiment for a ticker.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "limit": {"type": "integer", "default": 5},
                },
                "required": ["ticker"],
            },
        },
        {
            "name": "get_top_movers",
            "description": "Get top gaining or losing stocks on PSX today.",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {"type": "string", "enum": ["gainers", "losers"]},
                    "limit": {"type": "integer", "default": 5},
                },
                "required": ["direction"],
            },
        },
    ]


def _build_executor(structured: StructuredStore, vector, embedder, settings: Settings):
    import json as _json
    tool_log: list[dict] = []

    async def executor(tool_name: str, tool_input: dict) -> str:
        tool_log.append({"tool": tool_name, "ticker": tool_input.get("ticker")})
        try:
            if tool_name == "get_latest_price":
                row = await structured.get_latest_price(tool_input["ticker"])
                return _json.dumps(row or {"error": "No data found"}, default=str)

            if tool_name == "get_signal_and_forecast":
                ticker = tool_input["ticker"]
                sig, fore = await asyncio.gather(
                    structured.get_signal(ticker),
                    structured.get_forecast(ticker),
                )
                return _json.dumps({"signal": sig, "forecast": fore}, default=str)

            if tool_name == "get_news":
                news = await structured.get_news(
                    tool_input["ticker"], tool_input.get("limit", 5)
                )
                return _json.dumps(news, default=str)

            if tool_name == "get_top_movers":
                ascending = tool_input.get("direction", "gainers") == "losers"
                rows = await structured.get_top_movers(tool_input.get("limit", 5), ascending)
                return _json.dumps(rows, default=str)

        except Exception as exc:
            return _json.dumps({"error": str(exc)})

        return _json.dumps({"error": f"Unknown tool: {tool_name}"})

    return executor, tool_log


# ── Conversion helpers ────────────────────────────────────────────────────────

def _row_to_snapshot(row: dict, settings: Settings) -> PriceSnapshot:
    ticker = row.get("ticker", "")
    op     = row.get("open_price") or 0.0
    cl     = row.get("close") or 0.0
    change_pct = round(((cl - op) / op) * 100, 2) if op else None
    return PriceSnapshot(
        ticker=ticker,
        company_name=row.get("company_name") or settings.get_company_name(ticker),
        open_price=op or None,
        close_price=cl or None,
        high=row.get("high"),
        low=row.get("low"),
        volume=row.get("volume"),
        change_pct=change_pct,
        date=str(row.get("price_date") or row.get("date", "")),
    )


def _row_to_signal(row: dict) -> SignalData:
    return SignalData(
        ticker=row.get("ticker", ""),
        signal=row.get("signal", ""),
        confidence=row.get("confidence"),
        reason=row.get("reason"),
        dominant_sentiment=row.get("dominant_sentiment"),
        health_label=row.get("health_label"),
        blended_score=row.get("blended_score"),
        signal_strength=row.get("signal_strength"),
        forecast_signed_score=row.get("forecast_signed_score"),
    )


def _chunks_to_citations(chunks: list[dict]) -> list[Citation]:
    seen: set[str] = set()
    out = []
    for c in chunks:
        meta   = c.get("metadata", {})
        doc_id = meta.get("doc_id")
        if doc_id and doc_id in seen:
            continue
        if doc_id:
            seen.add(doc_id)
        out.append(Citation(
            ticker=meta.get("ticker"),
            doc_id=doc_id,
            doc_type=meta.get("doc_type"),
            source=meta.get("source"),
            published_at=meta.get("published_at"),
            score=c.get("score"),
        ))
    return out


def _build_citations(route: RouterOutput, context_data: dict) -> list[Citation]:
    return _chunks_to_citations(context_data.get("news", []))


def _sse_event(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"
