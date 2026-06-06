"""Evaluation metrics for the AIVA RAG system.

Metrics computed:
  - intent_accuracy     : did the router return the correct intent?
  - ticker_recall       : fraction of expected tickers extracted
  - numeric_exactness   : are required numeric fields present and non-zero?
  - citation_present    : does NEWS_QA response include ≥1 citation?
  - no_hallucination    : response does not contain INSUFFICIENT_CONTEXT when data exists
  - faithfulness (LLM)  : LLM judge asks "does the answer contradict the data?" (0/1)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class EvalResult:
    case_id: str
    intent_correct: bool | None = None
    ticker_recall: float | None = None
    numeric_exactness: float | None = None
    citation_present: bool | None = None
    no_hallucination: bool | None = None
    faithfulness: float | None = None
    raw_response: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def score(self) -> float:
        """Composite score 0–1."""
        parts = [
            v for v in [
                self.intent_correct,
                self.ticker_recall,
                self.numeric_exactness,
            ]
            if v is not None
        ]
        return sum(float(p) for p in parts) / len(parts) if parts else 0.0


def check_intent(case: dict, response: dict) -> bool:
    expected = case.get("intent", "").upper()
    actual   = response.get("intent", "").upper()
    return actual == expected


def check_ticker_recall(case: dict, response: dict) -> float:
    expected = set(case.get("expected_tickers", []))
    if not expected:
        return 1.0
    # Pull tickers from response — check citations or structured data
    found: set[str] = set()
    for c in response.get("citations", []):
        if c.get("ticker"):
            found.add(c["ticker"].upper())
    data = response.get("data", [])
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and item.get("ticker"):
                found.add(item["ticker"].upper())
    return len(expected & found) / len(expected)


def check_numeric_exactness(case: dict, response: dict) -> float:
    """Check that required numeric fields appear and are non-None."""
    fields = case.get("expected_fields", [])
    numeric_fields = {"close_price", "open_price", "high", "low", "volume",
                      "change_pct", "confidence", "predicted_price", "expected_change_pct"}
    required = [f for f in fields if f in numeric_fields]
    if not required:
        return 1.0

    # Look through all levels of the response
    raw = str(response)
    found = 0
    for f in required:
        # Field present with a number next to it
        if re.search(rf'"{f}"\s*:\s*[\d.-]+', raw):
            found += 1
    return found / len(required)


def check_citation_present(response: dict) -> bool:
    return bool(response.get("citations"))


def check_no_hallucination(response: dict) -> bool:
    answer = response.get("answer", "")
    if not answer:
        return True  # no answer generated — N/A
    return "INSUFFICIENT_CONTEXT" not in answer.upper()


async def check_faithfulness_llm(
    case: dict,
    response: dict,
    llm_client,
) -> float:
    """LLM judge: 1.0 = faithful, 0.0 = contradiction detected."""
    answer = response.get("answer", "")
    if not answer or not llm_client:
        return 1.0
    prompt = (
        "You are an evaluation judge for a financial AI system. "
        "Read the answer below and decide if it contains any made-up numbers, "
        "tickers, or facts not grounded in the provided context.\n\n"
        f"Context: {case}\n\nAnswer: {answer}\n\n"
        "Reply with FAITHFUL or HALLUCINATED and nothing else."
    )
    result = await llm_client._chat(
        system="You are a strict factuality judge.",
        messages=[{"role": "user", "content": prompt}],
        model=llm_client._router_model,
        max_tokens=10,
        temperature=0.0,
    )
    return 1.0 if "FAITHFUL" in result.upper() else 0.0


def print_scorecard(results: list[EvalResult]) -> None:
    print("\n" + "=" * 60)
    print(f"{'ID':<12} {'Intent':>7} {'Ticker':>7} {'Numeric':>8} {'Score':>6}")
    print("-" * 60)
    total = 0.0
    for r in results:
        if r.error:
            print(f"{r.case_id:<12} {'ERROR':>7}  —  {r.error[:30]}")
            continue
        s = r.score()
        total += s
        print(
            f"{r.case_id:<12} "
            f"{'✓' if r.intent_correct else '✗':>7} "
            f"{r.ticker_recall or 0:>7.2f} "
            f"{r.numeric_exactness or 0:>8.2f} "
            f"{s:>6.2f}"
        )
    print("=" * 60)
    print(f"Average score: {total / len(results):.3f}  ({len(results)} cases)")
