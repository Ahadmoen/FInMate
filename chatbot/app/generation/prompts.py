"""Versioned system prompts — conversational personality for AIVA.

VERSION is bumped whenever the grounding contract changes so that
cached LLM responses are automatically invalidated.
"""
PROMPT_VERSION = "v3"

# ── Grounding contract ────────────────────────────────────────────────────────
_GROUNDING = """
GROUNDING RULES (non-negotiable):
- Every number you state must come verbatim from the <context> block.
- If a number is missing from <context>, say you don't have that data.
- Never invent tickers, company names, prices, or dates.
- Currency is PKR unless stated otherwise.
""".strip()

# ── Personality base ──────────────────────────────────────────────────────────
_PERSONA = (
    "You are AIVA, a friendly and knowledgeable financial assistant for FinMate, "
    "a Pakistan Stock Exchange (PSX) app. You talk like a smart friend who knows "
    "the markets well — natural, warm, and to the point. No stiff report formats, "
    "no unnecessary headers. Just clear, helpful answers in plain conversational English. "
    "Keep responses concise (under 200 words unless the question genuinely needs more). "
    "End with a brief disclaimer only on responses that include specific numbers or signals."
)

_DISCLAIMER = "*(AI-generated, not financial advice.)*"

# ── Per-intent system prompts ─────────────────────────────────────────────────

SYSTEM_PROMPTS: dict[str, str] = {

    "PRICE_LOOKUP": f"""{_PERSONA}

{_GROUNDING}

The user asked for price data. Describe the stock's performance today in 2-3 natural sentences — \
like you're telling a friend. Include the close price, direction (up/down), percent change, and volume \
if those figures are in <context>. Then add {_DISCLAIMER}""",

    "FUNDAMENTALS": f"""{_PERSONA}

{_GROUNDING}

Summarise the signal, forecast, and price data from <context> in a conversational way. \
Lead with the most actionable insight (the signal), then briefly mention the price and forecast. \
Add {_DISCLAIMER} at the end.""",

    "NEWS_QA": f"""{_PERSONA}

{_GROUNDING}

Answer using only the news and documents in <context>. Write naturally — summarise the key \
story first, then explain what it might mean for the stock. Cite sources inline like \
(source: <source>). If <context> has nothing relevant, say so plainly — don't make things up. \
Add {_DISCLAIMER} at the end.""",

    "ANALYTICS": f"""{_PERSONA}

{_GROUNDING}

Present the analytics data from <context> conversationally. Lead with the headline finding, \
then a few supporting details. Exact numbers from the data only. Add {_DISCLAIMER} at the end.""",

    "COMPARISON": f"""{_PERSONA}

{_GROUNDING}

Compare the stocks from <context> in a clear, conversational way. Pick the most interesting \
differences — don't just list every field. Tell the user which stock looks more active, \
which moved more, and by how much. Add {_DISCLAIMER} at the end.""",

    "MULTI_STEP": f"""{_PERSONA}

{_GROUNDING}

You have tools to look up prices, signals, news, and movers. Use them to answer the user's \
question step by step. Think out loud briefly between tool calls. Stop once you have a \
grounded answer. Max 5 tool calls.""",

    "PORTFOLIO": f"""{_PERSONA}

{_GROUNDING}

The user is asking about their own stock portfolio. The <context> block may contain:
  - PORTFOLIO HOLDINGS: their positions with quantities, avg buy price, current price, and P&L
  - SIGNALS FOR YOUR HOLDINGS: BUY / SELL / HOLD signal with confidence and reason for each stock they own
  - TOP PSX BUY SIGNALS: globally recommended new stocks to consider adding

Answer based on what the user is actually asking:
  - If they ask "should I sell?" or "which to sell" → use SIGNALS FOR YOUR HOLDINGS. \
A SELL signal means consider exiting. A HOLD or BUY signal means do NOT sell — explain why. \
Lead with the signal recommendation, then support it with the P&L context.
  - If they ask "should I buy?" → use TOP PSX BUY SIGNALS for new additions; \
use SIGNALS FOR YOUR HOLDINGS to flag any existing holding with a BUY signal worth adding to.
  - If they ask "how is my portfolio doing?" → lead with overall P&L, then highlight \
the best and worst performers by unrealized P&L percentage.
  - If they ask both buy and sell → cover both clearly.

Always use exact numbers from <context>. Never invent signals or prices. \
If signal data is absent, say so rather than guessing. \
Add {_DISCLAIMER} at the end.""",

    "GENERAL": f"""{_PERSONA}

Answer helpfully. If the question is about PSX and you lack specific data, say so plainly \
rather than guessing. Keep it concise.""",
}


# ── Prompt builders ───────────────────────────────────────────────────────────

def build_price_prompt(
    user_query: str,
    user_name: str,
    snapshots: list[dict],
    history: list[dict] | None = None,
) -> list[dict]:
    import json
    context = json.dumps(snapshots, indent=2, default=str)
    user_msg = {"role": "user", "content": (
        f"{user_name}: {user_query}\n\n<context>\n{context}\n</context>"
    )}
    return _with_history(history, user_msg)


def build_fundamentals_prompt(
    user_query: str,
    user_name: str,
    data: dict,
    history: list[dict] | None = None,
) -> list[dict]:
    import json
    context = json.dumps(data, indent=2, default=str)
    user_msg = {"role": "user", "content": (
        f"{user_name}: {user_query}\n\n<context>\n{context}\n</context>"
    )}
    return _with_history(history, user_msg)


def build_news_qa_prompt(
    user_query: str,
    user_name: str,
    context_chunks: list[dict],
    history: list[dict] | None = None,
) -> list[dict]:
    context_text = _format_chunks(context_chunks)
    user_msg = {"role": "user", "content": (
        f"{user_name}: {user_query}\n\n<context>\n{context_text}\n</context>"
    )}
    return _with_history(history, user_msg)


def build_analytics_prompt(
    user_query: str,
    user_name: str,
    structured_data: dict,
    context_chunks: list[dict] | None = None,
    history: list[dict] | None = None,
) -> list[dict]:
    context_text = _format_structured(structured_data)
    if context_chunks:
        context_text += "\n\n" + _format_chunks(context_chunks)
    user_msg = {"role": "user", "content": (
        f"{user_name}: {user_query}\n\n<context>\n{context_text}\n</context>"
    )}
    return _with_history(history, user_msg)


def build_comparison_prompt(
    user_query: str,
    user_name: str,
    structured_data: dict,
    history: list[dict] | None = None,
) -> list[dict]:
    context_text = _format_structured(structured_data)
    user_msg = {"role": "user", "content": (
        f"{user_name}: {user_query}\n\n<context>\n{context_text}\n</context>"
    )}
    return _with_history(history, user_msg)


def build_portfolio_prompt(
    user_query: str,
    user_name: str,
    portfolio_rows: list[dict],
    summary: dict | None = None,
    history: list[dict] | None = None,
) -> list[dict]:
    import json
    payload = {"positions": portfolio_rows}
    if summary:
        payload["summary"] = summary
    context = json.dumps(payload, indent=2, default=str)
    user_msg = {"role": "user", "content": (
        f"{user_name}: {user_query}\n\n<context>\n{context}\n</context>"
    )}
    return _with_history(history, user_msg)


def build_general_prompt(
    user_query: str,
    user_name: str,
    history: list[dict] | None = None,
) -> list[dict]:
    user_msg = {"role": "user", "content": f"{user_name}: {user_query}"}
    return _with_history(history, user_msg)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _with_history(history: list[dict] | None, user_msg: dict) -> list[dict]:
    """Prepend the last 20 history entries (10 turns) before the current message."""
    prior = [
        {"role": m["role"], "content": str(m.get("content", ""))}
        for m in (history or [])[-20:]
        if m.get("role") in ("user", "assistant") and m.get("content")
    ]
    return prior + [user_msg]


def _format_chunks(chunks: list[dict]) -> str:
    parts = []
    for i, c in enumerate(chunks, 1):
        meta = c.get("metadata", {})
        source = meta.get("source") or meta.get("doc_id", "unknown")
        parts.append(
            f"[{i}] source={source} "
            f"ticker={meta.get('ticker', 'N/A')} "
            f"published={meta.get('published_at', 'unknown')}\n"
            f"{c.get('text', '')}"
        )
    return "\n\n".join(parts) if parts else "(no context available)"


def build_mixed_context_prompt(
    user_query: str,
    user_name: str,
    context_data: dict,
    history: list[dict] | None = None,
) -> list[dict]:
    """Build a unified prompt from the output of _execute_filters.

    Context keys:
      market_data  — unified price + signal + company rows from fetch_market_data
      top_gainers  — today's top gaining stocks
      top_losers   — today's top losing stocks
      news         — vector search chunks (news/filings)
      portfolio    — user's holdings with P&L (Phase 1)
    """
    import json
    parts = []

    if context_data.get("portfolio"):
        parts.append(
            "PORTFOLIO HOLDINGS (with live P&L):\n"
            + json.dumps(context_data["portfolio"], indent=2, default=str)
        )

    if context_data.get("portfolio_error"):
        parts.append(f"PORTFOLIO NOTE: {context_data['portfolio_error']}")

    if context_data.get("market_data"):
        parts.append(
            "STOCK DATA (price, signal, health, company info):\n"
            + json.dumps(context_data["market_data"], indent=2, default=str)
        )

    if context_data.get("buy_signals"):
        parts.append(
            "STOCKS TO BUY (BUY / STRONG_BUY signals):\n"
            + json.dumps(context_data["buy_signals"], indent=2, default=str)
        )

    if context_data.get("sell_signals"):
        parts.append(
            "STOCKS TO SELL (SELL / STRONG_SELL signals):\n"
            + json.dumps(context_data["sell_signals"], indent=2, default=str)
        )

    if context_data.get("top_gainers"):
        parts.append(
            "TODAY'S TOP GAINERS:\n"
            + json.dumps(context_data["top_gainers"], indent=2, default=str)
        )

    if context_data.get("top_losers"):
        parts.append(
            "TODAY'S TOP LOSERS:\n"
            + json.dumps(context_data["top_losers"], indent=2, default=str)
        )

    if context_data.get("news"):
        parts.append("RECENT NEWS & SENTIMENT:\n" + _format_chunks(context_data["news"]))

    context_text = "\n\n---\n\n".join(parts) if parts else "(no data available)"
    user_msg = {
        "role": "user",
        "content": f"{user_name}: {user_query}\n\n<context>\n{context_text}\n</context>",
    }
    return _with_history(history, user_msg)


def _format_structured(data: dict) -> str:
    import json
    return json.dumps(data, indent=2, default=str)
