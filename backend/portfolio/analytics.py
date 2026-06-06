"""
Portfolio Analytics — full computation for GET /api/v1/portfolio/analytics/

DB tables used (exact column names verified from models.py):
  portfolio_holdings  → PortfolioHolding
  stock_symbol        → StockSymbol  (field: sector, not industry)
  live_market_data    → LiveMarketData  (field: close, change_pct, rsi14, volatility20d)
  stock_signal        → StockSignal  (serves as health_scores; health_label is 5-class
                         VERY_BAD/BAD/NEUTRAL/GOOD/EXCELLENT; blended_score is the [-1,1]
                         numeric health metric; contributions JSON = {Forecast,Sentiment,Technicals})
  stock_forecast      → StockForecast  (fields: direction, confidence, expected_change_pct)
  news_sentiment      → NewsSentiment  (aggregated per ticker; no pre-built news_data table)

Design:
  1. Fetch raw holdings (main thread, sequential — tickers needed before parallel fetch)
  2. Parallel fetch live, signals, forecasts, news aggregation (ThreadPoolExecutor)
  3. Enrich all holdings in-memory (single pass)
  4. Compute all 8 sections from enriched data (pure in-memory, each fault-isolated)
"""

from collections import defaultdict
from datetime import timedelta

from django.db import close_old_connections
from django.db.models import Avg, Count
from django.utils import timezone

from core.models import LiveMarketData, NewsSentiment, StockForecast, StockSignal
from portfolio.models import PortfolioHolding


_SEV = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


def _sev(s: str) -> int:
    return _SEV.get(s, 3)


def _normalize_action(signal: str | None) -> str | None:
    """Map STRONG_BUY/BUY → BUY, STRONG_SELL/SELL → SELL, HOLD → HOLD."""
    if signal in ("BUY", "STRONG_BUY"):
        return "BUY"
    if signal in ("SELL", "STRONG_SELL"):
        return "SELL"
    if signal == "HOLD":
        return "HOLD"
    return None


def _sentiment_label(score: float) -> str:
    if score > 0.5:   return "Very Positive"
    if score > 0.3:   return "Positive"
    if score > 0.1:   return "Mixed"
    if score > -0.1:  return "Neutral"
    if score > -0.3:  return "Negative"
    return "Very Negative"


def _tone(score: float) -> str:
    if score > 0.1:  return "positive"
    if score < -0.1: return "negative"
    return "neutral"


def _time_ago(dt) -> str:
    seconds = int((timezone.now() - dt).total_seconds())
    if seconds < 3600:  return f"{max(0, seconds // 60)}m ago"
    if seconds < 86400: return f"{seconds // 3600}h ago"
    return f"{seconds // 86400}d ago"


# ── Per-thread DB fetchers (each manages its own connection lifecycle) ─────────

def _fetch_live(tickers: list) -> dict:
    """Latest LiveMarketData snapshot per ticker (one row per ticker in DB)."""
    close_old_connections()
    try:
        return {
            lmd.ticker: lmd
            for lmd in LiveMarketData.objects
            .filter(ticker__in=tickers)
            .order_by("ticker", "-date")
            .distinct("ticker")
        }
    finally:
        close_old_connections()


def _fetch_signals(tickers: list) -> dict:
    """Latest StockSignal per ticker — this table serves as health_scores."""
    close_old_connections()
    try:
        return {
            sig.ticker: sig
            for sig in StockSignal.objects
            .filter(ticker__in=tickers)
            .order_by("ticker", "-generated_at")
            .distinct("ticker")
        }
    finally:
        close_old_connections()


def _fetch_forecasts(tickers: list) -> dict:
    """Latest StockForecast per ticker (stock_forecast table, not stock_forecasting)."""
    close_old_connections()
    try:
        return {
            fc.ticker: fc
            for fc in StockForecast.objects
            .filter(ticker__in=tickers)
            .order_by("ticker", "-forecast_date")
            .distinct("ticker")
        }
    finally:
        close_old_connections()


def _fetch_news_agg(tickers: list) -> dict:
    """
    Aggregate news_sentiment per ticker.
    There is no pre-built news_data table; we aggregate from news_sentiment.
    Returns dict: ticker → {articles_count, recent_7d, avg_sentiment_score, distribution}
    """
    close_old_connections()
    try:
        seven_days_ago = timezone.now() - timedelta(days=7)

        total_counts = {
            r["ticker"]: r["n"]
            for r in NewsSentiment.objects
            .filter(ticker__in=tickers)
            .values("ticker")
            .annotate(n=Count("id"))
        }

        recent_agg = {
            r["ticker"]: r
            for r in NewsSentiment.objects
            .filter(ticker__in=tickers, published_at__gte=seven_days_ago)
            .values("ticker")
            .annotate(recent_7d=Count("id"), avg_score=Avg("score"))
        }

        dist_map: dict = defaultdict(dict)
        for r in (
            NewsSentiment.objects
            .filter(ticker__in=tickers)
            .values("ticker", "sentiment")
            .annotate(n=Count("id"))
        ):
            dist_map[r["ticker"]][r["sentiment"]] = r["n"]

        articles_raw = list(
            NewsSentiment.objects
            .filter(ticker__in=tickers, published_at__gte=seven_days_ago)
            .values("id", "ticker", "headline", "source", "link", "sentiment", "score", "published_at")
            .order_by("-published_at")
        )
        articles_map: dict = defaultdict(list)
        for a in articles_raw:
            articles_map[a["ticker"]].append(a)

        result = {}
        for ticker in tickers:
            dist = dist_map.get(ticker, {})
            rec  = recent_agg.get(ticker, {})
            result[ticker] = {
                "articles_count":      total_counts.get(ticker, 0),
                "recent_7d":           int(rec.get("recent_7d") or 0),
                "avg_sentiment_score": float(rec.get("avg_score") or 0.0),
                "distribution": {
                    "EXCELLENT": dist.get("EXCELLENT", 0),
                    "GOOD":      dist.get("GOOD",      0),
                    "NEUTRAL":   dist.get("NEUTRAL",   0),
                    "BAD":       dist.get("BAD",       0),
                    "VERY_BAD":  dist.get("VERY_BAD",  0),
                },
                "articles": articles_map.get(ticker, []),
            }
        return result
    finally:
        close_old_connections()


# ── Enrichment ─────────────────────────────────────────────────────────────────

def _build_enriched(raw_holdings, live_map, sig_map, fc_map, news_map) -> list:
    """
    Merge raw holdings (DB .values() rows) with all supporting data in-memory.
    Returns a list of enriched holding dicts.
    position_weight is initialised to 0.0 and filled after total_portfolio_value is known.

    Field-name notes:
      StockSymbol.sector    → exposed as 'industry' (field is named sector in DB)
      LiveMarketData.close  → current_price
      LiveMarketData.change_pct = (close − prior_close) / prior_close × 100
                            → last_close derived as close / (1 + change_pct/100)
      StockSignal.blended_score → health_score (numeric health metric in [−1, 1])
      StockSignal.health_label  → 5-class: VERY_BAD/BAD/NEUTRAL/GOOD/EXCELLENT
      LiveMarketData.volatility20d → confirmed field in live_market_data table
    """
    enriched = []
    for h in raw_holdings:
        ticker = h["symbol__ticker"]
        lmd    = live_map.get(ticker)
        sig    = sig_map.get(ticker)
        fc     = fc_map.get(ticker)
        news   = news_map.get(ticker, {})

        price_stale = lmd is None
        if lmd is not None:
            current_price = float(lmd.close)
            open_px = float(lmd.open_price) if lmd.open_price is not None else None
            chg     = lmd.change_pct
            # Prefer open_price as the intraday reference; fall back to change_pct derivation
            # if open is missing, and finally to current_price if both are unavailable.
            if open_px is not None and open_px > 0:
                last_close = open_px
            elif chg is not None and chg != 0:
                last_close = current_price / (1 + chg / 100)
            else:
                last_close = current_price
            rsi14         = lmd.rsi14
            volatility20d = lmd.volatility20d
        else:
            # No live data — fall back to avg_buy_price, flag as stale
            current_price = float(h["avg_buy_price"])
            last_close    = current_price
            rsi14         = None
            volatility20d = None

        qty    = float(h["quantity"])
        avg_px = float(h["avg_buy_price"])

        cur_val  = qty * current_price
        cost     = qty * avg_px
        unr_pnl  = cur_val - cost
        pnl_pct  = (unr_pnl / cost * 100) if cost else 0.0
        tod_chg  = qty * (current_price - last_close)
        tod_pct  = ((current_price - last_close) / last_close * 100) if last_close else 0.0

        enriched.append({
            "id":         str(h["id"]),
            "symbol_id":  str(h["symbol_id"]),
            "symbol":     ticker,
            "name":       h["symbol__company_name"],
            "industry":   h["symbol__sector"] or "Unknown",
            "quantity":   qty,
            "avg_buy_price": avg_px,
            "current_price": current_price,
            "last_close":    last_close,
            "price_stale":   price_stale,
            "current_value": cur_val,
            "cost_basis":    cost,
            "unrealized_pnl": unr_pnl,
            "pnl_pct":        round(pnl_pct, 4),
            "todays_change":  tod_chg,
            "todays_change_pct": round(tod_pct, 4),
            "position_weight": 0.0,
            # signals (StockSignal)
            "action":            _normalize_action(sig.signal if sig else None),
            "signal_confidence": sig.suggestion_confidence if sig else None,
            "blended_score":     sig.blended_score if sig else None,
            "reason":            sig.reason if sig else None,
            "dominant_sentiment": sig.dominant_sentiment if sig else None,
            "health_label":      sig.health_label if sig else None,
            "health_score":      sig.blended_score if sig else None,
            "contributions":     sig.contributions if sig else None,
            # forecast (StockForecast)
            "forecast_direction":  fc.direction if fc else None,
            "forecast_change_pct": fc.expected_change_pct if fc else None,
            "forecast_confidence": fc.confidence if fc else None,
            # technicals (from LiveMarketData)
            "rsi14":         rsi14,
            "volatility20d": volatility20d,
            # news aggregated from news_sentiment
            "articles_count":      news.get("articles_count", 0),
            "recent_7d":           news.get("recent_7d", 0),
            "avg_sentiment_score": news.get("avg_sentiment_score", 0.0),
            "news_distribution":   news.get("distribution", {}),
            "news_articles":       news.get("articles", []),
        })

    total_val = sum(h["current_value"] for h in enriched)
    if total_val > 0:
        for h in enriched:
            h["position_weight"] = round(h["current_value"] / total_val * 100, 4)

    return enriched


# ── Section 1: Summary ─────────────────────────────────────────────────────────

def _section_summary(holdings: list) -> dict:
    total_val  = sum(h["current_value"] for h in holdings)
    total_cost = sum(h["cost_basis"]    for h in holdings)
    total_unr  = total_val - total_cost
    total_pnl  = (total_unr / total_cost * 100) if total_cost else 0.0
    tod_change = sum(h["todays_change"] for h in holdings)
    prev_total = sum(h["quantity"] * h["last_close"] for h in holdings)
    tod_pct    = (tod_change / prev_total * 100) if prev_total else 0.0

    return {
        "total_portfolio_value": round(total_val,  2),
        "total_cost_basis":      round(total_cost, 2),
        "total_unrealized_pnl":  round(total_unr,  2),
        "total_pnl_pct":         round(total_pnl,  4),
        "todays_total_change":   round(tod_change, 2),
        "todays_total_pct":      round(tod_pct,    4),
        "total_holdings":        len(holdings),
        "updated_at":            timezone.now().isoformat(),
    }


# ── Section 2: Health ──────────────────────────────────────────────────────────

def _section_health(holdings: list) -> dict:
    total_val = sum(h["current_value"] for h in holdings)
    if total_val == 0:
        return {"score": 50, "raw_score": 0.0, "label": "NEUTRAL", "primary_driver": "Technicals"}

    # Weighted blended_score; health_score = blended_score ([-1, 1] numeric health metric)
    raw = sum((h["health_score"] or 0) * h["current_value"] for h in holdings) / total_val

    if   raw >  0.3: label = "BULLISH"
    elif raw > -0.3: label = "NEUTRAL"
    else:            label = "BEARISH"

    display = max(0, min(100, round(((raw + 1) / 2) * 100)))

    # Primary driver from contributions JSON: {Forecast: %, Sentiment: %, Technicals: %}
    totals: dict = defaultdict(float)
    for h in holdings:
        contrib = h.get("contributions")
        if contrib and isinstance(contrib, dict):
            w = h["current_value"] / total_val
            for comp, pct in contrib.items():
                totals[comp] += (pct or 0) * w

    known = {"Technicals", "Sentiment", "Forecast"}
    if totals:
        driver = max(totals, key=lambda k: totals[k])
        primary_driver = driver if driver in known else "Technicals"
    else:
        primary_driver = "Technicals"

    return {
        "score":          display,
        "raw_score":      round(raw, 4),
        "label":          label,
        "primary_driver": primary_driver,
    }


# ── Section 3: Allocation ──────────────────────────────────────────────────────

def _section_allocation(holdings: list) -> dict:
    total_val = sum(h["current_value"] for h in holdings)
    if total_val == 0:
        return {"total_holdings": 0, "sectors": [], "concentration_warnings": []}

    buckets: dict = defaultdict(lambda: {"value": 0.0, "count": 0})
    for h in holdings:
        buckets[h["industry"]]["value"] += h["current_value"]
        buckets[h["industry"]]["count"] += 1

    sectors = sorted(
        [
            {
                "industry":   ind,
                "value":      round(d["value"], 2),
                "weight_pct": round(d["value"] / total_val * 100, 4),
                "stock_count": d["count"],
            }
            for ind, d in buckets.items()
        ],
        key=lambda s: s["value"],
        reverse=True,
    )

    warnings = []
    for s in sectors:
        if s["weight_pct"] > 40:
            warnings.append({
                "type":     "SECTOR_CONCENTRATION",
                "message":  f"{s['industry']} is {s['weight_pct']:.1f}% of your portfolio",
                "severity": "MEDIUM",
            })
    for h in holdings:
        if h["position_weight"] > 30:
            warnings.append({
                "type":     "STOCK_CONCENTRATION",
                "message":  f"{h['symbol']} is {h['position_weight']:.1f}% of your portfolio",
                "severity": "MEDIUM",
            })

    return {
        "total_holdings":        len(holdings),
        "sectors":               sectors,
        "concentration_warnings": warnings,
    }


# ── Section 4: Holdings ────────────────────────────────────────────────────────

def _fmt(h: dict) -> dict:
    return {
        "id":                h["id"],
        "symbol_id":         h["symbol_id"],
        "symbol":            h["symbol"],
        "name":              h["name"],
        "industry":          h["industry"],
        "quantity":          h["quantity"],
        "avg_buy_price":     h["avg_buy_price"],
        "current_price":     h["current_price"],
        "current_value":     round(h["current_value"],  2),
        "cost_basis":        round(h["cost_basis"],     2),
        "unrealized_pnl":    round(h["unrealized_pnl"], 2),
        "pnl_pct":           h["pnl_pct"],
        "todays_change_pct": h["todays_change_pct"],
        "position_weight":   h["position_weight"],
        "forecast_change_pct": h["forecast_change_pct"],
        "forecast_direction":  h["forecast_direction"],
        "forecast_confidence": h["forecast_confidence"],
        "health_label":      h["health_label"],
        "health_score":      h["health_score"],
        "rsi14":             h["rsi14"],
        "action":            h["action"],
        "signal_confidence": h["signal_confidence"],
        "blended_score":     h["blended_score"],
        "reason":            h["reason"],
        "dominant_sentiment": h["dominant_sentiment"],
        "price_stale":       h["price_stale"],
    }


def _section_holdings(holdings: list) -> dict:
    by_val = sorted(holdings, key=lambda h: h["current_value"], reverse=True)
    return {
        "featured_holdings": [_fmt(h) for h in by_val[:5]],
        "all_holdings":      [_fmt(h) for h in by_val],
    }


# ── Section 5: Recommendations ─────────────────────────────────────────────────

def _section_recommendations(holdings: list) -> dict:
    """
    One recommendation per holding — first matching rule wins.
    health_label BULLISH equivalent: GOOD or EXCELLENT
    (StockSignal.health_label is 5-class, not 3-class; GOOD/EXCELLENT map to BULLISH)
    """
    recs = []
    for h in holdings:
        action  = h["action"]
        pnl     = h["pnl_pct"]
        bullish = h["health_label"] in ("GOOD", "EXCELLENT")
        fc_dir  = h["forecast_direction"]
        fc_conf = h["forecast_confidence"]
        rsi     = h["rsi14"]

        if action == "SELL" and pnl < 0:
            lab, sev, col = "Cut Loss — Exit Signal", "HIGH", "red"
        elif action == "SELL" and pnl >= 0:
            lab, sev, col = "Consider Taking Profit", "MEDIUM", "amber"
        elif action == "BUY" and bullish:
            lab, sev, col = "Strong Hold — Add More", "LOW", "green"
        elif action == "HOLD" and bullish:
            lab, sev, col = "Hold — Positive Outlook", "LOW", "green"
        elif fc_dir == "DOWN" and fc_conf is not None and fc_conf > 0.90:
            lab, sev, col = "High Confidence Down — Review Position", "HIGH", "red"
        elif rsi is not None and rsi > 70:
            lab, sev, col = "Overbought — Watch for Exit", "MEDIUM", "amber"
        elif rsi is not None and rsi < 30:
            lab, sev, col = "Oversold — Possible Bounce", "LOW", "blue"
        else:
            lab, sev, col = "Monitor Position", "LOW", "gray"

        recs.append({
            "symbol":          h["symbol"],
            "name":            h["name"],
            "label":           lab,
            "severity":        sev,
            "color":           col,
            "reason":          h["reason"],
            "pnl_pct":         h["pnl_pct"],
            "current_value":   round(h["current_value"], 2),
            "position_weight": h["position_weight"],
        })

    recs.sort(key=lambda r: _sev(r["severity"]))
    return {"recommendations": recs}




# ── Section 7: Risk ────────────────────────────────────────────────────────────

def _section_risk(holdings: list, high_count: int) -> dict:
    total_val = sum(h["current_value"] for h in holdings)
    if total_val == 0:
        return {
            "overall_risk":          "LOW",
            "downside_exposure_pct": 0.0,
            "divergence_count":      0,
            "divergent_symbols":     [],
            "weighted_volatility":   None,
        }

    down_val = sum(
        h["current_value"] for h in holdings
        if h["forecast_direction"] == "DOWN"
        and h["forecast_confidence"] is not None
        and h["forecast_confidence"] > 0.85
    )
    downside_pct = down_val / total_val * 100

    divergent = [
        h["symbol"] for h in holdings
        if (h["forecast_direction"] == "DOWN" and h["action"] == "BUY")
        or (h["forecast_direction"] == "UP"   and h["action"] == "SELL")
    ]

    # volatility20d confirmed in live_market_data (LiveMarketData model)
    vol_hs = [h for h in holdings if h.get("volatility20d") is not None]
    if vol_hs:
        weighted_volatility = round(
            sum(h["volatility20d"] * h["current_value"] for h in vol_hs) / total_val, 4
        )
    else:
        weighted_volatility = None

    div_count = len(divergent)
    if high_count >= 2 or downside_pct > 40:
        risk = "HIGH"
    elif high_count == 1 or downside_pct > 20 or div_count > 2:
        risk = "MODERATE"
    else:
        risk = "LOW"

    return {
        "overall_risk":          risk,
        "downside_exposure_pct": round(downside_pct, 4),
        "divergence_count":      div_count,
        "divergent_symbols":     divergent,
        "weighted_volatility":   weighted_volatility,
    }


# ── Section 7: News ────────────────────────────────────────────────────────────

def _section_news(holdings: list) -> dict:
    all_articles = []
    for h in holdings:
        sym  = h["symbol"]
        name = h["name"]
        for a in h.get("news_articles", []):
            pub = a["published_at"]
            all_articles.append({
                "id":           str(a["id"]),
                "symbol":       sym,
                "symbol_name":  name,
                "headline":     a["headline"],
                "source":       a["source"],
                "link":         a["link"],
                "sentiment":    a["sentiment"],
                "score":        a["score"],
                "tone":         _tone(a["score"]),
                "published_at": pub.isoformat() if hasattr(pub, "isoformat") else str(pub),
                "time_ago":     _time_ago(pub),
            })

    all_articles.sort(key=lambda x: x["published_at"], reverse=True)
    return {"total": len(all_articles), "items": all_articles}


# ── Main entry point ───────────────────────────────────────────────────────────

def compute_portfolio_analytics(user) -> dict:
    """
    Full portfolio analytics for a single authenticated user.
    All DB reads happen before section computation; sections are pure in-memory.
    """
    errors  = []
    user_id = str(user.id)
    now_iso = timezone.now().isoformat

    # ── Step 1: Raw holdings (sequential — tickers needed for parallel fetch) ──
    try:
        raw_holdings = list(
            PortfolioHolding.objects
            .filter(user=user)
            .select_related("symbol")
            .values(
                "id", "symbol_id",
                "symbol__ticker",
                "symbol__company_name",
                "symbol__sector",
                "quantity",
                "avg_buy_price",
            )
        )
    except Exception as exc:
        return {
            "success":       True,
            "user_id":       user_id,
            "has_holdings":  False,
            "errors":        [{"section": "holdings_fetch", "error": str(exc)}],
            "generated_at":  now_iso(),
        }

    if not raw_holdings:
        ts = now_iso()
        return {
            "success":      True,
            "user_id":      user_id,
            "has_holdings": False,
            "summary": {
                "total_portfolio_value": 0,
                "total_cost_basis":      0,
                "total_unrealized_pnl":  0,
                "total_pnl_pct":         0,
                "todays_total_change":   0,
                "todays_total_pct":      0,
                "total_holdings":        0,
                "updated_at":            ts,
            },
            "health":          None,
            "allocation":      None,
            "holdings":        {"featured_holdings": [], "all_holdings": []},
            "recommendations": {"recommendations": []},
            "risk":         None,
            "news":         {"total": 0, "items": []},
            "generated_at": ts,
        }

    tickers = [h["symbol__ticker"] for h in raw_holdings]

    # ── Step 2: Sequential DB fetches (Supabase session-mode pool is limited) ──
    try:
        live_map = _fetch_live(tickers)
        sig_map  = _fetch_signals(tickers)
        fc_map   = _fetch_forecasts(tickers)
        news_map = _fetch_news_agg(tickers)
    except Exception as exc:
        errors.append({"section": "data_fetch", "error": str(exc)})
        live_map = sig_map = fc_map = news_map = {}

    # ── Step 3: Enrich in-memory ──────────────────────────────────────────────
    try:
        holdings = _build_enriched(raw_holdings, live_map, sig_map, fc_map, news_map)
    except Exception as exc:
        errors.append({"section": "enrichment", "error": str(exc)})
        holdings = []

    if not holdings:
        result = {
            "success":       True,
            "user_id":       user_id,
            "has_holdings":  False,
            "generated_at":  now_iso(),
        }
        if errors:
            result["errors"] = errors
        return result

    # ── Step 4: Compute sections (each fault-isolated) ────────────────────────
    def safe(name, fn, *args):
        try:
            return fn(*args)
        except Exception as exc:
            errors.append({"section": name, "error": str(exc)})
            return None

    summary         = safe("summary",         _section_summary,         holdings)
    health          = safe("health",          _section_health,          holdings)
    allocation      = safe("allocation",      _section_allocation,      holdings)
    holdings_sec    = safe("holdings",        _section_holdings,        holdings)
    recommendations = safe("recommendations", _section_recommendations, holdings)

    high_count = sum(
        (1 if h["action"] == "SELL" and h["pnl_pct"] < 0 else 0)
        + (1 if h["forecast_direction"] == "DOWN" and (h["forecast_confidence"] or 0) > 0.90 else 0)
        + (1 if h.get("dominant_sentiment") in ("VERY_BAD", "BAD") else 0)
        for h in holdings
    )
    risk = safe("risk", _section_risk, holdings, high_count)
    news = safe("news", _section_news, holdings)

    result = {
        "success":         True,
        "user_id":         user_id,
        "has_holdings":    True,
        "summary":         summary,
        "health":          health,
        "allocation":      allocation,
        "holdings":        holdings_sec,
        "recommendations": recommendations,
        "risk":            risk,
        "news":            news,
        "generated_at":    now_iso(),
    }
    if errors:
        result["errors"] = errors
    return result
