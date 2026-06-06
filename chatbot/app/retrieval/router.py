"""Query intent router.

Wraps the LLM classifier and augments its output with regex-based
ticker extraction (word-boundary safe, handles $PSO and #PSO cashtags).
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING

from app.core.config import Settings
from app.core.logging import get_logger
from app.generation.schemas import QueryFilters, QueryIntent, RouterOutput

if TYPE_CHECKING:
    from app.generation.llm import LLMClient

log = get_logger(__name__)

# Matches $PSO, #PSO, or word-boundary PSO — avoids partial hits like "SYMPHONY" matching "SYM"
_CASHTAG = re.compile(r"(?:[$#]?)([A-Z]{2,7})(?=\s|$|[^A-Z])", re.IGNORECASE)


class QueryRouter:
    def __init__(self, llm: "LLMClient", settings: Settings) -> None:
        self._llm = llm
        self._settings = settings
        self._ticker_set = set(settings.psx_tickers)

    async def route(
        self,
        query: str,
        history: list[dict] | None = None,
        sectors: list[str] | None = None,
    ) -> RouterOutput:
        raw = await self._llm.classify_intent(query, history=history, sectors=sectors)

        intent_str = raw.get("intent", "GENERAL").upper()
        try:
            intent = QueryIntent(intent_str)
        except ValueError:
            intent = QueryIntent.GENERAL

        # Parse filters object from LLM output
        raw_filters = raw.get("filters", {})
        llm_tickers = [t.upper() for t in (raw_filters.get("tickers") or [])]
        # Augment with regex-extracted tickers in case LLM missed any
        regex_tickers = self._extract_tickers_regex(query)
        all_tickers = list(dict.fromkeys(llm_tickers + regex_tickers))

        raw_signal_filters = [sf.upper() for sf in (raw_filters.get("signal_filters") or [])]
        filters = QueryFilters(
            tickers=all_tickers,
            sector=raw_filters.get("sector"),
            signal_filter=raw_filters.get("signal_filter"),
            signal_filters=raw_signal_filters,
            include_price=bool(raw_filters.get("include_price", True)),
            include_signal=bool(raw_filters.get("include_signal", True)),
            include_news=bool(raw_filters.get("include_news", False)),
            limit=int(raw_filters.get("limit") or 10),
        )

        # Validate specialized_ops — allowlist only
        valid_specialized = {"get_top_gainers", "get_top_losers"}
        specialized_ops = [
            op for op in (raw.get("specialized_ops") or [])
            if op in valid_specialized
        ]

        needs_portfolio = bool(raw.get("needs_portfolio", False))

        output = RouterOutput(
            intent=intent,
            filters=filters,
            needs_portfolio=needs_portfolio,
            specialized_ops=specialized_ops,
            time_range=raw.get("time_range"),
            raw=raw,
        )
        log.info(
            "query_routed",
            intent=intent.value,
            tickers=filters.tickers,
            sector=filters.sector,
            signal_filter=filters.signal_filter,
            include_news=filters.include_news,
            specialized_ops=specialized_ops,
            needs_portfolio=needs_portfolio,
            query=query[:100],
        )
        return output

    def _extract_tickers_regex(self, query: str) -> list[str]:
        found = []
        for match in _CASHTAG.finditer(query.upper()):
            candidate = match.group(1)
            if candidate in self._ticker_set:
                found.append(candidate)
        return found
