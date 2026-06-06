"""Provider-agnostic async LLM client.

Supports:
  groq      — llama-3.3-70b-versatile via Groq API (free tier, OpenAI-compatible)
  anthropic — claude-* via Anthropic SDK
  openai    — gpt-* via OpenAI SDK

Provider and model are selected via LLM_PROVIDER / LLM_MODEL env vars.
Default: groq (uses GROQ_API_KEY, no cost).
"""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import openai          # used for both Groq and OpenAI paths

from app.core.config import Settings
from app.core.logging import get_logger
from app.generation.prompts import SYSTEM_PROMPTS

log = get_logger(__name__)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
MAX_TOOL_ITERATIONS = 5


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._provider = settings.llm_provider
        self._model = settings.llm_model
        self._router_model = settings.router_model

        if self._provider == "anthropic":
            import anthropic as _anthropic
            self._client = _anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        elif self._provider == "groq":
            # Groq is 100% OpenAI-API-compatible — same SDK, different base URL + key
            self._client = openai.AsyncOpenAI(
                api_key=settings.groq_api_key,
                base_url=GROQ_BASE_URL,
            )
        else:
            self._client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

    # ── Intent classification ─────────────────────────────────────────────────

    async def classify_intent(
        self,
        query: str,
        history: list[dict] | None = None,
        sectors: list[str] | None = None,
    ) -> dict[str, Any]:
        prompt = _build_router_prompt(
            query, self._settings.psx_tickers,
            history=history, sectors=sectors,
        )
        raw = await self._chat(
            system=prompt["system"],
            messages=prompt["messages"],
            model=self._router_model,
            max_tokens=256,
            temperature=0.0,
        )
        # Strip markdown code fences if Groq/LLM wraps the JSON
        raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            log.warning("router_json_parse_failed", raw=raw[:200])
            return {"intent": "GENERAL", "tickers": [], "time_range": None}

    # ── Main generation ───────────────────────────────────────────────────────

    async def generate(
        self,
        intent: str,
        messages: list[dict],
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> str:
        system = SYSTEM_PROMPTS.get(intent, SYSTEM_PROMPTS["GENERAL"])
        return await self._chat(
            system=system,
            messages=messages,
            model=self._model,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    async def generate_stream(
        self,
        intent: str,
        messages: list[dict],
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> AsyncIterator[str]:
        system = SYSTEM_PROMPTS.get(intent, SYSTEM_PROMPTS["GENERAL"])
        async for chunk in self._chat_stream(
            system=system,
            messages=messages,
            model=self._model,
            max_tokens=max_tokens,
            temperature=temperature,
        ):
            yield chunk

    # ── Agent loop (MULTI_STEP) ───────────────────────────────────────────────

    async def run_agent(
        self,
        intent: str,
        messages: list[dict],
        tools: list[dict],
        tool_executor,
    ) -> tuple[str, int]:
        system = SYSTEM_PROMPTS.get(intent, SYSTEM_PROMPTS["GENERAL"])
        working_messages = list(messages)
        iterations = 0

        for _ in range(MAX_TOOL_ITERATIONS):
            iterations += 1
            if self._provider == "anthropic":
                result = await self._anthropic_tool_call(system, working_messages, tools)
            else:
                # Both groq and openai use the same tool-call path
                result = await self._openai_tool_call(system, working_messages, tools)

            if result["type"] == "final":
                return result["content"], iterations

            tool_result = await tool_executor(result["tool_name"], result["tool_input"])
            working_messages.append({"role": "assistant", "content": result["raw_content"]})
            working_messages.append({"role": "user", "content": f"<tool_result>{tool_result}</tool_result>"})

        return "INSUFFICIENT_CONTEXT — maximum tool iterations reached.", iterations

    # ── Low-level helpers ─────────────────────────────────────────────────────

    async def _chat(
        self,
        system: str,
        messages: list[dict],
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> str:
        if self._provider == "anthropic":
            resp = await self._client.messages.create(
                model=model,
                system=system,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return resp.content[0].text
        else:
            # groq + openai share the same OpenAI SDK path
            resp = await self._client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system}] + messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return resp.choices[0].message.content or ""

    async def _chat_stream(
        self,
        system: str,
        messages: list[dict],
        model: str,
        max_tokens: int,
        temperature: float,
    ) -> AsyncIterator[str]:
        if self._provider == "anthropic":
            async with self._client.messages.stream(
                model=model,
                system=system,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            ) as stream:
                async for text in stream.text_stream:
                    yield text
        else:
            stream = await self._client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system}] + messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta

    async def _anthropic_tool_call(self, system, messages, tools) -> dict:
        import anthropic as _anthropic
        anthropic_tools = [
            {"name": t["name"], "description": t["description"], "input_schema": t["parameters"]}
            for t in tools
        ]
        resp = await self._client.messages.create(
            model=self._model, system=system, messages=messages,
            tools=anthropic_tools, max_tokens=1024,
        )
        if resp.stop_reason == "tool_use":
            tool_use = next(b for b in resp.content if b.type == "tool_use")
            return {"type": "tool_call", "tool_name": tool_use.name,
                    "tool_input": tool_use.input, "raw_content": [b.model_dump() for b in resp.content]}
        text = next((b.text for b in resp.content if hasattr(b, "text")), "")
        return {"type": "final", "content": text}

    async def _openai_tool_call(self, system, messages, tools) -> dict:
        openai_tools = [
            {"type": "function", "function": {
                "name": t["name"], "description": t["description"], "parameters": t["parameters"],
            }}
            for t in tools
        ]
        resp = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "system", "content": system}] + messages,
            tools=openai_tools, max_tokens=1024,
        )
        msg = resp.choices[0].message
        if msg.tool_calls:
            tc = msg.tool_calls[0]
            return {"type": "tool_call", "tool_name": tc.function.name,
                    "tool_input": json.loads(tc.function.arguments), "raw_content": msg.model_dump()}
        return {"type": "final", "content": msg.content or ""}


# ── Router prompt ─────────────────────────────────────────────────────────────

def _build_router_prompt(
    query: str,
    known_tickers: list[str],
    history: list[dict] | None = None,
    sectors: list[str] | None = None,
) -> dict:
    ticker_list  = ", ".join(known_tickers)
    sector_list  = ", ".join(sectors) if sectors else "Banking, Cement, Information Technology, Oil & Gas Exploration, Power Generation"

    system = (
        "You are a query classifier for a Pakistan Stock Exchange (PSX) financial chatbot.\n\n"

        "STEP 1 — Pick exactly one INTENT:\n"
        "  PRICE_LOOKUP  — current or historical price / OHLCV data\n"
        "  FUNDAMENTALS  — performance, signals, forecasts for specific stocks\n"
        "  ANALYTICS     — sector overview, BUY/SELL signal lists, computed market analytics\n"
        "  NEWS_QA       — news, sentiment, or qualitative explanation of market events\n"
        "  COMPARISON    — compare two or more stocks side by side\n"
        "  PORTFOLIO     — user's own holdings, P&L, what to buy/sell from their portfolio\n"
        "  MULTI_STEP    — complex multi-part question needing reasoning across many sources\n"
        "  GENERAL       — greetings, general finance questions, nothing PSX-specific\n\n"

        "STEP 2 — Fill the 'filters' object (all fields optional, use null/false/[] if not needed):\n"
        "  tickers       — list of PSX ticker symbols mentioned in query (e.g. ['PSO','OGDC'])\n"
        "  sector        — exact DB sector name if user asks about an industry/field/sector\n"
        f"  Known sectors: {sector_list}\n"
        "  signal_filter — one of: STRONG_BUY, BUY, HOLD, SELL, STRONG_SELL — only if user asks for ONE specific signal type\n"
        "  signal_filters — list of signal types when user asks about MULTIPLE signals simultaneously, e.g. [\"BUY\",\"SELL\"]\n"
        "  include_price — true if price/OHLCV data is needed (default true for most queries)\n"
        "  include_signal— true if signal/health/performance data is needed\n"
        "  include_news  — true only if user explicitly asks about news, events, or 'why'\n"
        "  limit         — number of results (default 10, use 5 for quick lookups)\n\n"

        "STEP 3 — Fill 'specialized_ops' only for these two cases:\n"
        "  get_top_gainers — user asks for today's top gaining/best performing stocks\n"
        "  get_top_losers  — user asks for today's top losing/worst performing stocks\n\n"

        "FILTER RULES:\n"
        "  SECTOR queries ('IT stocks','companies in banking','cement sector'):\n"
        "    → match user phrase to exact sector name above, set sector=<exact name>, include_price=true, include_signal=true\n"
        "  PERFORMANCE queries ('how is PSO doing','how well is X performing'):\n"
        "    → tickers=[X], include_price=true, include_signal=true, intent=FUNDAMENTALS\n"
        "  SELL/LEAVE/EXIT with resolvable ticker from context:\n"
        "    → tickers=[that ticker], include_signal=true, intent=FUNDAMENTALS, needs_portfolio=false\n"
        "  SELL/LEAVE with NO resolvable ticker (general about holdings):\n"
        "    → needs_portfolio=true, include_signal=true, intent=PORTFOLIO\n"
        "  BUY with specific ticker:\n"
        "    → tickers=[X], include_price=true, include_signal=true, intent=FUNDAMENTALS\n"
        "  BUY with no ticker (general recommendation):\n"
        "    → signal_filter=BUY, include_signal=true, intent=ANALYTICS\n"
        "  BUY AND SELL (portfolio context):\n"
        "    → needs_portfolio=true, signal_filter=null, signal_filters=[], include_signal=true, intent=PORTFOLIO\n"
        "  BUY AND SELL (general, no portfolio — user asks which stocks to buy and which to sell):\n"
        "    → signal_filter=null, signal_filters=[\"BUY\",\"SELL\"], include_signal=true, intent=ANALYTICS\n"
        "  NEWS queries:\n"
        "    → include_news=true, tickers=[X if mentioned], intent=NEWS_QA\n"
        "  COMPARE queries:\n"
        "    → tickers=[X,Y], include_price=true, include_signal=true, intent=COMPARISON\n"
        "  TOP GAINERS/LOSERS:\n"
        "    → specialized_ops=[get_top_gainers or get_top_losers], filters={}, intent=ANALYTICS\n"
        "  MY PORTFOLIO:\n"
        "    → needs_portfolio=true, include_price=true, include_signal=true, intent=PORTFOLIO\n\n"

        f"Known PSX tickers: {ticker_list}\n"
        "Extract tickers by word boundary only — never match substrings.\n\n"

        "Return ONLY valid JSON, no extra text:\n"
        '{"intent":"FUNDAMENTALS","filters":{"tickers":[],"sector":null,"signal_filter":null,'
        '"signal_filters":[],"include_price":true,"include_signal":true,"include_news":false,"limit":10},'
        '"needs_portfolio":false,"specialized_ops":[],"time_range":null}'
    )

    # Include last 3 turns so the router can resolve pronouns like
    # "this one", "it", "that stock" back to the ticker named in context.
    recent = ""
    if history:
        turns = [
            m for m in history[-6:]
            if m.get("role") in ("user", "assistant") and m.get("content")
        ]
        if turns:
            lines = "\n".join(
                f"  {'User' if m['role'] == 'user' else 'Assistant'}: "
                f"{str(m['content'])[:300]}"
                for m in turns
            )
            recent = (
                f"\n\nRECENT CONVERSATION CONTEXT:\n{lines}\n\n"
                "IMPORTANT: If the current query uses pronouns like 'this one', 'it', "
                "'that stock', resolve them to the ticker discussed above ONLY IF the entire "
                "query is specifically about that one stock. "
                "If the query asks about a sector, industry, or a broader topic (e.g. 'how are "
                "textile stocks affected by it?'), do NOT add tickers from history — set "
                "tickers=[] and classify using sector or GENERAL intent instead."
            )

    user_content = f"{recent}\n\nCURRENT QUERY TO CLASSIFY: {query}".strip() if recent else query
    return {"system": system, "messages": [{"role": "user", "content": user_content}]}
