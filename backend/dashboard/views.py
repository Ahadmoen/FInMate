from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from django.db import close_old_connections
from django.db.models import Avg
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.market_utils import effective_change_pct, live_snapshot_updated_iso
from core.models import (
    LiveMarketData,
    NewsSentiment,
    StockForecast,
    StockSignal,
    StockSymbol,
)
from dashboard.db_cache import db_cache_get, db_cache_get_or_compute, db_cache_set
from portfolio.analytics import (
    _build_enriched,
    _fetch_forecasts,
    _fetch_live,
    _fetch_signals,
    _section_allocation,
    _section_health,
    _section_risk,
    _section_summary,
    _time_ago,
    _tone,
)
from portfolio.models import PortfolioHolding as Holding


# ── Cache TTLs ────────────────────────────────────────────────────────────────
_TTL_MEDIUM = 900   # 15 min
_TTL_SHORT  = 480   # 8 min


# ── DISTINCT ON helpers ───────────────────────────────────────────────────────

def _latest_signals(ticker_filter=None):
    qs = StockSignal.objects.order_by("ticker", "-generated_at").distinct("ticker")
    if ticker_filter is not None:
        qs = qs.filter(ticker__in=ticker_filter)
    return qs


def _latest_forecasts(ticker_filter=None):
    qs = StockForecast.objects.order_by("ticker", "-forecast_date").distinct("ticker")
    if ticker_filter is not None:
        qs = qs.filter(ticker__in=ticker_filter)
    return qs


def _latest_live(ticker_filter=None):
    qs = LiveMarketData.objects.order_by("ticker", "-date").distinct("ticker")
    if ticker_filter is not None:
        qs = qs.filter(ticker__in=ticker_filter)
    return qs


# ── Label helpers ─────────────────────────────────────────────────────────────

_HEALTH_LABEL_DISPLAY = {
    "EXCELLENT": "Excellent",
    "GOOD":      "Good",
    "NEUTRAL":   "Steady",
    "BAD":       "Weak",
    "VERY_BAD":  "Poor",
}

_MOOD_LABEL_DISPLAY = {
    "BULLISH": "Strong",
    "NEUTRAL": "Steady",
    "BEARISH": "Weak",
}


def _health_display(value: str | None) -> str | None:
    if value is None:
        return None
    return _HEALTH_LABEL_DISPLAY.get(value, value)


def _mood_display(value: str | None) -> str | None:
    if value is None:
        return None
    return _MOOD_LABEL_DISPLAY.get(value, value)


def _sentiment_label(score: float) -> str:
    if score > 0.5:
        return "Very Positive"
    if score > 0.2:
        return "Positive"
    if score > -0.2:
        return "Mixed"
    if score > -0.5:
        return "Negative"
    return "Very Negative"


# ── Pure compute functions (no cache logic) ───────────────────────────────────

def _compute_market_summary():
    close_old_connections()
    try:
        buy = hold = sell = 0
        for sig in _latest_signals().values_list("signal", flat=True):
            if sig in ("BUY", "STRONG_BUY"):
                buy += 1
            elif sig == "HOLD":
                hold += 1
            else:
                sell += 1
        return {"buy": buy, "hold": hold, "sell": sell, "total": buy + hold + sell}
    finally:
        close_old_connections()


def _compute_market_mood():
    close_old_connections()
    try:
        rows = list(
            _latest_signals().values("ticker", "health_label", "signal", "blended_score")
        )

        bull = neut = bear = 0
        buy = hold = sell = 0
        sig_scores: dict = {}

        for row in rows:
            lbl = row["health_label"]
            if lbl in ("GOOD", "EXCELLENT"):
                bull += 1
            elif lbl == "NEUTRAL":
                neut += 1
            else:
                bear += 1

            sig = row["signal"]
            if sig in ("BUY", "STRONG_BUY"):
                buy += 1
            elif sig == "HOLD":
                hold += 1
            else:
                sell += 1

            if row["blended_score"] is not None:
                sig_scores[row["ticker"]] = row["blended_score"]

        total = bull + neut + bear

        # Scoped to last 7 days — uses the (ticker, published_at) index
        seven_days_ago = timezone.now() - timedelta(days=7)
        avg_sent = float(
            NewsSentiment.objects
            .filter(published_at__gte=seven_days_ago)
            .aggregate(a=Avg("score"))["a"] or 0.0
        )

        bull_pct = (bull / total * 100) if total else 0
        if bull_pct > 55:
            mood_label = "Optimistic"
        elif bull_pct > 45:
            mood_label = "Mixed"
        elif bull_pct > 35:
            mood_label = "Cautious"
        else:
            mood_label = "Risk Off"

        confidence_index = round(((bull + neut * 0.5) / total) * 100, 1) if total else 0.0

        if avg_sent > 0.3:
            news_sent_label = "Positive"
        elif avg_sent > 0.1:
            news_sent_label = "Neutral"
        else:
            news_sent_label = "Negative"

        sector_buckets: dict = defaultdict(list)
        for sym in StockSymbol.objects.filter(
            is_active=True, ticker__in=sig_scores, sector__gt=""
        ).values("ticker", "sector"):
            sector_buckets[sym["sector"]].append(sig_scores[sym["ticker"]])

        hottest = (
            max(sector_buckets, key=lambda k: sum(sector_buckets[k]) / len(sector_buckets[k]))
            if sector_buckets else None
        )

        return {
            "strong_count": bull,
            "steady_count": neut,
            "weak_count": bear,
            "buy_count": buy,
            "hold_count": hold,
            "sell_count": sell,
            "total": total,
            "avg_sentiment_score": round(avg_sent, 4),
            "mood_label": mood_label,
            "confidence_index": confidence_index,
            "news_sentiment": news_sent_label,
            "hottest_sector": hottest,
        }
    finally:
        close_old_connections()


def _compute_ai_pick():
    close_old_connections()
    try:
        good_fc = {
            fc.ticker: fc
            for fc in _latest_forecasts()
            if fc.direction == "UP" and fc.confidence >= 0.88
        }
        if not good_fc:
            return None

        good_sig = {
            sig.ticker: sig
            for sig in _latest_signals(ticker_filter=good_fc)
            if sig.health_label in ("GOOD", "EXCELLENT")
            and sig.signal in ("BUY", "STRONG_BUY")
            and sig.suggestion_confidence != "LOW"
        }
        if not good_sig:
            return None

        live_map = {
            lmd.ticker: lmd
            for lmd in _latest_live(ticker_filter=good_sig)
            if lmd.rsi14 is not None and 35 <= lmd.rsi14 <= 65
        }
        candidates = [t for t in good_sig if t in live_map]
        if not candidates:
            return None

        best = max(candidates, key=lambda t: good_sig[t].blended_score or 0)
        sig = good_sig[best]
        fc  = good_fc[best]
        lmd = live_map[best]
        sym = StockSymbol.objects.filter(ticker=best).values("company_name", "sector").first()

        return {
            "symbol": best,
            "name": sym["company_name"] if sym else best,
            "industry": sym["sector"] if sym else None,
            "current_price": float(lmd.close),
            "change_pct_today": effective_change_pct(
                lmd.change_pct, lmd.open_price, lmd.close
            ),
            "price_updated_at": live_snapshot_updated_iso(lmd.updated_at),
            "forecast_change_pct": fc.expected_change_pct,
            "forecast_confidence": fc.confidence,
            "health_label": _health_display(sig.health_label),
            "rsi14": lmd.rsi14,
            "signal_action": sig.signal,
            "signal_confidence": sig.suggestion_confidence,
            "blended_score": sig.blended_score,
            "reason": sig.reason,
            "dominant_sentiment": sig.dominant_sentiment,
            "picked_at": timezone.now().isoformat(),
        }
    finally:
        close_old_connections()


def _compute_rising_stars(sector_filter: str, limit: int):
    close_old_connections()
    try:
        good_fc = {
            fc.ticker: fc
            for fc in _latest_forecasts()
            if fc.direction == "UP" and fc.confidence >= 0.85
        }
        if not good_fc:
            return {"stocks": [], "total": 0, "sector_filter": sector_filter}

        good_sig = {
            sig.ticker: sig
            for sig in _latest_signals(ticker_filter=good_fc)
            if sig.health_label not in ("VERY_BAD", "BAD")
            and sig.signal not in ("SELL", "STRONG_SELL")
        }
        if not good_sig:
            return {"stocks": [], "total": 0, "sector_filter": sector_filter}

        live_map = {
            lmd.ticker: lmd
            for lmd in _latest_live(ticker_filter=good_sig)
            if lmd.rsi14 is not None and 30 <= lmd.rsi14 <= 65
        }

        sym_map = {
            s.ticker: s
            for s in StockSymbol.objects.filter(
                ticker__in=[t for t in good_sig if t in live_map],
                is_active=True,
            )
        }

        rows = []
        for ticker in good_sig:
            if ticker not in live_map:
                continue
            sym = sym_map.get(ticker)
            if sector_filter != "all" and (not sym or sym.sector != sector_filter):
                continue
            sig = good_sig[ticker]
            fc  = good_fc[ticker]
            lmd = live_map[ticker]
            rows.append({
                "_score": sig.blended_score or 0,
                "symbol": ticker,
                "name": sym.company_name if sym else ticker,
                "industry": sym.sector if sym else None,
                "current_price": float(lmd.close),
                "change_pct_today": effective_change_pct(
                    lmd.change_pct, lmd.open_price, lmd.close
                ),
                "price_updated_at": live_snapshot_updated_iso(lmd.updated_at),
                "forecast_change_pct": fc.expected_change_pct,
                "forecast_confidence": fc.confidence,
                "health_label": _health_display(sig.health_label),
                "rsi14": lmd.rsi14,
                "volume_ratio": lmd.volume_ratio,
                "action": sig.signal,
                "blended_score": sig.blended_score,
                "reason": sig.reason,
                "dominant_sentiment": sig.dominant_sentiment,
                "is_top_pick": False,
            })

        rows.sort(key=lambda r: r["_score"], reverse=True)
        if rows:
            rows[0]["is_top_pick"] = True

        stocks = [{k: v for k, v in r.items() if k != "_score"} for r in rows[:limit]]
        return {"stocks": stocks, "total": len(rows), "sector_filter": sector_filter}
    finally:
        close_old_connections()


def _compute_sector_performance():
    close_old_connections()
    try:
        latest_sigs = list(
            _latest_signals().values("ticker", "signal", "blended_score")
        )
        fc_map = {
            fc["ticker"]: fc["expected_change_pct"]
            for fc in _latest_forecasts().values("ticker", "expected_change_pct")
        }
        sym_map = {
            s["ticker"]: s["sector"]
            for s in StockSymbol.objects.filter(is_active=True, sector__gt="")
            .values("ticker", "sector")
        }

        bucket: dict = defaultdict(lambda: {
            "blended_scores": [], "fc_pcts": [],
            "buy": 0, "hold": 0, "sell": 0, "count": 0,
        })

        for row in latest_sigs:
            sector = sym_map.get(row["ticker"])
            if not sector:
                continue
            d = bucket[sector]
            d["count"] += 1
            if row["blended_score"] is not None:
                d["blended_scores"].append(row["blended_score"])
            pct = fc_map.get(row["ticker"])
            if pct is not None:
                d["fc_pcts"].append(pct)
            if row["signal"] in ("BUY", "STRONG_BUY"):
                d["buy"] += 1
            elif row["signal"] == "HOLD":
                d["hold"] += 1
            else:
                d["sell"] += 1

        sectors = []
        for sector, d in bucket.items():
            avg_score = (
                sum(d["blended_scores"]) / len(d["blended_scores"])
                if d["blended_scores"] else 0.0
            )
            avg_fc_pct = (
                sum(d["fc_pcts"]) / len(d["fc_pcts"])
                if d["fc_pcts"] else 0.0
            )
            if avg_score > 0.3:
                health_label = _mood_display("BULLISH")
            elif avg_score > -0.3:
                health_label = _mood_display("NEUTRAL")
            else:
                health_label = _mood_display("BEARISH")

            trend = "up" if avg_fc_pct > 0.5 else ("down" if avg_fc_pct < -0.5 else "neutral")

            sectors.append({
                "sector": sector,
                "stock_count": d["count"],
                "avg_health_score": round(avg_score, 4),
                "health_label": health_label,
                "avg_forecast_pct": round(avg_fc_pct, 4),
                "trend": trend,
                "buy_count": d["buy"],
                "hold_count": d["hold"],
                "sell_count": d["sell"],
                "is_hottest": False,
            })

        sectors.sort(key=lambda s: s["avg_health_score"], reverse=True)
        if sectors:
            sectors[0]["is_hottest"] = True

        return {"sectors": sectors}
    finally:
        close_old_connections()


def _compute_top_performers():
    close_old_connections()
    try:
        candidates = sorted(
            [
                sig for sig in _latest_signals()
                if sig.health_label not in ("VERY_BAD", "BAD", None)
                and sig.blended_score is not None
            ],
            key=lambda s: s.blended_score,
            reverse=True,
        )

        if not candidates:
            return {"featured": None, "list": []}

        top_ranked_tickers = [s.ticker for s in candidates[:50]]
        live_map = {
            lmd.ticker: lmd
            for lmd in _latest_live(ticker_filter=top_ranked_tickers)
        }

        sig_map = {sig.ticker: sig for sig in candidates}
        top5 = [t for t in top_ranked_tickers if t in live_map][:5]

        if not top5:
            return {"featured": None, "list": []}

        fc_map = {fc.ticker: fc for fc in _latest_forecasts(ticker_filter=top5)}
        sym_map = {
            s.ticker: s
            for s in StockSymbol.objects.filter(ticker__in=top5)
        }

        def _signal_strength(signal: str, confidence: str | None) -> str:
            if signal in ("BUY", "STRONG_BUY") and confidence == "HIGH":
                return "STRONG_BUY"
            if signal in ("BUY", "STRONG_BUY") and confidence == "MEDIUM":
                return "BUY"
            if signal == "HOLD":
                return "HOLD"
            return "SELL"

        def _build(ticker: str) -> dict:
            sig = sig_map[ticker]
            lmd = live_map[ticker]
            fc  = fc_map.get(ticker)
            sym = sym_map.get(ticker)
            return {
                "symbol": ticker,
                "name": sym.company_name if sym else ticker,
                "industry": sym.sector if sym else None,
                "current_price": float(lmd.close),
                "change_pct_today": effective_change_pct(
                    lmd.change_pct, lmd.open_price, lmd.close
                ),
                "price_updated_at": live_snapshot_updated_iso(lmd.updated_at),
                "forecast_change_pct": fc.expected_change_pct if fc else None,
                "forecast_direction": fc.direction if fc else None,
                "health_label": _health_display(sig.health_label),
                "health_score": sig.blended_score,
                "rsi14": lmd.rsi14,
                "signal_action": sig.signal,
                "signal_confidence": sig.suggestion_confidence,
                "blended_score": sig.blended_score,
                "dominant_sentiment": sig.dominant_sentiment,
                "signal_strength": _signal_strength(sig.signal, sig.suggestion_confidence),
            }

        stocks = [_build(t) for t in top5]
        return {"featured": stocks[0], "list": stocks[1:]}
    finally:
        close_old_connections()


# ── Cache-wrapped fetch functions ─────────────────────────────────────────────

def _fetch_market_summary():
    return db_cache_get_or_compute(
        "dashboard:market_summary", _compute_market_summary, _TTL_MEDIUM
    )


def _fetch_market_mood():
    return db_cache_get_or_compute(
        "dashboard:market_mood", _compute_market_mood, _TTL_MEDIUM
    )


def _fetch_ai_pick():
    today = timezone.localdate().isoformat()
    cache_key = f"dashboard:ai_pick:{today}"

    cached, _ = db_cache_get(cache_key)
    if cached is not None:
        # Pick is stable for the day; refresh live price only
        close_old_connections()
        try:
            live = (
                LiveMarketData.objects
                .filter(ticker=cached["symbol"])
                .order_by("-date")
                .values("close", "change_pct", "open_price", "updated_at")
                .first()
            )
        finally:
            close_old_connections()
        if live:
            cached["current_price"] = float(live["close"])
            cached["change_pct_today"] = effective_change_pct(
                live["change_pct"], live.get("open_price"), live["close"]
            )
            if live.get("updated_at"):
                cached["price_updated_at"] = live_snapshot_updated_iso(live["updated_at"])
        return cached

    payload = _compute_ai_pick()
    if payload is not None:
        now = timezone.localtime()
        seconds_until_midnight = 86400 - (now.hour * 3600 + now.minute * 60 + now.second)
        db_cache_set(cache_key, payload, seconds_until_midnight)
    return payload


def _fetch_rising_stars(sector_filter: str, limit: int):
    return db_cache_get_or_compute(
        f"dashboard:rising_stars:v2:{sector_filter}:{limit}",
        lambda: _compute_rising_stars(sector_filter, limit),
        _TTL_SHORT,
    )


def _fetch_sector_performance():
    return db_cache_get_or_compute(
        "dashboard:sector_performance", _compute_sector_performance, _TTL_MEDIUM
    )


def _fetch_top_performers():
    return db_cache_get_or_compute(
        "dashboard:top_performers:v2", _compute_top_performers, _TTL_MEDIUM
    )


# ── Portfolio Health ──────────────────────────────────────────────────────────

_HEALTH_DISPLAY = {"BULLISH": "Healthy", "NEUTRAL": "Steady", "BEARISH": "Weak"}

_RISK_DISPLAY = {
    "LOW":      {"label": "Low",      "sublabel": "Institutional Grade"},
    "MODERATE": {"label": "Moderate", "sublabel": "Market Rate"},
    "HIGH":     {"label": "High",     "sublabel": "Above Average Risk"},
}

_DIV_LABELS = [
    (8.0, "Highly Optimized"),
    (6.0, "Well Diversified"),
    (4.0, "Moderate"),
    (0.0, "Needs Improvement"),
]


def _diversification_score(holdings: list, allocation: dict) -> tuple[float, str]:
    n_sectors  = len({h["industry"] for h in holdings})
    n_holdings = len(holdings)
    weights    = [h["position_weight"] / 100.0 for h in holdings]
    hhi        = sum(w * w for w in weights)

    sector_score   = min(n_sectors, 5)  / 5.0  * 5.0
    holdings_score = min(n_holdings, 10) / 10.0 * 3.0
    hhi_score      = (1.0 - min(hhi, 1.0)) * 2.0
    warning_penalty = len(allocation.get("concentration_warnings", [])) * 0.3

    score = round(max(0.0, min(10.0, sector_score + holdings_score + hhi_score - warning_penalty)), 1)
    label = next(lbl for threshold, lbl in _DIV_LABELS if score >= threshold)
    return score, label


def _compute_portfolio_health(user):
    close_old_connections()
    try:
        raw_holdings = list(
            Holding.objects
            .filter(user=user)
            .select_related("symbol")
            .values(
                "id", "symbol_id",
                "symbol__ticker", "symbol__company_name", "symbol__sector",
                "quantity", "avg_buy_price",
            )
        )
        if not raw_holdings:
            return None

        tickers  = [h["symbol__ticker"] for h in raw_holdings]
        live_map = _fetch_live(tickers)
        sig_map  = _fetch_signals(tickers)
        fc_map   = _fetch_forecasts(tickers)

        holdings   = _build_enriched(raw_holdings, live_map, sig_map, fc_map, {})
        summary    = _section_summary(holdings)
        health     = _section_health(holdings)
        allocation = _section_allocation(holdings)

        high_count = sum(
            (1 if h["action"] == "SELL" and h["pnl_pct"] < 0 else 0)
            + (1 if h["forecast_direction"] == "DOWN" and (h["forecast_confidence"] or 0) > 0.90 else 0)
            for h in holdings
        )
        risk = _section_risk(holdings, high_count)

        div_score, div_label = _diversification_score(holdings, allocation)

        # Raw analytics labels — same fields as GET /portfolio/analytics/ (health + risk).
        health_label = health["label"]
        overall_risk = risk["overall_risk"]

        return {
            "health_label":          health_label,
            "score":                 health["score"],
            "raw_score":             health.get("raw_score"),
            "primary_driver":        health.get("primary_driver"),
            "overall_risk":          overall_risk,
            "downside_exposure_pct": risk.get("downside_exposure_pct"),
            "label":                 health_label,
            "total_value":           summary["total_portfolio_value"],
            "todays_change_pct":     round(summary["todays_total_pct"], 4),
            "risk_level":            overall_risk,
            "risk_sublabel":         (
                f"{risk.get('downside_exposure_pct', 0):.1f}% downside exposure"
            ),
            "diversification_score": div_score,
            "diversification_label": div_label,
            "total_holdings":        summary["total_holdings"],
        }
    finally:
        close_old_connections()


def _fetch_portfolio_health(user):
    cache_key = f"dashboard:portfolio_health:v2:{user.id}"
    return db_cache_get_or_compute(
        cache_key, lambda: _compute_portfolio_health(user), _TTL_SHORT
    )


# ── API Views ─────────────────────────────────────────────────────────────────

class DashboardStocksView(APIView):
    """GET /api/v1/dashboard/stocks/

    Query params:
      sector (str, default "all") — filter rising_stars by sector
      limit  (int, default 10)   — max rising_stars to return
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        sector = request.query_params.get("sector", "all")
        try:
            limit = int(request.query_params.get("limit", 10))
        except (ValueError, TypeError):
            limit = 10

        with ThreadPoolExecutor(max_workers=7) as pool:
            f_summary    = pool.submit(_fetch_market_summary)
            f_mood       = pool.submit(_fetch_market_mood)
            f_pick       = pool.submit(_fetch_ai_pick)
            f_stars      = pool.submit(_fetch_rising_stars, sector, limit)
            f_sectors    = pool.submit(_fetch_sector_performance)
            f_performers = pool.submit(_fetch_top_performers)
            f_ph         = pool.submit(_fetch_portfolio_health, request.user)

        return Response({
            "market_summary":     f_summary.result(),
            "market_mood":        f_mood.result(),
            "ai_pick":            f_pick.result(),
            "rising_stars":       f_stars.result(),
            "sector_performance": f_sectors.result(),
            "top_performers":     f_performers.result(),
            "portfolio_health":   f_ph.result(),
            "generated_at":       timezone.now().isoformat(),
        })


class DashboardNewsView(APIView):
    """GET /api/v1/dashboard/news/

    Returns 3 news articles — one per sentiment:
      EXCELLENT  → highest score in last 7 days
      VERY_BAD   → lowest  score in last 7 days
      NEUTRAL    → most recent in last 7 days
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        items = db_cache_get_or_compute(
            "dashboard:news:v4", self._compute, _TTL_SHORT
        )
        return Response({"total": len(items), "items": items})

    def _compute(self):
        close_old_connections()
        try:
            seven_days_ago = timezone.now() - timedelta(days=7)
            base_qs = NewsSentiment.objects.filter(published_at__gte=seven_days_ago)
            fields  = ("id", "ticker", "headline", "source", "link", "sentiment", "score", "published_at")

            raw_picks = [
                base_qs.filter(sentiment="EXCELLENT").order_by("-score").values(*fields).first(),
                base_qs.filter(sentiment="VERY_BAD").order_by("score").values(*fields).first(),
                base_qs.filter(sentiment="NEUTRAL").order_by("-published_at").values(*fields).first(),
            ]
            raw_picks = [p for p in raw_picks if p]

            tickers = list({p["ticker"] for p in raw_picks})
            sym_map = {s.ticker: s for s in StockSymbol.objects.filter(ticker__in=tickers)}

            items = []
            for article in raw_picks:
                sym   = sym_map.get(article["ticker"])
                pub   = article["published_at"]
                score = float(article["score"] or 0)
                items.append({
                    "id":           str(article["id"]),
                    "symbol":       article["ticker"],
                    "symbol_name":  sym.company_name if sym else article["ticker"],
                    "headline":     article["headline"],
                    "source":       article["source"],
                    "link":         article["link"],
                    "sentiment":    article["sentiment"],
                    "score":        score,
                    "tone":         _tone(score),
                    "published_at": pub.isoformat() if hasattr(pub, "isoformat") else str(pub),
                    "time_ago":     _time_ago(pub),
                })
            return items
        finally:
            close_old_connections()
