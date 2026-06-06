"""Gemini-powered plain-English summaries for alert payloads.

Ports the LLM calls from `n8n/local_workflow_a_strong_signals.json` and
`n8n/local_workflow_b_portfolio_alerts.json`. Three call sites:

  - summarize_top_pick(signal, live, news)   → 5-7 sentence detailed
                                                explanation for THE top pick
  - summarize_digest(signals_with_live)      → {ticker: one-liner} batch
  - summarize_position(signal, live, news, holding) → holder-framed
                                                       explanation for
                                                       SELL/STRONG_SELL on
                                                       a user's holding

Each call has a template fallback — Gemini outage never blocks the alert
pipeline. Circuit breaker opens after 3 consecutive failures and stays
open for 60s so we don't hammer a wedged endpoint.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time

import requests

logger = logging.getLogger(__name__)

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/"
    "models/gemini-2.5-flash-lite:generateContent"
)
API_KEY = os.environ.get("GEMINI_API_KEY", "")
TIMEOUT_SEC = 15

# Simple in-process circuit breaker (single Celery worker = fine).
_BREAKER_LOCK = threading.Lock()
_BREAKER = {"failures": 0, "open_until": 0.0}
BREAKER_THRESHOLD = 3
BREAKER_TIMEOUT = 60


def _breaker_open() -> bool:
    return _BREAKER["open_until"] > time.time()


def _record_failure() -> None:
    with _BREAKER_LOCK:
        _BREAKER["failures"] += 1
        if _BREAKER["failures"] >= BREAKER_THRESHOLD:
            _BREAKER["open_until"] = time.time() + BREAKER_TIMEOUT
            logger.warning("Gemini circuit breaker OPEN for %ds", BREAKER_TIMEOUT)


def _record_success() -> None:
    with _BREAKER_LOCK:
        _BREAKER["failures"] = 0
        _BREAKER["open_until"] = 0


def _gemini_call(system: str, user: str, *, json_mode: bool = False) -> str:
    if not API_KEY:
        logger.warning("GEMINI_API_KEY not set; falling back to template")
        raise RuntimeError("no api key")
    if _breaker_open():
        raise RuntimeError("circuit breaker open")
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {
            "maxOutputTokens": 2000,
            "temperature": 0.4 if json_mode else 0.7,
            "thinkingConfig": {"thinkingBudget": 0},
            **({"responseMimeType": "application/json"} if json_mode else {}),
        },
    }
    try:
        r = requests.post(
            GEMINI_URL,
            headers={"x-goog-api-key": API_KEY, "content-type": "application/json"},
            json=body,
            timeout=TIMEOUT_SEC,
        )
        r.raise_for_status()
        text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
        _record_success()
        return text.strip()
    except Exception as exc:
        logger.warning("Gemini call failed: %s", exc)
        _record_failure()
        raise


# -------------------------------------------------------------------- A: top
TOP_PICK_SYSTEM = (
    "You are FinMate, a Pakistani stock-market assistant writing for everyday "
    "investors who don't know what RSI or MA50 means. Write a confident, "
    "friendly 5-7 sentence explanation of why this stock signal was issued. "
    "Translate technical terms into meaning, don't define them. Cite specific "
    "numbers from the data (price, change %, RSI level, MA crossover position, "
    "volume vs 20-day average, EPS if relevant) to back up the recommendation. "
    "Mention the news context if relevant. Be direct — DO NOT add disclaimers, "
    "risk warnings, hedging language, 'consult an advisor' lines, or 'this is "
    "not financial advice' caveats."
)


def _format_top_user_msg(signal: dict, live: dict, news: list) -> str:
    contributions = json.dumps(signal.get("contributions") or {})
    n0 = (news[0] or {}).get("headline", "none") if news else "none"
    n1 = (news[1] or {}).get("headline", "none") if len(news) > 1 else "none"
    return (
        f"Stock: {signal.get('ticker')}\n"
        f"Signal: STRONG BUY (confidence: {signal.get('suggestion_confidence')})\n"
        f"Health label: {signal.get('health_label')}\n"
        f"Directional horizon: {signal.get('horizon')}d\n"
        f"Blended score: {signal.get('blended_score')}\n"
        f"Signal strength: {signal.get('signal_strength')}\n"
        f"Forecast signed score: {signal.get('forecast_signed_score')}\n"
        f"Reason: {signal.get('reason')}\n"
        f"Dominant news sentiment: {signal.get('dominant_sentiment')}\n"
        f"Contributions: {contributions}\n\n"
        f"Current: close = {live.get('close')}, change = {live.get('change_pct')}%, "
        f"RSI14 = {live.get('rsi14')}, MA20 = {live.get('ma20')}, "
        f"MA50 = {live.get('ma50')}, MA200 = {live.get('ma200')}, "
        f"volatility20d = {live.get('volatility20d')}, "
        f"volume_ratio = {live.get('volume_ratio')}, EPS = {live.get('eps')}.\n\n"
        f"Top news headlines:\n- {n0}\n- {n1}\n\n"
        f"Write the explanation now. Start with the recommendation, weave the "
        f"specific numbers into your reasoning, end with a confident closing "
        f"statement (NOT a risk warning)."
    )


def summarize_top_pick(signal: dict, live: dict, news: list) -> str:
    try:
        return _gemini_call(TOP_PICK_SYSTEM, _format_top_user_msg(signal, live, news))
    except Exception:
        return _template_top_pick(signal, live)


def _template_top_pick(signal: dict, live: dict) -> str:
    ticker = signal.get("ticker", "—")
    close = live.get("close") or "—"
    pct = live.get("change_pct") or 0
    conf = signal.get("suggestion_confidence", "MEDIUM")
    return (
        f"{ticker} is showing a STRONG BUY at PKR {close} ({pct:+.2f}% today). "
        f"Our models give this a {conf} confidence rating. "
        f"The signal blends technical momentum, recent news sentiment, and our "
        f"forecast for the coming days. Watch for follow-through on volume."
    )


# -------------------------------------------------------------------- A: digest
DIGEST_SYSTEM = (
    "You are FinMate. For each STRONG_BUY stock below, write a short "
    "ONE-SENTENCE plain-English summary in 12 words or fewer — translate the "
    "numbers into meaning, no jargon. Return ONLY a single JSON object mapping "
    "ticker to summary string, no markdown, no surrounding text. Example: "
    "{\"HBL\":\"Banking momentum continuing with strong volume.\","
    "\"OGDC\":\"Energy sector picking up after recent dip.\"}"
)


def summarize_digest(signals_with_live: list) -> dict:
    """Returns {ticker: one_liner} for batch summarisation. Falls back to
    a generic per-ticker template on any failure."""
    if not signals_with_live:
        return {}
    user = "\n".join(
        f"{s['signal'].get('ticker')}: rsi={s['live'].get('rsi14','n/a')}, "
        f"ma50={s['live'].get('ma50','n/a')}, ma200={s['live'].get('ma200','n/a')}, "
        f"close={s['live'].get('close','n/a')}, "
        f"change_pct={s['live'].get('change_pct','n/a')}, "
        f"health={s['signal'].get('health_label','n/a')}"
        for s in signals_with_live
    )
    try:
        text = _gemini_call(DIGEST_SYSTEM, user, json_mode=True)
        # Strip ```json fences if the model adds them despite responseMimeType
        text = text.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        return json.loads(text)
    except Exception:
        return {
            s["signal"].get("ticker"): "Strong-buy signal — momentum building."
            for s in signals_with_live
        }


# -------------------------------------------------------------------- B: position
POSITION_SYSTEM = (
    "You are FinMate writing for an investor who already OWNS this stock. The "
    "signal is on their existing position. Write a confident, friendly 5-7 "
    "sentence explanation. Translate technical terms into meaning, don't "
    "define them. Cite specific numbers (current price, % change, RSI level, "
    "MA position, volume vs 20-day average, EPS if relevant, and the holder's "
    "P&L) to ground the recommendation. Mention news context if relevant. Be "
    "direct — DO NOT add disclaimers, risk warnings, hedging, 'consult an "
    "advisor' lines, or 'this is not financial advice' caveats. End with a "
    "direct, practical action."
)


def _format_position_user_msg(signal: dict, live: dict, news: list) -> str:
    contributions = json.dumps(signal.get("contributions") or {})
    n0 = (news[0] or {}).get("headline", "none") if news else "none"
    n1 = (news[1] or {}).get("headline", "none") if len(news) > 1 else "none"
    return (
        f"User HOLDS: {signal.get('ticker')}\n"
        f"Signal: {signal.get('signal')} "
        f"(confidence: {signal.get('suggestion_confidence')})\n"
        f"Health: {signal.get('health_label')}\n"
        f"Horizon: {signal.get('horizon')}d\n"
        f"Reason: {signal.get('reason')}\n"
        f"Dominant news sentiment: {signal.get('dominant_sentiment')}\n"
        f"Contributions: {contributions}\n\n"
        f"Current: close = {live.get('close')}, change = {live.get('change_pct')}%, "
        f"RSI14 = {live.get('rsi14')}, MA20 = {live.get('ma20')}, "
        f"MA50 = {live.get('ma50')}, MA200 = {live.get('ma200')}, "
        f"volatility20d = {live.get('volatility20d')}, "
        f"volume_ratio = {live.get('volume_ratio')}, EPS = {live.get('eps')}.\n\n"
        f"Top news:\n- {n0}\n- {n1}\n\n"
        f"Write the explanation addressed to the holder. Weave the specific "
        f"numbers into your reasoning. End with a confident, direct action "
        f"(no risk warnings or 'consider consulting' lines)."
    )


def summarize_position(signal: dict, live: dict, news: list) -> str:
    try:
        return _gemini_call(
            POSITION_SYSTEM, _format_position_user_msg(signal, live, news)
        )
    except Exception:
        return _template_position(signal, live)


def _template_position(signal: dict, live: dict) -> str:
    ticker = signal.get("ticker", "—")
    sig = signal.get("signal", "SELL").replace("_", " ")
    close = live.get("close") or "—"
    conf = signal.get("suggestion_confidence", "MEDIUM")
    return (
        f"Our models are recommending {sig} on your {ticker} position at "
        f"PKR {close}. Confidence: {conf}. The combined technical + news + "
        f"forecast signal has weakened — consider trimming or fully closing."
    )
