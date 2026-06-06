"""Workflow A + B orchestrators (replaces n8n).

Each public function below is the Python equivalent of one of the
two n8n workflow JSON files:

  dispatch_top_pick(window)      — Workflow A · Top Pick
  dispatch_digest(window)        — Workflow A · Digest (sent 2 min after top)
  dispatch_position_alerts(window) — Workflow B · holdings × SELL/STRONG_SELL

All three are designed to be called from a Celery task — they're
synchronous, read from DB / live_market_data / news_sentiment, call
Gemini for summarisation, and send mail via `alerts.notifications.email`.
They write Alert + AlertDetail + Notification + AlertLog rows so the
in-app feed mirrors what the user saw in email.

`window` is one of 'PRE_MARKET' / 'MID_SESSION' / 'POST_MARKET'.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from typing import Iterable

from django.contrib.auth import get_user_model
from django.utils import timezone

from alerts import formatters, summarizer
from alerts.models import Alert, AlertDetail, AlertLog, Notification
from alerts.notifications.email import send_email
from alerts.notifications.inapp import create_in_app_notification
from alerts.notifications.push import send_push_notification
from core.models import LiveMarketData, NewsSentiment, StockSignal
from portfolio.models import PortfolioHolding
from users.models import DeviceToken, NotificationPreference

logger = logging.getLogger(__name__)
User = get_user_model()

# Window → NotificationPreference boolean column
WINDOW_FIELD = {
    "PRE_MARKET": "pre_market",
    "MID_SESSION": "mid_session",
    "POST_MARKET": "post_market",
}

# Window → human label used in subject + email body
WINDOW_LABEL = {
    "PRE_MARKET": "Pre-Market Outlook",
    "MID_SESSION": "Mid-Session Update",
    "POST_MARKET": "Post-Market Recap",
}


# ----------------------------------------------------- helpers / data fetch
def _signal_to_dict(s: StockSignal) -> dict:
    """Shape we hand to formatters + summarizer — flat dict, same keys
    the n8n workflows used."""
    return {
        "ticker": s.ticker,
        "signal": s.signal,
        "suggestion_confidence": s.suggestion_confidence,
        "confidence": float(s.confidence) if s.confidence is not None else None,
        "blended_score": float(s.blended_score) if s.blended_score is not None else None,
        "forecast_signed_score": (
            float(s.forecast_signed_score)
            if s.forecast_signed_score is not None
            else None
        ),
        "signal_strength": (
            float(s.signal_strength) if s.signal_strength is not None else None
        ),
        "reason": s.reason,
        "health_label": s.health_label,
        "horizon": s.horizon,
        "dominant_sentiment": s.dominant_sentiment,
        "contributions": s.contributions,
        "generated_at": s.generated_at.isoformat() if s.generated_at else None,
    }


def _live_to_dict(lmd: LiveMarketData | None) -> dict:
    if not lmd:
        return {}
    return {
        "ticker": lmd.ticker,
        "close": float(lmd.close) if lmd.close is not None else None,
        "change_pct": float(lmd.change_pct) if lmd.change_pct is not None else None,
        "rsi14": float(lmd.rsi14) if lmd.rsi14 is not None else None,
        "ma20": float(lmd.ma20) if lmd.ma20 is not None else None,
        "ma50": float(lmd.ma50) if lmd.ma50 is not None else None,
        "ma200": float(lmd.ma200) if lmd.ma200 is not None else None,
        "volatility20d": (
            float(lmd.volatility20d) if lmd.volatility20d is not None else None
        ),
        "volume_ratio": (
            float(lmd.volume_ratio) if lmd.volume_ratio is not None else None
        ),
        "eps": float(lmd.eps) if lmd.eps is not None else None,
        "date": lmd.date.isoformat() if lmd.date else None,
    }


def _news_to_dict(rows: Iterable[NewsSentiment]) -> list:
    return [
        {
            "headline": n.headline,
            "link": n.link,
            "source": n.source,
            "sentiment": n.sentiment,
            "score": float(n.score) if n.score is not None else None,
            "published_at": n.published_at.isoformat() if n.published_at else None,
        }
        for n in rows
    ]


def _latest_signals(*, signals_in: list[str]) -> list[StockSignal]:
    """Latest StockSignal row per ticker where signal ∈ signals_in."""
    return list(
        StockSignal.objects.filter(signal__in=signals_in)
        .order_by("ticker", "-generated_at")
        .distinct("ticker")
    )


def _eligible_users_for_window(window: str) -> list[NotificationPreference]:
    """Users opted into THIS window AND at least one channel."""
    field = WINDOW_FIELD[window]
    return list(
        NotificationPreference.objects.filter(
            **{field: True},
        )
        .filter(
            # in-app is always allowed (DB row, no channel cost); email
            # gating happens at send time.
            in_app_enabled=True,
        )
        .select_related("user")
    )


def _latest_live(ticker: str) -> LiveMarketData | None:
    return LiveMarketData.objects.filter(ticker=ticker).order_by("-updated_at").first()


def _top_news(ticker: str, limit: int = 2) -> list[NewsSentiment]:
    return list(
        NewsSentiment.objects.filter(ticker=ticker)
        .order_by("-published_at")[:limit]
    )


# ----------------------------------------------------- write DB row helpers
def _persist_alert(
    *,
    user,
    signal: dict,
    signal_3class: str,
    summary: str,
    alert_window: str,
    notification_type: str,
    payload: dict,
) -> Alert | None:
    """Write Alert + AlertDetail + Notification in one shot. Returns Alert."""
    try:
        alert = Alert.objects.create(
            user=user,
            ticker=signal["ticker"],
            symbols=[signal["ticker"]],
            signal=signal_3class,
            reason=summary,
            alert_window=alert_window,
        )
        AlertDetail.objects.create(alert=alert, payload=payload)
        create_in_app_notification(
            user=user,
            alert=alert,
            notification_type=notification_type,
            category="stock" if notification_type != "DIGEST" else "digest",
        )
        return alert
    except Exception:
        logger.exception("persist_alert failed for user=%s", user.id)
        return None


def _log_send(alert: Alert, channel: str, result: dict) -> None:
    """Write an AlertLog row reflecting the send outcome."""
    if result.get("status") == "SKIPPED":
        # Not a delivery failure — record as PENDING with the reason in
        # error_message for audit. Keeps the SENT/FAILED split clean.
        status = AlertLog.Status.PENDING
        err = result.get("reason", "")
    elif result.get("status") == "SENT":
        status = AlertLog.Status.SENT
        err = ""
    else:
        status = AlertLog.Status.FAILED
        err = result.get("error", "")
    AlertLog.objects.create(
        alert=alert,
        channel=channel,
        status=status,
        error_message=err,
        sent_at=timezone.now() if status == AlertLog.Status.SENT else None,
    )


def _send_email_for(prefs: NotificationPreference, *, alert: Alert, subject, html, plain):
    """Send one email + write the AlertLog row. No-op if email disabled."""
    if not prefs.email_enabled or not prefs.user.email:
        return
    result = send_email(prefs.user.email, subject, html, plain)
    _log_send(alert, AlertLog.Channel.EMAIL, result)


# ============================================================ Workflow A
def dispatch_top_pick(window: str) -> dict:
    """STRONG_BUY + HIGH confidence → highest blended_score = Top Pick.
    One alert per eligible user."""
    label = WINDOW_LABEL[window]
    signals = [
        s for s in _latest_signals(signals_in=["STRONG_BUY"])
        if s.suggestion_confidence == "HIGH"
    ]
    if not signals:
        logger.info("[%s] no STRONG_BUY HIGH signals — top pick skipped", window)
        return {"sent": 0, "reason": "no signals"}

    signals.sort(key=lambda s: (s.blended_score or 0), reverse=True)
    top = signals[0]
    sig_dict = _signal_to_dict(top)
    live_dict = _live_to_dict(_latest_live(top.ticker))
    news_dicts = _news_to_dict(_top_news(top.ticker))
    summary = summarizer.summarize_top_pick(sig_dict, live_dict, news_dicts)

    subject, html, plain = formatters.build_top_pick_email(
        sig_dict, live_dict, news_dicts, summary, label
    )

    payload = {
        "ticker": sig_dict["ticker"],
        "signal": "STRONG_BUY",
        "confidence": sig_dict["suggestion_confidence"],
        "close": live_dict.get("close"),
        "change_pct": live_dict.get("change_pct"),
        "rsi14": live_dict.get("rsi14"),
        "ma50": live_dict.get("ma50"),
        "ma200": live_dict.get("ma200"),
        "volatility20d": live_dict.get("volatility20d"),
        "news": news_dicts,
        "summary": summary,
        "window_label": label,
        "type": "TOP_PICK",
    }

    sent = 0
    for prefs in _eligible_users_for_window(window):
        alert = _persist_alert(
            user=prefs.user,
            signal=sig_dict,
            signal_3class=Alert.Signal.BUY,
            summary=summary,
            alert_window=window,
            notification_type=Notification.Type.TOP_PICK,
            payload=payload,
        )
        if not alert:
            continue
        _send_email_for(prefs, alert=alert, subject=subject, html=html, plain=plain)

        tokens = list(
            DeviceToken.objects.filter(user=prefs.user).values_list("token", flat=True)
        )
        push_result = send_push_notification(
            tokens=tokens,
            title=f"{sig_dict['ticker']} — STRONG_BUY",
            body=summary[:200],
            data={
                "alert_id": str(alert.id),
                "ticker": sig_dict["ticker"],
                "type": "TOP_PICK",
            },
        )
        _log_send(alert, AlertLog.Channel.PUSH, push_result)
        sent += 1

    logger.info("[%s] top pick dispatched to %d users (%s)", window, sent, top.ticker)
    return {"sent": sent, "ticker": top.ticker}


def dispatch_digest(window: str) -> dict:
    """All STRONG_BUYs OTHER THAN the top pick, summarised in one digest."""
    label = WINDOW_LABEL[window]
    signals = [
        s for s in _latest_signals(signals_in=["STRONG_BUY"])
        if s.suggestion_confidence == "HIGH"
    ]
    if len(signals) <= 1:
        logger.info("[%s] only %d STRONG_BUY — no digest", window, len(signals))
        return {"sent": 0, "reason": "nothing-to-digest"}

    signals.sort(key=lambda s: (s.blended_score or 0), reverse=True)
    # Skip the #1 (it's the Top Pick) and cap the digest at the next 20.
    # n8n was sending the *entire* remaining list — an email with 100+
    # rows is unreadable and Gmail clips long messages anyway. 20 is
    # roughly one screen on mobile.
    rest = signals[1:21]

    enriched = []
    for s in rest:
        sig_dict = _signal_to_dict(s)
        live_dict = _live_to_dict(_latest_live(s.ticker))
        enriched.append({"signal": sig_dict, "live": live_dict})

    summaries = summarizer.summarize_digest(enriched)

    subject, html, plain = formatters.build_digest_email(enriched, summaries, label)

    payload = {
        "tickers": [
            {
                "ticker": e["signal"]["ticker"],
                "close": (e["live"] or {}).get("close"),
                "change_pct": (e["live"] or {}).get("change_pct"),
                "rsi14": (e["live"] or {}).get("rsi14"),
                "summary": summaries.get(
                    e["signal"]["ticker"], e["signal"].get("reason")
                ),
            }
            for e in enriched
        ],
        "count": len(enriched),
        "window_label": label,
        "type": "DIGEST",
    }
    # The Alert row uses the literal sentinel "DIGEST" as ticker since
    # it doesn't represent any single stock. Frontend should detect
    # digest notifications via Notification.type == "DIGEST" (more
    # explicit) — but querying `Alert.ticker = 'DIGEST'` also works.
    # The full ticker list lives in `Alert.symbols`.
    sent = 0
    for prefs in _eligible_users_for_window(window):
        try:
            alert = Alert.objects.create(
                user=prefs.user,
                ticker="DIGEST",
                symbols=[e["signal"]["ticker"] for e in enriched],
                signal=Alert.Signal.BUY,
                reason=(
                    f"Digest of {len(enriched)} STRONG_BUY signals: "
                    + ", ".join(e["signal"]["ticker"] for e in enriched)
                ),
                alert_window=window,
            )
            AlertDetail.objects.create(alert=alert, payload=payload)
            create_in_app_notification(
                user=prefs.user,
                alert=alert,
                notification_type=Notification.Type.DIGEST,
                category="digest",
            )
        except Exception:
            logger.exception("digest persist failed for user=%s", prefs.user_id)
            continue
        _send_email_for(prefs, alert=alert, subject=subject, html=html, plain=plain)
        sent += 1

    logger.info("[%s] digest dispatched to %d users (%d tickers)",
                window, sent, len(enriched))
    return {"sent": sent, "digest_size": len(enriched)}


# ============================================================ Workflow B
def dispatch_position_alerts(window: str) -> dict:
    """For every PortfolioHolding whose ticker has a fresh SELL or
    STRONG_SELL signal, send a per-holder personalised alert."""
    label = WINDOW_LABEL[window]
    field = WINDOW_FIELD[window]

    signals_by_ticker = {
        s.ticker: s for s in _latest_signals(signals_in=["SELL", "STRONG_SELL"])
    }
    if not signals_by_ticker:
        logger.info("[%s] no SELL/STRONG_SELL signals — position alerts skipped",
                    window)
        return {"sent": 0, "reason": "no signals"}

    holdings = (
        PortfolioHolding.objects
        .filter(symbol__ticker__in=signals_by_ticker.keys())
        .select_related("symbol", "user")
    )

    # Pre-fetch each user's prefs (one query) to avoid N+1.
    prefs_by_user = {
        p.user_id: p
        for p in NotificationPreference.objects
        .filter(user_id__in={h.user_id for h in holdings})
    }

    # Cache live + news per ticker (multiple holders share data).
    live_cache: dict[str, dict] = {}
    news_cache: dict[str, list] = {}
    summary_cache: dict[str, str] = {}

    sent = 0
    for h in holdings:
        ticker = h.symbol.ticker
        sig = signals_by_ticker[ticker]
        prefs = prefs_by_user.get(h.user_id)
        if not prefs or not getattr(prefs, field):
            continue
        if not prefs.in_app_enabled:
            continue

        live = live_cache.setdefault(ticker, _live_to_dict(_latest_live(ticker)))
        news = news_cache.setdefault(ticker, _news_to_dict(_top_news(ticker)))
        sig_dict = _signal_to_dict(sig)

        if ticker not in summary_cache:
            summary_cache[ticker] = summarizer.summarize_position(
                sig_dict, live, news
            )
        summary = summary_cache[ticker]

        qty = float(h.quantity)
        avg_buy = float(h.avg_buy_price)
        cur = float(live.get("close") or avg_buy)
        pnl_pkr = (cur - avg_buy) * qty
        pnl_pct = ((cur - avg_buy) / avg_buy * 100) if avg_buy else 0.0

        subject, html, plain = formatters.build_position_email(
            sig_dict, live, news, summary,
            qty=qty, avg_buy=avg_buy, window_label=label,
        )

        signal_3class = (
            Alert.Signal.SELL if sig.signal in ("SELL", "STRONG_SELL") else Alert.Signal.HOLD
        )
        payload = {
            "ticker": ticker,
            "signal": sig.signal,
            "confidence": sig.suggestion_confidence,
            "qty": qty,
            "avg_buy": avg_buy,
            "current": cur,
            "pnl_pct": pnl_pct,
            "pnl_pkr": pnl_pkr,
            "close": live.get("close"),
            "change_pct": live.get("change_pct"),
            "rsi14": live.get("rsi14"),
            "ma50": live.get("ma50"),
            "ma200": live.get("ma200"),
            "volatility20d": live.get("volatility20d"),
            "news": news,
            "summary": summary,
            "window_label": label,
            "type": "POSITION_ALERT",
        }

        alert = _persist_alert(
            user=h.user,
            signal=sig_dict,
            signal_3class=signal_3class,
            summary=summary,
            alert_window=window,
            notification_type=Notification.Type.POSITION_ALERT,
            payload=payload,
        )
        if not alert:
            continue
        _send_email_for(prefs, alert=alert, subject=subject, html=html, plain=plain)

        if prefs.in_app_enabled:
            pnl_str = f"P&L {pnl_pct:+.1f}% · " if pnl_pct else ""
            tokens = list(
                DeviceToken.objects.filter(user=h.user).values_list("token", flat=True)
            )
            push_result = send_push_notification(
                tokens=tokens,
                title=f"{ticker} — {sig.signal}",
                body=f"{pnl_str}{summary[:160]}",
                data={
                    "alert_id": str(alert.id),
                    "ticker": ticker,
                    "type": "POSITION_ALERT",
                },
            )
            _log_send(alert, AlertLog.Channel.PUSH, push_result)
        sent += 1

    logger.info("[%s] position alerts dispatched to %d holders", window, sent)
    return {"sent": sent}
