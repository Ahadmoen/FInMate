"""Portfolio endpoints.

GET /v1/portfolio/{user_id}         — full positions with live P&L
GET /v1/portfolio/{user_id}/summary — aggregate metrics only

The user_id is the Supabase auth UUID. Pass it in the URL path.
For production, gate these routes behind Supabase JWT verification;
for now they trust the caller (same pattern as /v1/admin uses X-Admin-Key).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from app.core.config import get_settings
from app.core.logging import get_logger
from app.generation.schemas import PortfolioPosition, PortfolioResponse, PortfolioSummary
from app.retrieval.structured import StructuredStore

log = get_logger(__name__)
router = APIRouter()


def _build_store(request: Request) -> StructuredStore:
    settings = get_settings()
    pool = getattr(request.app.state, "db_pool", None)
    sb   = getattr(request.app.state, "supabase", None)
    return StructuredStore(settings, pool=pool, supabase=sb)


@router.get("/{user_id}", response_model=PortfolioResponse)
async def get_portfolio(user_id: str, request: Request):
    """Return all holdings for a user with live prices and P&L."""
    store = _build_store(request)
    try:
        rows = await store.get_portfolio(user_id)
    except Exception as exc:
        log.error("portfolio_fetch_failed", user_id=user_id, error=str(exc))
        raise HTTPException(status_code=502, detail="Failed to fetch portfolio data.")

    positions = [
        PortfolioPosition(
            id=r["id"],
            ticker=r.get("ticker") or "UNKNOWN",
            company_name=r.get("company_name"),
            sector=r.get("sector"),
            quantity=r["quantity"],
            avg_buy_price=r["avg_buy_price"],
            current_price=r.get("current_price"),
            price_date=r.get("price_date"),
            market_value=r.get("market_value"),
            cost_basis=r["cost_basis"],
            unrealized_pnl=r.get("unrealized_pnl"),
            pnl_pct=r.get("pnl_pct"),
            added_at=r.get("added_at"),
            updated_at=r.get("updated_at"),
        )
        for r in rows
    ]

    total_cost   = sum(p.cost_basis for p in positions)
    total_mv     = sum(p.market_value for p in positions if p.market_value is not None)
    total_pnl    = sum(p.unrealized_pnl for p in positions if p.unrealized_pnl is not None)
    total_pnl_pct = (
        round((total_pnl / total_cost) * 100, 2) if total_cost else None
    )

    summary = PortfolioSummary(
        total_positions=len(positions),
        total_cost_basis=round(total_cost, 2),
        total_market_value=round(total_mv, 2) if total_mv else None,
        total_unrealized_pnl=round(total_pnl, 2) if total_pnl is not None else None,
        total_pnl_pct=total_pnl_pct,
    )

    log.info("portfolio_fetched", user_id=user_id, positions=len(positions))
    return PortfolioResponse(user_id=user_id, positions=positions, summary=summary)


@router.get("/{user_id}/summary", response_model=PortfolioSummary)
async def get_portfolio_summary(user_id: str, request: Request):
    """Return only the aggregate P&L summary (lighter call)."""
    full = await get_portfolio(user_id, request)
    return full.summary
