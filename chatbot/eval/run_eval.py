"""
Evaluation runner.

Usage:
  python eval/run_eval.py            # full suite
  python eval/run_eval.py --smoke    # smoke subset only
  make eval
  make eval-smoke
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import httpx

from eval.metrics import (
    EvalResult,
    check_citation_present,
    check_intent,
    check_no_hallucination,
    check_numeric_exactness,
    check_ticker_recall,
    print_scorecard,
)

GOLDEN_PATH = Path(__file__).parent / "golden_dataset.json"
API_BASE    = "http://localhost:8000"
TIMEOUT     = 30.0


async def run_case(client: httpx.AsyncClient, case: dict) -> EvalResult:
    result = EvalResult(case_id=case["id"])
    try:
        resp = await client.post(
            f"{API_BASE}/v1/query/sync",
            json={"query": case["query"], "user_name": "EvalBot"},
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        result.raw_response = data

        result.intent_correct    = check_intent(case, data)
        result.ticker_recall     = check_ticker_recall(case, data)
        result.numeric_exactness = check_numeric_exactness(case, data)
        result.citation_present  = check_citation_present(data)
        result.no_hallucination  = check_no_hallucination(data)

    except Exception as exc:
        result.error = str(exc)
    return result


async def main(smoke: bool) -> int:
    cases = json.loads(GOLDEN_PATH.read_text())
    if smoke:
        cases = [c for c in cases if c.get("smoke")]

    print(f"Running {len(cases)} eval cases against {API_BASE} ...")

    async with httpx.AsyncClient() as client:
        tasks = [run_case(client, c) for c in cases]
        results = await asyncio.gather(*tasks)

    print_scorecard(list(results))

    failed = sum(1 for r in results if r.error or r.score() < 0.5)
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    sys.exit(asyncio.run(main(args.smoke)))
