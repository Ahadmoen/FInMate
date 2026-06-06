"""Structured data retrieval from Supabase.

Primary path: asyncpg (requires SUPABASE_DB_URL) — true async, connection
pooling, complex SQL.

Fallback path: async Supabase REST client — uses only SUPABASE_URL +
SUPABASE_KEY, no direct DB connection needed.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import asyncpg
from supabase._async.client import AsyncClient

from app.core.config import Settings
from app.core.logging import get_logger

log = get_logger(__name__)


class StructuredStore:
    def __init__(
        self,
        settings: Settings,
        pool: asyncpg.Pool | None = None,
        supabase: AsyncClient | None = None,
    ) -> None:
        self._s = settings
        self._pool = pool
        self._sb = supabase

    # ── Price / OHLCV ──────────────────────────────────────────────────────────

    async def get_latest_price(self, ticker: str) -> dict[str, Any] | None:
        ticker = ticker.upper()
        if self._pool:
            row = await self._pool.fetchrow(
                """
                SELECT ticker, open_price, close, high, low, volume, date
                FROM live_market_data
                WHERE ticker = $1
                ORDER BY date DESC
                LIMIT 1
                """,
                ticker,
            )
            return dict(row) if row else None

        resp = await self._sb.table("live_market_data")\
            .select("ticker,open_price,close,high,low,volume,date")\
            .eq("ticker", ticker).order("date", desc=True).limit(1).execute()
        return resp.data[0] if resp.data else None

    async def get_prices_range(
        self, ticker: str, start: str, end: str
    ) -> list[dict[str, Any]]:
        """Return OHLCV rows between start and end (ISO date strings)."""
        ticker = ticker.upper()
        if self._pool:
            rows = await self._pool.fetch(
                """
                SELECT ticker, open_price, close, high, low, volume, date
                FROM live_market_data
                WHERE ticker = $1 AND date BETWEEN $2 AND $3
                ORDER BY date ASC
                """,
                ticker, start, end,
            )
            return [dict(r) for r in rows]

        resp = await self._sb.table("live_market_data")\
            .select("ticker,open_price,close,high,low,volume,date")\
            .eq("ticker", ticker)\
            .gte("date", start).lte("date", end)\
            .order("date").execute()
        return resp.data or []

    # ── Signals & Forecasts ───────────────────────────────────────────────────

    async def get_signal(self, ticker: str) -> dict[str, Any] | None:
        ticker = ticker.upper()
        if self._pool:
            row = await self._pool.fetchrow(
                """
                SELECT ticker, signal, confidence, reason,
                       dominant_sentiment, generated_at
                FROM stock_signal
                WHERE ticker = $1
                ORDER BY generated_at DESC
                LIMIT 1
                """,
                ticker,
            )
            return dict(row) if row else None

        resp = await self._sb.table("stock_signal")\
            .select("*").eq("ticker", ticker)\
            .order("generated_at", desc=True).limit(1).execute()
        return resp.data[0] if resp.data else None

    async def get_forecast(self, ticker: str) -> dict[str, Any] | None:
        ticker = ticker.upper()
        if self._pool:
            row = await self._pool.fetchrow(
                """
                SELECT ticker, direction, predicted_price, expected_change_pct,
                       confidence, model_used, forecast_date
                FROM stock_forecast
                WHERE ticker = $1
                ORDER BY forecast_date DESC
                LIMIT 1
                """,
                ticker,
            )
            return dict(row) if row else None

        resp = await self._sb.table("stock_forecast")\
            .select("*").eq("ticker", ticker)\
            .order("forecast_date", desc=True).limit(1).execute()
        return resp.data[0] if resp.data else None

    # ── News ──────────────────────────────────────────────────────────────────

    async def get_news(self, ticker: str, limit: int = 5) -> list[dict[str, Any]]:
        ticker = ticker.upper()
        if self._pool:
            rows = await self._pool.fetch(
                """
                SELECT ticker, headline, sentiment, source, published_at, score
                FROM news_sentiment
                WHERE ticker = $1
                ORDER BY published_at DESC
                LIMIT $2
                """,
                ticker, limit,
            )
            return [dict(r) for r in rows]

        resp = await self._sb.table("news_sentiment")\
            .select("ticker,headline,sentiment,source,published_at,score")\
            .eq("ticker", ticker)\
            .order("published_at", desc=True).limit(limit).execute()
        return resp.data or []

    # ── Analytics ─────────────────────────────────────────────────────────────

    async def get_top_movers(self, limit: int = 5, ascending: bool = False) -> list[dict]:
        """Return top gainers (ascending=False) or losers (ascending=True)."""
        if self._pool:
            rows = await self._pool.fetch(
                """
                WITH latest AS (
                    SELECT DISTINCT ON (ticker)
                        ticker, open_price, close, volume, date
                    FROM live_market_data
                    ORDER BY ticker, date DESC
                )
                SELECT ticker, open_price, close, volume, date,
                       ROUND(((close - open_price) / NULLIF(open_price, 0)) * 100, 2) AS change_pct
                FROM latest
                WHERE open_price > 0
                ORDER BY change_pct %s
                LIMIT $1
                """ % ("ASC" if ascending else "DESC"),
                limit,
            )
            return [dict(r) for r in rows]

        # REST fallback — fetch all, compute in Python
        resp = await self._sb.table("live_market_data")\
            .select("ticker,open_price,close,volume,date")\
            .order("date", desc=True).limit(200).execute()
        rows = resp.data or []
        seen: set[str] = set()
        processed = []
        for r in rows:
            if r["ticker"] in seen:
                continue
            seen.add(r["ticker"])
            op = r.get("open_price") or 0
            cl = r.get("close") or 0
            if op > 0:
                r["change_pct"] = round(((cl - op) / op) * 100, 2)
                processed.append(r)
        processed.sort(key=lambda x: x["change_pct"], reverse=not ascending)
        return processed[:limit]

    async def get_buy_signals(self, limit: int = 5) -> list[dict]:
        if self._pool:
            rows = await self._pool.fetch(
                """
                SELECT ticker, signal, confidence, reason, dominant_sentiment
                FROM stock_signal
                WHERE signal IN ('BUY', 'STRONG_BUY')
                ORDER BY CASE signal WHEN 'STRONG_BUY' THEN 0 ELSE 1 END, confidence DESC
                LIMIT $1
                """,
                limit,
            )
            return [dict(r) for r in rows]

        resp = await self._sb.table("stock_signal")\
            .select("ticker,signal,confidence,reason,dominant_sentiment")\
            .in_("signal", ["BUY", "STRONG_BUY"]).order("confidence", desc=True).limit(limit * 2).execute()
        data = resp.data or []
        data.sort(key=lambda x: (0 if x["signal"] == "STRONG_BUY" else 1, -x.get("confidence", 0)))
        return data[:limit]

    async def get_all_latest_prices(self) -> list[dict]:
        """Used by health/freshness endpoint."""
        if self._pool:
            rows = await self._pool.fetch(
                """
                SELECT DISTINCT ON (ticker) ticker, date
                FROM live_market_data
                ORDER BY ticker, date DESC
                """
            )
            return [dict(r) for r in rows]

        resp = await self._sb.table("live_market_data")\
            .select("ticker,date").order("date", desc=True).limit(500).execute()
        seen: set[str] = set()
        out = []
        for r in (resp.data or []):
            if r["ticker"] not in seen:
                seen.add(r["ticker"])
                out.append(r)
        return out

    # ── Portfolio ─────────────────────────────────────────────────────────────

    async def get_portfolio(self, user_id: str) -> list[dict[str, Any]]:
        """
        Return all holdings for a user, joined with stock_symbol and latest price.
        Each row includes: ticker, company_name, sector, quantity, avg_buy_price,
        current_price, price_date, market_value, cost_basis, unrealized_pnl, pnl_pct.
        """
        if self._pool:
            rows = await self._pool.fetch(
                """
                SELECT
                    ph.id::text,
                    ph.user_id::text,
                    ph.quantity::float,
                    ph.avg_buy_price::float,
                    ph.added_at::text,
                    ph.updated_at::text,
                    s.ticker,
                    s.company_name,
                    s.sector,
                    lmd.close::float          AS current_price,
                    lmd.date::text            AS price_date,
                    (ph.quantity * lmd.close)::float
                                              AS market_value,
                    (ph.quantity * ph.avg_buy_price)::float
                                              AS cost_basis,
                    ((lmd.close - ph.avg_buy_price) * ph.quantity)::float
                                              AS unrealized_pnl,
                    CASE WHEN ph.avg_buy_price > 0
                         THEN ROUND(((lmd.close - ph.avg_buy_price)
                              / ph.avg_buy_price) * 100, 2)
                         ELSE 0
                    END::float                AS pnl_pct
                FROM portfolio_holdings ph
                JOIN stock_symbol s ON ph.symbol_id = s.id
                LEFT JOIN LATERAL (
                    SELECT close, date
                    FROM live_market_data
                    WHERE ticker = s.ticker
                    ORDER BY date DESC
                    LIMIT 1
                ) lmd ON true
                WHERE ph.user_id = $1::uuid
                ORDER BY market_value DESC NULLS LAST
                """,
                user_id,
            )
            return [dict(r) for r in rows]

        # REST fallback — three separate fetches joined in Python
        ph_resp = await self._sb.table("portfolio_holdings") \
            .select("id,user_id,quantity,avg_buy_price,added_at,updated_at,symbol_id") \
            .eq("user_id", user_id).execute()
        holdings = ph_resp.data or []
        if not holdings:
            return []

        symbol_ids = list({h["symbol_id"] for h in holdings})
        sym_resp = await self._sb.table("stock_symbol") \
            .select("id,ticker,company_name,sector") \
            .in_("id", symbol_ids).execute()
        sym_map = {s["id"]: s for s in (sym_resp.data or [])}

        tickers = [sym_map[h["symbol_id"]]["ticker"]
                   for h in holdings if h["symbol_id"] in sym_map]
        price_map: dict[str, dict] = {}
        if tickers:
            px_resp = await self._sb.table("live_market_data") \
                .select("ticker,close,date") \
                .in_("ticker", tickers) \
                .order("date", desc=True).limit(len(tickers) * 5).execute()
            for row in (px_resp.data or []):
                if row["ticker"] not in price_map:
                    price_map[row["ticker"]] = row

        result = []
        for h in holdings:
            sym = sym_map.get(h["symbol_id"], {})
            ticker = sym.get("ticker")
            px = price_map.get(ticker, {}) if ticker else {}
            qty = float(h["quantity"])
            abp = float(h["avg_buy_price"])
            cur = float(px["close"]) if px.get("close") is not None else None
            mv = round(qty * cur, 4) if cur is not None else None
            cb = round(qty * abp, 4)
            pnl = round((cur - abp) * qty, 4) if cur is not None else None
            pnl_pct = round(((cur - abp) / abp) * 100, 2) if cur and abp else None
            result.append({
                "id": h["id"],
                "user_id": h["user_id"],
                "ticker": ticker,
                "company_name": sym.get("company_name"),
                "sector": sym.get("sector"),
                "quantity": qty,
                "avg_buy_price": abp,
                "current_price": cur,
                "price_date": px.get("date"),
                "market_value": mv,
                "cost_basis": cb,
                "unrealized_pnl": pnl,
                "pnl_pct": pnl_pct,
                "added_at": h.get("added_at"),
                "updated_at": h.get("updated_at"),
            })
        result.sort(key=lambda x: (x["market_value"] or 0), reverse=True)
        return result

    async def get_signals_for_tickers(self, tickers: list[str]) -> list[dict[str, Any]]:
        """Return the latest BUY/SELL/HOLD signal for each ticker in the list.

        Used for portfolio-scoped sell/hold recommendations — the caller
        provides only the tickers the user actually holds.
        """
        if not tickers:
            return []
        upper = [t.upper() for t in tickers]

        if self._pool:
            rows = await self._pool.fetch(
                """
                SELECT DISTINCT ON (ticker)
                    ticker, signal, confidence, reason,
                    dominant_sentiment, generated_at
                FROM stock_signal
                WHERE ticker = ANY($1)
                ORDER BY ticker, generated_at DESC
                """,
                upper,
            )
            return [dict(r) for r in rows]

        # REST fallback — one .in_() call covers all tickers
        resp = await self._sb.table("stock_signal") \
            .select("ticker,signal,confidence,reason,dominant_sentiment,generated_at") \
            .in_("ticker", upper) \
            .order("generated_at", desc=True) \
            .execute()

        # Keep only the latest row per ticker
        seen: set[str] = set()
        out = []
        for r in (resp.data or []):
            if r["ticker"] not in seen:
                seen.add(r["ticker"])
                out.append(r)
        return out

    # ── Unified parameterised market data fetch ───────────────────────────────

    async def fetch_market_data(
        self,
        tickers: list[str] | None = None,
        sector: str | None = None,
        signal_filter: str | None = None,
        include_price: bool = True,
        include_signal: bool = True,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Single query covering price + signal + company info with any filter combo.

        Entry points:
          - tickers → fetch those specific stocks
          - sector  → fetch all stocks in that sector
          - signal_filter → fetch stocks with that signal (STRONG_BUY / BUY / etc.)
          - any combination of the above
        Returns [] when no filter is supplied to avoid full-table scans.
        """
        upper_tickers = [t.upper() for t in tickers] if tickers else None

        # Expand "BUY" → ["BUY", "STRONG_BUY"] and "SELL" → ["SELL", "STRONG_SELL"]
        signal_group: list[str] | None = None
        if signal_filter:
            _sf = signal_filter.upper()
            if _sf == "BUY":
                signal_group = ["BUY", "STRONG_BUY"]
            elif _sf == "SELL":
                signal_group = ["SELL", "STRONG_SELL"]
            else:
                signal_group = [_sf]

        has_filter = bool(upper_tickers or sector or signal_group)
        if not has_filter:
            return []

        if self._pool:
            order = "ASC" if signal_filter and signal_filter.upper() in ("SELL", "STRONG_SELL") else "DESC"
            rows = await self._pool.fetch(
                f"""
                WITH base AS (
                    SELECT ticker, company_name, sector
                    FROM stock_symbol
                    WHERE ($1::text[] IS NULL OR ticker = ANY($1))
                      AND ($2::text IS NULL OR sector ILIKE '%' || $2 || '%')
                )
                SELECT
                    b.ticker, b.company_name, b.sector,
                    lmd.open_price, lmd.close, lmd.high, lmd.low,
                    lmd.volume,  lmd.date AS price_date,
                    sig.signal, sig.health_label, sig.confidence,
                    sig.blended_score, sig.signal_strength,
                    sig.forecast_signed_score, sig.contributions,
                    sig.reason, sig.dominant_sentiment
                FROM base b
                LEFT JOIN LATERAL (
                    SELECT open_price, close, high, low, volume, date
                    FROM live_market_data
                    WHERE ticker = b.ticker
                    ORDER BY date DESC LIMIT 1
                ) lmd ON true
                LEFT JOIN LATERAL (
                    SELECT signal, health_label, confidence, blended_score,
                           signal_strength, forecast_signed_score, contributions,
                           reason, dominant_sentiment
                    FROM stock_signal
                    WHERE ticker = b.ticker
                    ORDER BY generated_at DESC LIMIT 1
                ) sig ON true
                WHERE ($3::text[] IS NULL OR sig.signal = ANY($3))
                ORDER BY sig.confidence {order} NULLS LAST
                LIMIT $4
                """,
                upper_tickers, sector, signal_group, limit,
            )
            return [dict(r) for r in rows]

        # ── REST fallback: 3-step join in Python ──────────────────────────────
        sym_q = self._sb.table("stock_symbol").select("ticker,company_name,sector")
        if upper_tickers:
            sym_q = sym_q.in_("ticker", upper_tickers)
        if sector:
            sym_q = sym_q.ilike("sector", f"%{sector}%")
        sym_resp = await sym_q.limit(limit * 3).execute()
        symbols  = sym_resp.data or []
        if not symbols:
            return []

        sym_tickers = [s["ticker"] for s in symbols]
        sym_map     = {s["ticker"]: s for s in symbols}

        price_resp, sig_resp = await asyncio.gather(
            self._sb.table("live_market_data")
                .select("ticker,open_price,close,high,low,volume,date")
                .in_("ticker", sym_tickers)
                .order("date", desc=True)
                .limit(len(sym_tickers) * 3)
                .execute(),
            self._sb.table("stock_signal")
                .select(
                    "ticker,signal,health_label,confidence,blended_score,"
                    "signal_strength,forecast_signed_score,contributions,"
                    "reason,dominant_sentiment"
                )
                .in_("ticker", sym_tickers)
                .order("generated_at", desc=True)
                .limit(len(sym_tickers) * 3)
                .execute(),
        )

        price_map: dict[str, dict] = {}
        for r in price_resp.data or []:
            if r["ticker"] not in price_map:
                price_map[r["ticker"]] = r

        sig_map: dict[str, dict] = {}
        for r in sig_resp.data or []:
            if r["ticker"] not in sig_map:
                sig_map[r["ticker"]] = r

        results = []
        for ticker in sym_tickers:
            sym   = sym_map.get(ticker, {})
            price = price_map.get(ticker, {})
            sig   = sig_map.get(ticker, {})
            if signal_group and sig.get("signal") not in signal_group:
                continue
            results.append({
                "ticker":               ticker,
                "company_name":         sym.get("company_name"),
                "sector":               sym.get("sector"),
                "open_price":           price.get("open_price"),
                "close":                price.get("close"),
                "high":                 price.get("high"),
                "low":                  price.get("low"),
                "volume":               price.get("volume"),
                "price_date":           price.get("date"),
                "signal":               sig.get("signal"),
                "health_label":         sig.get("health_label"),
                "confidence":           sig.get("confidence"),
                "blended_score":        sig.get("blended_score"),
                "signal_strength":      sig.get("signal_strength"),
                "forecast_signed_score":sig.get("forecast_signed_score"),
                "contributions":        sig.get("contributions"),
                "reason":               sig.get("reason"),
                "dominant_sentiment":   sig.get("dominant_sentiment"),
            })

        results.sort(key=lambda x: (x.get("confidence") or 0), reverse=True)
        return results[:limit]

    async def get_distinct_sectors(self) -> list[str]:
        """Return all distinct non-null sector values from stock_symbol."""
        if self._pool:
            rows = await self._pool.fetch(
                "SELECT DISTINCT sector FROM stock_symbol WHERE sector IS NOT NULL ORDER BY sector"
            )
            return [r["sector"] for r in rows]

        resp = await self._sb.table("stock_symbol").select("sector").execute()
        seen: set[str] = set()
        out  = []
        for r in (resp.data or []):
            s = r.get("sector")
            if s and s not in seen:
                seen.add(s)
                out.append(s)
        return sorted(out)

    # ── News freshness — fetch rows not yet in Qdrant ─────────────────────────

    async def get_unindexed_news(self, after: str | None = None, limit: int = 500) -> list[dict]:
        """Returns news_sentiment rows for Qdrant ingestion."""
        if self._pool:
            if after:
                rows = await self._pool.fetch(
                    """
                    SELECT id, ticker, headline, sentiment, source,
                           published_at, score
                    FROM news_sentiment
                    WHERE published_at > $1
                    ORDER BY published_at DESC
                    LIMIT $2
                    """,
                    after, limit,
                )
            else:
                rows = await self._pool.fetch(
                    """
                    SELECT id, ticker, headline, sentiment, source,
                           published_at, score
                    FROM news_sentiment
                    ORDER BY published_at DESC
                    LIMIT $1
                    """,
                    limit,
                )
            return [dict(r) for r in rows]

        q = self._sb.table("news_sentiment")\
            .select("id,ticker,headline,sentiment,source,published_at,score")\
            .order("published_at", desc=True).limit(limit)
        if after:
            q = q.gt("published_at", after)
        resp = await q.execute()
        return resp.data or []
