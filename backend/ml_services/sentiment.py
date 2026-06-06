"""News sentiment scoring.

Default model: **FinBERT** (`ProsusAI/finbert`) — a BERT model fine-tuned
on financial news. It outputs three class probabilities
(positive / negative / neutral). We convert them to a continuous
compound score in `[-1, 1]` (`pos_prob - neg_prob`) and bucket into the
five labels `VERY_BAD / BAD / NEUTRAL / GOOD / EXCELLENT`.

If the FinBERT load fails (no network, no model on disk), we fall back
to VADER + a small finance-specific lexicon overlay so the pipeline
still runs in offline / minimal environments. Set `SENTIMENT_BACKEND=vader`
in the environment to force VADER even when FinBERT is available.
"""
import json
import os
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "integrations" / "data"
NEWS_FILE = DATA_DIR / "news_data.json"
OUTPUT_FILE = DATA_DIR / "news_sentiment.json"

LABELS = [
    (-1.01, -0.6, "VERY_BAD"),
    (-0.6,  -0.2, "BAD"),
    (-0.2,   0.2, "NEUTRAL"),
    ( 0.2,   0.6, "GOOD"),
    ( 0.6,   1.01, "EXCELLENT"),
]

FINBERT_MODEL_ID = "ProsusAI/finbert"
FINBERT_BATCH = 16
FINBERT_MAX_LEN = 256


def _label(score: float) -> str:
    for lo, hi, name in LABELS:
        if lo <= score < hi:
            return name
    return "NEUTRAL"


# ---------------- VADER fallback ------------------------------------------

FINANCE_LEXICON = {
    "downgrade": -2.5, "downgraded": -2.5, "default": -3.0, "defaults": -3.0,
    "fraud": -3.5, "scam": -3.5, "lawsuit": -2.0, "probe": -1.5,
    "loss": -2.0, "losses": -2.0, "deficit": -1.8, "plunge": -2.5,
    "plunged": -2.5, "slump": -2.0, "slumped": -2.0, "bearish": -2.0,
    "selloff": -2.0, "crash": -3.0, "crashed": -3.0, "tumble": -2.0,
    "tumbled": -2.0, "weak": -1.0, "miss": -1.5, "missed": -1.5,
    "warn": -1.5, "warning": -1.5, "cut": -1.0,
    "upgrade": 2.5, "upgraded": 2.5, "beat": 2.0, "beats": 2.0,
    "profit": 1.8, "profits": 1.8, "surge": 2.5, "surged": 2.5,
    "rally": 2.0, "rallied": 2.0, "bullish": 2.0, "soar": 2.5, "soared": 2.5,
    "record": 1.5, "strong": 1.2, "growth": 1.5, "expand": 1.2,
    "expansion": 1.5, "dividend": 1.2, "buyback": 2.0,
}


def _vader_scorer():
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    a = SentimentIntensityAnalyzer()
    a.lexicon.update(FINANCE_LEXICON)
    return a


# ---------------- FinBERT loader (lazy) -----------------------------------

_finbert_pipe = None
_backend = None


def _try_load_finbert():
    """Returns the HF pipeline or None on any failure."""
    try:
        from transformers import (
            AutoModelForSequenceClassification,
            AutoTokenizer,
            pipeline,
        )
        tokenizer = AutoTokenizer.from_pretrained(FINBERT_MODEL_ID)
        model = AutoModelForSequenceClassification.from_pretrained(FINBERT_MODEL_ID)
        return pipeline(
            "text-classification",
            model=model,
            tokenizer=tokenizer,
            top_k=None,            # return all class scores, not just argmax
            truncation=True,
            max_length=FINBERT_MAX_LEN,
            device=-1,             # CPU
        )
    except Exception as exc:
        print(f"  FinBERT unavailable ({exc.__class__.__name__}: {exc}). Falling back to VADER.")
        return None


def _ensure_backend():
    """Pick FinBERT or VADER once and cache the choice."""
    global _finbert_pipe, _backend
    if _backend is not None:
        return
    forced = os.environ.get("SENTIMENT_BACKEND", "").lower()
    if forced == "vader":
        _backend = "vader"
        return
    pipe = _try_load_finbert()
    if pipe is not None:
        _finbert_pipe = pipe
        _backend = "finbert"
    else:
        _backend = "vader"


def score_text(text: str) -> tuple:
    """Return (compound_score, label) for a single piece of text."""
    if not text:
        return 0.0, "NEUTRAL"
    _ensure_backend()
    if _backend == "finbert":
        result = _finbert_pipe(text)
        scores = result[0] if isinstance(result[0], list) else result
        by = {s["label"].lower(): float(s["score"]) for s in scores}
        compound = by.get("positive", 0.0) - by.get("negative", 0.0)
        return float(compound), _label(compound)
    # VADER fallback
    analyzer = _vader_scorer() if not hasattr(score_text, "_va") else score_text._va
    score_text._va = analyzer
    compound = float(analyzer.polarity_scores(text)["compound"])
    return compound, _label(compound)


def _batch_finbert(texts: list) -> list:
    """Score a list of texts via FinBERT batches. Returns list of (score, label)."""
    out = []
    for i in range(0, len(texts), FINBERT_BATCH):
        batch = texts[i : i + FINBERT_BATCH]
        results = _finbert_pipe(batch)
        for r in results:
            scores = r if isinstance(r, list) else [r]
            by = {s["label"].lower(): float(s["score"]) for s in scores}
            compound = by.get("positive", 0.0) - by.get("negative", 0.0)
            out.append((float(compound), _label(compound)))
        if (i // FINBERT_BATCH) % 10 == 0:
            print(f"  FinBERT progress: {min(i + FINBERT_BATCH, len(texts))}/{len(texts)}")
    return out


def analyze_sentiment(articles: list) -> list:
    _ensure_backend()
    print(f"  using backend: {_backend}")

    texts = []
    for art in articles:
        t = " ".join(filter(None, [art.get("Heading"), art.get("Description")]))
        texts.append(t or art.get("Heading") or "")

    if _backend == "finbert":
        scored = _batch_finbert(texts)
    else:
        analyzer = _vader_scorer()
        scored = []
        for t in texts:
            if not t:
                scored.append((0.0, "NEUTRAL"))
                continue
            s = float(analyzer.polarity_scores(t)["compound"])
            scored.append((s, _label(s)))

    out = []
    for art, (score, label) in zip(articles, scored):
        new = dict(art)
        new["SentimentScore"] = round(score, 4)
        new["Sentiment"] = label
        new["SentimentBackend"] = _backend
        out.append(new)
    return out


def main() -> None:
    if not NEWS_FILE.exists():
        print(f"missing {NEWS_FILE} — run news_scraper first")
        return

    articles = json.loads(NEWS_FILE.read_text())
    if not articles:
        print("news_data.json is empty")
        return

    import time as _time
    from . import mlflow_utils
    started = _time.time()
    with mlflow_utils.run("sentiment_v2", run_name=f"batch_{int(started)}",
                          tags={"kind": "inference_batch"}):
        annotated = analyze_sentiment(articles)
        OUTPUT_FILE.write_text(json.dumps(annotated, indent=2, default=str))

        counts: dict = {}
        for a in annotated:
            counts[a["Sentiment"]] = counts.get(a["Sentiment"], 0) + 1
        print(f"\nscored {len(annotated)} articles via {_backend} -> {OUTPUT_FILE}")
        for label in ["VERY_BAD", "BAD", "NEUTRAL", "GOOD", "EXCELLENT"]:
            print(f"  {label:10s} {counts.get(label, 0)}")

        mlflow_utils.log_params({
            "backend": _backend,
            "finbert_model": FINBERT_MODEL_ID,
            "input_articles": len(articles),
        })
        mlflow_utils.log_metrics({
            "scored_articles": len(annotated),
            "duration_sec": _time.time() - started,
            **{f"label_{k.lower()}_count": float(v) for k, v in counts.items()},
        })


if __name__ == "__main__":
    main()
