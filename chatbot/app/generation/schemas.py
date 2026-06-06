"""Pydantic v2 response schemas — one per query class.

Every public response carries trace_id and citations so the caller
can always verify where numbers came from.
"""
from __future__ import annotations

import uuid
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field, model_validator


# ── Intent enum ───────────────────────────────────────────────────────────────

class QueryIntent(str, Enum):
    PRICE_LOOKUP  = "PRICE_LOOKUP"
    ANALYTICS     = "ANALYTICS"
    NEWS_QA       = "NEWS_QA"
    FUNDAMENTALS  = "FUNDAMENTALS"
    COMPARISON    = "COMPARISON"
    PORTFOLIO     = "PORTFOLIO"
    MULTI_STEP    = "MULTI_STEP"
    GENERAL       = "GENERAL"


# ── Citation ──────────────────────────────────────────────────────────────────

class Citation(BaseModel):
    ticker: str | None = None
    doc_id: str | None = None
    doc_type: str | None = None       # news | transcript | filing | structured
    source: str | None = None
    published_at: str | None = None
    score: float | None = None


# ── Router output (internal) ──────────────────────────────────────────────────

class QueryFilters(BaseModel):
    """Declarative filter plan the router emits — no function names, just dimensions."""
    tickers: list[str] = Field(default_factory=list)
    sector: str | None = None
    signal_filter: str | None = None   # STRONG_BUY / BUY / HOLD / SELL / STRONG_SELL
    signal_filters: list[str] = Field(default_factory=list)  # multiple signals e.g. ["BUY","SELL"]
    include_price: bool = True
    include_signal: bool = True
    include_news: bool = False
    limit: int = 10


class RouterOutput(BaseModel):
    intent: QueryIntent
    filters: QueryFilters = Field(default_factory=QueryFilters)
    needs_portfolio: bool = False
    specialized_ops: list[str] = Field(default_factory=list)  # get_top_gainers | get_top_losers
    time_range: str | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


# ── Structured data containers (returned without LLM for pure numeric queries) ─

class PriceSnapshot(BaseModel):
    ticker: str
    company_name: str
    open_price: float | None
    close_price: float | None
    high: float | None
    low: float | None
    volume: int | None
    change_pct: float | None
    date: str | None


class SignalData(BaseModel):
    ticker: str
    signal: str                        # STRONG_BUY | BUY | HOLD | SELL | STRONG_SELL
    confidence: float | None           # 0–1
    reason: str | None
    dominant_sentiment: str | None
    health_label: str | None = None    # VERY_BAD → EXCELLENT
    blended_score: float | None = None
    signal_strength: float | None = None
    forecast_signed_score: float | None = None


class ForecastData(BaseModel):
    ticker: str
    direction: str | None
    predicted_price: float | None
    expected_change_pct: float | None
    confidence: float | None
    model_used: str | None
    forecast_date: str | None


# ── Per-intent response schemas ───────────────────────────────────────────────

class StockInsightCard(BaseModel):
    """Structured price snapshot shown alongside any stock-related response."""
    symbol: str
    company_name: str
    open: float | None = None
    current_price: float | None = None
    high: float | None = None
    low: float | None = None
    volume: int | None = None
    currency: str = "PKR"
    updated_at: str | None = None


class BaseResponse(BaseModel):
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    intent: QueryIntent
    citations: list[Citation] = Field(default_factory=list)
    insufficient_context: bool = False
    insight_card: StockInsightCard | None = None


class PriceLookupResponse(BaseResponse):
    intent: QueryIntent = QueryIntent.PRICE_LOOKUP
    data: list[PriceSnapshot]
    answer: str = ""


class FundamentalsResponse(BaseResponse):
    intent: QueryIntent = QueryIntent.FUNDAMENTALS
    prices: list[PriceSnapshot] = Field(default_factory=list)
    signals: list[SignalData] = Field(default_factory=list)
    forecasts: list[ForecastData] = Field(default_factory=list)
    answer: str = ""


class AnalyticsResponse(BaseResponse):
    intent: QueryIntent = QueryIntent.ANALYTICS
    answer: str
    structured_data: list[dict[str, Any]] = Field(default_factory=list)


class NewsQAResponse(BaseResponse):
    intent: QueryIntent = QueryIntent.NEWS_QA
    answer: str


class ComparisonResponse(BaseResponse):
    intent: QueryIntent = QueryIntent.COMPARISON
    answer: str
    structured_data: list[dict[str, Any]] = Field(default_factory=list)


class MultiStepResponse(BaseResponse):
    intent: QueryIntent = QueryIntent.MULTI_STEP
    answer: str
    tool_calls_made: int = 0


class GeneralResponse(BaseResponse):
    intent: QueryIntent = QueryIntent.GENERAL
    answer: str


class PortfolioQueryResponse(BaseResponse):
    intent: QueryIntent = QueryIntent.PORTFOLIO
    answer: str
    structured_data: list[dict[str, Any]] = Field(default_factory=list)


# Union type for the query endpoint
QueryResponse = (
    PriceLookupResponse
    | FundamentalsResponse
    | AnalyticsResponse
    | NewsQAResponse
    | ComparisonResponse
    | PortfolioQueryResponse
    | MultiStepResponse
    | GeneralResponse
)


# ── API request / response wrappers ──────────────────────────────────────────

class QueryRequest(BaseModel):
    model_config = {"json_schema_extra": {
        "examples": [{
            "query": "What is PSO's current price and signal?",
            "user_name": "Ahmed",
            "user_id": "user_123",
            "stream": False,
            "history": [],
        }]
    }}

    query: str = Field(min_length=1, max_length=2000)
    user_name: str = Field(default="Friend", max_length=100)
    user_id: str | None = None
    stream: bool = False
    history: list[dict] = Field(
        default_factory=list,
        description="Previous turns: [{role: user|assistant, content: str}, ...]",
    )


class TickerSnapshotResponse(BaseModel):
    ticker: str
    company_name: str
    price: PriceSnapshot | None
    signal: SignalData | None
    forecast: ForecastData | None
    news: list[dict[str, Any]] = Field(default_factory=list)
    freshness_seconds: int | None = None


class FreshnessEntry(BaseModel):
    ticker: str
    last_updated: str | None
    staleness_seconds: int | None
    is_stale: bool


class HealthFreshnessResponse(BaseModel):
    status: str
    entries: list[FreshnessEntry]
    qdrant_vectors: int
    redis_connected: bool


# ── Backward-compat wrappers (keeps old /chat/ contract intact) ───────────────

class LegacyChatRequest(BaseModel):
    message: str
    user_name: str = "Friend"
    user_id: str | None = None


class LegacyStockCard(BaseModel):
    type: str = "stock_card"
    data: dict[str, Any]


class LegacyChatResponse(BaseModel):
    answer: str
    card: LegacyStockCard | None = None
    sources: list[dict[str, Any]] = Field(default_factory=list)
    query_type: str = "general"
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


class LegacyIngestRequest(BaseModel):
    text: str = Field(min_length=10)
    source: str = "manual"
    metadata: dict[str, Any] | None = None


class LegacyIngestResponse(BaseModel):
    success: bool
    message: str
    chunks_added: int


# ── Chat session / message schemas ───────────────────────────────────────────

class ChatAskRequest(BaseModel):
    """Request body for POST /v1/chat/ask."""
    message: str = Field(min_length=1, max_length=2000)
    session_id: str | None = Field(
        default=None,
        description="Existing session UUID to continue. Omit to start a new session.",
    )


class ChatAskResponse(BaseModel):
    """Response from POST /v1/chat/ask — mirrors the Django BE contract."""
    answer: str
    session_id: str
    insight_card: StockInsightCard | None = None
    citations: list[Citation] = Field(default_factory=list)


class ChatMessageOut(BaseModel):
    id: str
    session_id: str
    role: str                       # USER | ASSISTANT
    content: str
    sources_used: Any = None
    insight_card: StockInsightCard | None = None
    created_at: str | None = None


class ChatSessionOut(BaseModel):
    id: str
    user_id: str | None = None
    title: str | None = None
    started_at: str | None = None
    last_active: str | None = None
    is_active: bool = True
    created_at: str | None = None


class ChatSessionDetailOut(ChatSessionOut):
    messages: list[ChatMessageOut] = Field(default_factory=list)


# ── Portfolio schemas ──────────────────────────────────────────────────────────

class PortfolioPosition(BaseModel):
    """One holding enriched with current market data and P&L."""
    id: str
    ticker: str
    company_name: str | None = None
    sector: str | None = None
    quantity: float
    avg_buy_price: float
    current_price: float | None = None
    price_date: str | None = None
    market_value: float | None = None   # quantity × current_price
    cost_basis: float                   # quantity × avg_buy_price
    unrealized_pnl: float | None = None
    pnl_pct: float | None = None
    added_at: str | None = None
    updated_at: str | None = None


class PortfolioSummary(BaseModel):
    """Aggregate metrics across all holdings."""
    total_positions: int
    total_cost_basis: float
    total_market_value: float | None = None
    total_unrealized_pnl: float | None = None
    total_pnl_pct: float | None = None


class PortfolioResponse(BaseModel):
    user_id: str
    positions: list[PortfolioPosition]
    summary: PortfolioSummary
