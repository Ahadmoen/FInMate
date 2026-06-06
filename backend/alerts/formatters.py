"""HTML + plain-text email builders for FinMate alerts.

Ports the inline HTML strings from the n8n workflows so the email
output looks identical to what users saw under the n8n era:

  build_top_pick_email   (Workflow A — TOP PICK)
  build_digest_email     (Workflow A — DIGEST, table of the rest)
  build_position_email   (Workflow B — POSITION_ALERT on a holding)

Each returns (subject, html, plain) ready to hand to
`alerts.notifications.email.send_email`.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

PKT = ZoneInfo("Asia/Karachi")
DOCS_URL = "https://finmate.app/docs/notifications"


def _safe(v, d=2):
    try:
        if v is None:
            return "—"
        return f"{float(v):.{d}f}"
    except (TypeError, ValueError):
        return "—"


def _pct_color(pct):
    try:
        return "#16a34a" if float(pct) >= 0 else "#dc2626"
    except (TypeError, ValueError):
        return "#6b7280"


def _pct_sign(pct):
    try:
        return "+" if float(pct) >= 0 else ""
    except (TypeError, ValueError):
        return ""


def _now_pkt_str(iso: str | None = None) -> str:
    if iso:
        try:
            dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        except Exception:
            dt = datetime.now(tz=PKT)
    else:
        dt = datetime.now(tz=PKT)
    return dt.astimezone(PKT).strftime("%d %b %Y, %I:%M %p")


def _news_html(news: list) -> str:
    if not news:
        return '<li style="color: #6b7280;">No recent news</li>'
    return "".join(
        f'<li style="margin: 4px 0;">'
        f'<a href="{n.get("link", "#")}" style="color: #2563eb; text-decoration: none;">'
        f'{n.get("headline", "")}</a> '
        f'<span style="color: #6b7280; font-size: 12px;">· '
        f'{n.get("source", "")} · {n.get("sentiment", "")}</span></li>'
        for n in news
    )


# -------------------------------------------------------------- A: top pick
def build_top_pick_email(
    signal: dict,
    live: dict,
    news: list,
    summary: str,
    window_label: str,
) -> tuple[str, str, str]:
    ticker = signal.get("ticker", "—")
    pct = live.get("change_pct") or 0
    color = _pct_color(pct)
    sign = _pct_sign(pct)
    conf = signal.get("suggestion_confidence", "MEDIUM")
    generated_at = _now_pkt_str(signal.get("generated_at"))

    subject = f"Top Pick: {ticker} ▲ STRONG BUY — {window_label}"
    html = f"""
<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 560px; margin: 0 auto; padding: 24px; background: #ffffff; border: 1px solid #e5e7eb; border-radius: 12px;">
  <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #f3f4f6; padding-bottom: 12px; margin-bottom: 16px;">
    <h1 style="margin: 0; font-size: 22px; font-weight: 700; color: #1f2937;">Fin<span style="color: #2563eb;">Mate</span></h1>
    <span style="font-size: 12px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px;">Top Pick · {window_label}</span>
  </div>
  <div style="background: #ecfdf5; border-left: 4px solid #16a34a; padding: 12px 16px; border-radius: 8px; margin-bottom: 16px; font-size: 14px; color: #14532d;">
    <strong>Today's top pick</strong> — our highest-confidence STRONG BUY across the market.
  </div>
  <div style="background: #f9fafb; border-radius: 10px; padding: 16px; margin-bottom: 16px;">
    <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 8px;">
      <h2 style="margin: 0; font-size: 28px; font-weight: 700; color: #1f2937;">{ticker}</h2>
      <span style="font-size: 14px; font-weight: 600; color: #16a34a;">▲ STRONG BUY</span>
    </div>
    <div style="font-size: 14px; color: #4b5563;">
      <strong style="color: #1f2937;">PKR {_safe(live.get("close"))}</strong>
      &nbsp;·&nbsp; <span style="color: {color};">{sign}{_safe(pct)}%</span>
      &nbsp;·&nbsp; confidence: <strong>{conf}</strong>
    </div>
  </div>
  <p style="font-size: 15px; line-height: 1.6; color: #374151; margin: 0 0 16px 0;">{summary}</p>
  <table style="width: 100%; font-size: 13px; color: #4b5563; border-collapse: collapse; margin-bottom: 16px;">
    <tr style="background: #f9fafb;">
      <td style="padding: 8px 12px; border-radius: 6px 0 0 6px;">RSI 14</td>
      <td style="padding: 8px 12px; text-align: right;"><strong>{_safe(live.get("rsi14"), 1)}</strong></td>
      <td style="padding: 8px 12px;">MA 50</td>
      <td style="padding: 8px 12px; text-align: right; border-radius: 0 6px 6px 0;"><strong>{_safe(live.get("ma50"))}</strong></td>
    </tr>
    <tr>
      <td style="padding: 8px 12px;">MA 200</td>
      <td style="padding: 8px 12px; text-align: right;"><strong>{_safe(live.get("ma200"))}</strong></td>
      <td style="padding: 8px 12px;">Volatility</td>
      <td style="padding: 8px 12px; text-align: right;"><strong>{_safe((live.get("volatility20d") or 0) * 100, 1)}%</strong></td>
    </tr>
  </table>
  <h3 style="font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px; color: #6b7280; margin: 0 0 8px 0;">Recent news</h3>
  <ul style="list-style: none; padding-left: 0; margin: 0 0 20px 0; font-size: 14px;">
    {_news_html(news)}
  </ul>
  <div style="border-top: 1px solid #f3f4f6; padding-top: 12px; font-size: 12px; color: #6b7280; text-align: center;">
    Don't understand a number? <a href="{DOCS_URL}" style="color: #2563eb;">Read the guide →</a><br>
    Sent by FinMate · {generated_at} PKT
  </div>
</div>""".strip()

    plain = (
        f"Top Pick: {ticker} — STRONG BUY ({conf})\n\n{summary}\n\n"
        f"RSI {_safe(live.get('rsi14'), 1)} · MA50 {_safe(live.get('ma50'))} "
        f"· MA200 {_safe(live.get('ma200'))}\n\nDocs: {DOCS_URL}"
    )
    return subject, html, plain


# -------------------------------------------------------------- A: digest
def build_digest_email(
    enriched: list,
    summaries: dict,
    window_label: str,
) -> tuple[str, str, str]:
    """`enriched` = [{'signal': stock_signal_dict, 'live': live_md_dict}, ...]
    `summaries` = {ticker: one-line text from Gemini batch}."""
    rows_html = []
    for s in enriched:
        sig = s["signal"]
        live = s.get("live") or {}
        ticker = sig.get("ticker")
        pct = live.get("change_pct") or 0
        color = _pct_color(pct)
        sign = _pct_sign(pct)
        rows_html.append(
            f"""<tr style="border-bottom: 1px solid #f3f4f6;">
      <td style="padding: 10px 8px; font-weight: 600; color: #1f2937;">{ticker}</td>
      <td style="padding: 10px 8px; text-align: right; color: #1f2937;">{_safe(live.get("close"))}</td>
      <td style="padding: 10px 8px; text-align: right; color: {color};">{sign}{_safe(pct)}%</td>
      <td style="padding: 10px 8px; text-align: right; color: #4b5563;">{_safe(live.get("rsi14"), 1)}</td>
      <td style="padding: 10px 8px; color: #4b5563; font-size: 12px;">{summaries.get(ticker, sig.get("reason", ""))}</td>
    </tr>"""
        )

    table_rows = "\n".join(rows_html)
    subject = f"{len(enriched)} more strong-buy moves — {window_label}"
    html = f"""
<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 640px; margin: 0 auto; padding: 24px; background: #ffffff; border: 1px solid #e5e7eb; border-radius: 12px;">
  <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #f3f4f6; padding-bottom: 12px; margin-bottom: 16px;">
    <h1 style="margin: 0; font-size: 22px; font-weight: 700; color: #1f2937;">Fin<span style="color: #2563eb;">Mate</span></h1>
    <span style="font-size: 12px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px;">Other Top Performers · {window_label}</span>
  </div>
  <p style="font-size: 14px; color: #4b5563; margin: 0 0 16px 0;">{len(enriched)} more strong-buy moves on PSX today:</p>
  <table style="width: 100%; font-size: 13px; border-collapse: collapse;">
    <thead>
      <tr style="background: #f9fafb; text-transform: uppercase; font-size: 11px; color: #6b7280; letter-spacing: 0.5px;">
        <th style="padding: 8px; text-align: left;">Ticker</th>
        <th style="padding: 8px; text-align: right;">Price</th>
        <th style="padding: 8px; text-align: right;">Change</th>
        <th style="padding: 8px; text-align: right;">RSI</th>
        <th style="padding: 8px; text-align: left;">Note</th>
      </tr>
    </thead>
    <tbody>{table_rows}</tbody>
  </table>
  <div style="border-top: 1px solid #f3f4f6; padding-top: 12px; margin-top: 20px; font-size: 12px; color: #6b7280; text-align: center;">
    Don't understand a number? <a href="{DOCS_URL}" style="color: #2563eb;">Read the guide →</a><br>
    Sent by FinMate · {window_label}
  </div>
</div>""".strip()

    plain_rows = []
    for s in enriched:
        sig = s["signal"]
        live = s.get("live") or {}
        ticker = sig.get("ticker")
        pct = live.get("change_pct") or 0
        plain_rows.append(
            f"{ticker}  PKR {_safe(live.get('close'))}  "
            f"{_pct_sign(pct)}{_safe(pct)}%  RSI {_safe(live.get('rsi14'), 1)}\n"
            f"{summaries.get(ticker, sig.get('reason', ''))}"
        )
    plain = (
        f"Other top performers ({len(enriched)})\n\n"
        + "\n\n".join(plain_rows)
        + f"\n\nDocs: {DOCS_URL}"
    )
    return subject, html, plain


# -------------------------------------------------------------- B: position
def build_position_email(
    signal: dict,
    live: dict,
    news: list,
    summary: str,
    *,
    qty: float,
    avg_buy: float,
    window_label: str,
) -> tuple[str, str, str]:
    ticker = signal.get("ticker", "—")
    signal_label = (signal.get("signal") or "SELL").replace("_", " ")
    conf = signal.get("suggestion_confidence", "MEDIUM")
    cur = float(live.get("close") or avg_buy or 0)
    pct = live.get("change_pct") or 0
    color_today = _pct_color(pct)
    sign_today = _pct_sign(pct)
    generated_at = _now_pkt_str(signal.get("generated_at"))

    pnl_pkr = (cur - avg_buy) * qty
    pnl_pct = ((cur - avg_buy) / avg_buy * 100) if avg_buy else 0.0
    pnl_color = _pct_color(pnl_pct)
    pnl_sign = _pct_sign(pnl_pct)

    subject = f"Position alert — {ticker} ▼ {signal_label}"
    html = f"""
<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 560px; margin: 0 auto; padding: 24px; background: #ffffff; border: 1px solid #e5e7eb; border-radius: 12px;">
  <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid #f3f4f6; padding-bottom: 12px; margin-bottom: 16px;">
    <h1 style="margin: 0; font-size: 22px; font-weight: 700; color: #1f2937;">Fin<span style="color: #2563eb;">Mate</span></h1>
    <span style="font-size: 12px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.5px;">Your Portfolio · {window_label}</span>
  </div>
  <div style="background: #fef3c7; border-left: 4px solid #d97706; padding: 12px 16px; border-radius: 8px; margin-bottom: 16px; font-size: 14px; color: #92400e;">
    <strong>Position alert</strong> — you hold this stock and our models recommend {signal_label.lower()}.
  </div>
  <div style="background: #f9fafb; border-radius: 10px; padding: 16px; margin-bottom: 16px;">
    <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 8px;">
      <h2 style="margin: 0; font-size: 28px; font-weight: 700; color: #1f2937;">{ticker}</h2>
      <span style="font-size: 14px; font-weight: 600; color: #dc2626;">▼ {signal_label}</span>
    </div>
    <div style="font-size: 14px; color: #4b5563;">
      <strong style="color: #1f2937;">PKR {_safe(cur)}</strong>
      &nbsp;·&nbsp; <span style="color: {color_today};">{sign_today}{_safe(pct)}% today</span>
      &nbsp;·&nbsp; confidence: <strong>{conf}</strong>
    </div>
  </div>
  <table style="width: 100%; font-size: 13px; color: #4b5563; border-collapse: collapse; margin-bottom: 16px;">
    <tr style="background: #f3f4f6;"><td colspan="4" style="padding: 8px 12px; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; color: #6b7280; border-radius: 6px 6px 0 0;">Your position</td></tr>
    <tr>
      <td style="padding: 8px 12px;">Quantity</td>
      <td style="padding: 8px 12px; text-align: right;"><strong>{_safe(qty, 0)}</strong></td>
      <td style="padding: 8px 12px;">Avg buy price</td>
      <td style="padding: 8px 12px; text-align: right;"><strong>PKR {_safe(avg_buy)}</strong></td>
    </tr>
    <tr style="background: #f9fafb;">
      <td style="padding: 8px 12px; border-radius: 0 0 0 6px;">Unrealised P&amp;L</td>
      <td style="padding: 8px 12px; text-align: right; color: {pnl_color};"><strong>{pnl_sign}{_safe(pnl_pct)}%</strong></td>
      <td style="padding: 8px 12px;">P&amp;L in PKR</td>
      <td style="padding: 8px 12px; text-align: right; color: {pnl_color}; border-radius: 0 0 6px 0;"><strong>{pnl_sign}{_safe(pnl_pkr)}</strong></td>
    </tr>
  </table>
  <p style="font-size: 15px; line-height: 1.6; color: #374151; margin: 0 0 16px 0;">{summary}</p>
  <table style="width: 100%; font-size: 13px; color: #4b5563; border-collapse: collapse; margin-bottom: 16px;">
    <tr style="background: #f9fafb;">
      <td style="padding: 8px 12px; border-radius: 6px 0 0 6px;">RSI 14</td>
      <td style="padding: 8px 12px; text-align: right;"><strong>{_safe(live.get("rsi14"), 1)}</strong></td>
      <td style="padding: 8px 12px;">MA 50</td>
      <td style="padding: 8px 12px; text-align: right; border-radius: 0 6px 6px 0;"><strong>{_safe(live.get("ma50"))}</strong></td>
    </tr>
    <tr>
      <td style="padding: 8px 12px;">MA 200</td>
      <td style="padding: 8px 12px; text-align: right;"><strong>{_safe(live.get("ma200"))}</strong></td>
      <td style="padding: 8px 12px;">Volatility</td>
      <td style="padding: 8px 12px; text-align: right;"><strong>{_safe((live.get("volatility20d") or 0) * 100, 1)}%</strong></td>
    </tr>
  </table>
  <h3 style="font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px; color: #6b7280; margin: 0 0 8px 0;">Recent news</h3>
  <ul style="list-style: none; padding-left: 0; margin: 0 0 20px 0; font-size: 14px;">{_news_html(news)}</ul>
  <div style="border-top: 1px solid #f3f4f6; padding-top: 12px; font-size: 12px; color: #6b7280; text-align: center;">
    Don't understand a number? <a href="{DOCS_URL}" style="color: #2563eb;">Read the guide →</a><br>
    Sent by FinMate · {generated_at} PKT
  </div>
</div>""".strip()

    plain = (
        f"Position alert: {ticker} — {signal_label} ({conf})\n\n"
        f"You hold {_safe(qty, 0)} @ PKR {_safe(avg_buy)} "
        f"(P&L {pnl_sign}{_safe(pnl_pct)}%)\n\n{summary}\n\nDocs: {DOCS_URL}"
    )
    return subject, html, plain
