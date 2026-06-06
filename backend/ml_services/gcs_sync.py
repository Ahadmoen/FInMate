"""GCS sync for the model cache + pipeline output JSONs.

Layout in the bucket (set via the `GCS_BUCKET` env var):

    gs://{GCS_BUCKET}/
    ├── models/
    │   ├── lstm/{SYMBOL}.pt
    │   └── directional/{SYMBOL}_{H}d.pkl
    └── outputs/
        ├── stocks.json
        ├── forecasting_trend.json
        ├── news_sentiment.json
        └── historical_data.json

Auth via `GOOGLE_APPLICATION_CREDENTIALS` (service account JSON key path).
Service account needs *Storage Object Admin* on the bucket — bucket-level
metadata permissions are not required.

Public surface:
  * `upload_models()`        — push every per-symbol artifact under
                                `integrations/data/models/` to GCS.
                                Called at the end of cold runs.
  * `download_models()`      — pull every model object back to local disk.
                                Called on a fresh machine before the
                                first warm run if `models/` is empty.
  * `upload_outputs()`       — push the four pipeline-output JSONs to
                                `outputs/`. Called at the end of every
                                pipeline run (warm or cold).
  * `is_configured()`        — quick env-var check; lets callers decide
                                whether to skip GCS work in dev mode.

Behavior:
  * All uploads are concurrent (ThreadPoolExecutor, 8 workers) so a
    600-symbol cache pushes in ~30 s instead of ~10 min serial.
  * Each function is idempotent — re-running uploads overwrites; downloads
    skip files already present on disk with the same size.
  * Every function logs progress so a long sync is visible in the launcher
    output instead of opaque silence.
"""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "integrations" / "data"
MODEL_DIR = DATA_DIR / "models"

# Every pipeline-output JSON the Cloud Run Job produces.
# Bucket folder layout: gs://{bucket}/outputs/<filename>
LOCAL_OUTPUTS = {
    "outputs/stocks.json": DATA_DIR / "stocks.json",
    "outputs/forecasting_trend.json": DATA_DIR / "forecasting_trend.json",
    "outputs/news_sentiment.json": DATA_DIR / "news_sentiment.json",
    "outputs/news_data.json": DATA_DIR / "news_data.json",
    "outputs/stock_forecasts.json": DATA_DIR / "stock_forecasts.json",
    "outputs/best_models.json": DATA_DIR / "best_models.json",
    "outputs/directional_signals.json": DATA_DIR / "directional_signals.json",
    "outputs/daily_ratios.json": DATA_DIR / "daily_ratios.json",
    "outputs/fundamental_ratios.json": DATA_DIR / "fundamental_ratios.json",
    "outputs/live_data.json": DATA_DIR / "live_data.json",
    # Active-symbols filter — written by warm-4 _ingest_stocks() after each
    # forecast run. Lists the tickers that produced predictions in stocks.json.
    # Downstream scrapers (live / news / warm-1 / warm-2) intersect their
    # SYMBOLS list with this file at module load to skip dead/unforecastable
    # tickers, keeping per-run wall-time under the Cloud Run task timeout.
    "outputs/active_symbols.json": DATA_DIR / "active_symbols.json",
    # Per-ticker last real trading bar (Open/High/Low/Close/Volume/Date),
    # extracted by warm-1 from historical_data.json. Used by live_scraper
    # as the OHLC fallback when the PSX intraday endpoint returns no data
    # for a ticker — replaces the flat-LastClose stub with a real
    # prior-day bar so live_market_data shows natural OHLC + real volume.
    "outputs/last_bars.json": DATA_DIR / "last_bars.json",
}

# historical_data.json is special: too big for `outputs/` (327 MB) and
# is BOTH downloaded at run start and uploaded at run end. Lives at the
# bucket root so it's clearly the persistent input cache.
HISTORICAL_BLOB = "historical_data.json"
HISTORICAL_LOCAL = DATA_DIR / "historical_data.json"

UPLOAD_WORKERS = int(os.environ.get("GCS_UPLOAD_WORKERS", "8"))


def _bucket():
    """Lazy import so importing this module never fails when google-cloud
    isn't installed (e.g. in tests). Returns a `Bucket` handle."""
    bucket_name = os.environ.get("GCS_BUCKET")
    if not bucket_name:
        raise RuntimeError(
            "GCS_BUCKET env var not set. Either set it to your bucket name "
            "or call gcs_sync.is_configured() before invoking sync functions."
        )
    from google.cloud import storage
    return storage.Client().bucket(bucket_name)


def is_configured() -> bool:
    """True if GCS env vars are present. Cold/warm callers use this to
    skip GCS sync in dev mode without wrapping every call in try/except."""
    return bool(os.environ.get("GCS_BUCKET")) and bool(
        os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    )


# ---------- model artifacts ---------------------------------------------------

def _model_blob_path(local_path: Path) -> str:
    """Map `integrations/data/models/{SYM}/lstm.pt` → `models/lstm/{SYM}.pt`
    and `directional_Xd.pkl` → `models/directional/{SYM}_Xd.pkl`."""
    symbol = local_path.parent.name
    fname = local_path.name
    if fname == "lstm.pt":
        return f"models/lstm/{symbol}.pt"
    if fname.startswith("directional_") and fname.endswith(".pkl"):
        return f"models/directional/{symbol}_{fname[len('directional_'):]}"
    # Fallback — shouldn't hit for current cache shape but safe.
    return f"models/{local_path.relative_to(MODEL_DIR)}"


def _gather_model_files() -> list[Path]:
    if not MODEL_DIR.exists():
        return []
    out: list[Path] = []
    for p in MODEL_DIR.rglob("*"):
        if p.is_file() and (p.suffix == ".pt" or p.suffix == ".pkl"):
            out.append(p)
    return out


def upload_models() -> dict:
    """Push every model artifact under `integrations/data/models/` to GCS.

    Returns `{"uploaded": N, "skipped": 0, "bytes": M}`. Skipped is always
    zero today — we always overwrite — but the field is here so the
    caller's print statement stays stable if we add a skip-if-newer
    optimisation later."""
    bucket = _bucket()
    files = _gather_model_files()
    if not files:
        print("[gcs_sync] no model files to upload")
        return {"uploaded": 0, "skipped": 0, "bytes": 0}

    total_bytes = 0

    def _one(local: Path) -> int:
        blob = bucket.blob(_model_blob_path(local))
        blob.upload_from_filename(str(local))
        return local.stat().st_size

    print(f"[gcs_sync] uploading {len(files)} model files to gs://{bucket.name}/models/ …")
    with ThreadPoolExecutor(max_workers=UPLOAD_WORKERS) as ex:
        futures = {ex.submit(_one, f): f for f in files}
        for i, fut in enumerate(as_completed(futures), 1):
            try:
                total_bytes += fut.result()
            except Exception as exc:
                print(f"[gcs_sync]   FAILED {futures[fut].name}: {exc}")
            if i % 100 == 0:
                print(f"[gcs_sync]   {i}/{len(files)} done")

    print(f"[gcs_sync] uploaded {len(files)} files, {total_bytes / 1024 / 1024:.1f} MB")
    return {"uploaded": len(files), "skipped": 0, "bytes": total_bytes}


def download_models() -> dict:
    """Pull every model object from `gs://.../models/` to local disk.

    Skips files that already exist locally with the same size — so this
    is safe to call unconditionally at the start of warm runs; only
    missing files actually transfer."""
    bucket = _bucket()
    blobs = list(bucket.list_blobs(prefix="models/"))
    if not blobs:
        print("[gcs_sync] no model blobs in bucket — nothing to download")
        return {"downloaded": 0, "skipped": 0, "bytes": 0}

    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    def _local_path_for(blob_name: str) -> Path | None:
        # models/lstm/{SYM}.pt → integrations/data/models/{SYM}/lstm.pt
        # models/directional/{SYM}_Xd.pkl → integrations/data/models/{SYM}/directional_Xd.pkl
        parts = blob_name.split("/")
        if len(parts) != 3:
            return None
        _, kind, fname = parts
        if kind == "lstm" and fname.endswith(".pt"):
            symbol = fname[:-len(".pt")]
            return MODEL_DIR / symbol / "lstm.pt"
        if kind == "directional" and fname.endswith(".pkl"):
            stem = fname[:-len(".pkl")]
            if "_" not in stem:
                return None
            symbol, suffix = stem.rsplit("_", 1)
            return MODEL_DIR / symbol / f"directional_{suffix}.pkl"
        return None

    downloaded = 0
    skipped = 0
    total_bytes = 0

    def _one(blob) -> tuple[bool, int]:
        local = _local_path_for(blob.name)
        if local is None:
            return False, 0
        if local.exists() and local.stat().st_size == blob.size:
            return False, 0  # skip identical
        local.parent.mkdir(parents=True, exist_ok=True)
        blob.download_to_filename(str(local))
        return True, local.stat().st_size

    print(f"[gcs_sync] checking {len(blobs)} model blobs against local cache …")
    with ThreadPoolExecutor(max_workers=UPLOAD_WORKERS) as ex:
        futures = [ex.submit(_one, b) for b in blobs]
        for i, fut in enumerate(as_completed(futures), 1):
            try:
                did_download, size = fut.result()
                if did_download:
                    downloaded += 1
                    total_bytes += size
                else:
                    skipped += 1
            except Exception as exc:
                print(f"[gcs_sync]   FAILED: {exc}")
            if i % 200 == 0:
                print(f"[gcs_sync]   {i}/{len(blobs)} processed")

    print(
        f"[gcs_sync] downloaded {downloaded} new, skipped {skipped} unchanged "
        f"({total_bytes / 1024 / 1024:.1f} MB)"
    )
    return {"downloaded": downloaded, "skipped": skipped, "bytes": total_bytes}


# ---------- pipeline output JSONs ---------------------------------------------

def upload_outputs(only: list[str] | None = None) -> dict:
    """Push pipeline-output JSONs to `gs://.../outputs/`.

    Idempotent: each daily run overwrites yesterday's file under the
    same blob path. Files that don't exist locally are skipped.

    Args:
        only: optional whitelist of basenames (e.g. ['stocks.json',
              'forecasting_trend.json']). If given, only those JSONs
              are uploaded — used by the split Cloud Run Jobs that each
              own a subset of outputs.
    """
    bucket = _bucket()
    uploaded = 0
    skipped = 0
    total_bytes = 0

    for blob_path, local in LOCAL_OUTPUTS.items():
        if only is not None and local.name not in only:
            continue
        if not local.exists():
            print(f"[gcs_sync] skip {blob_path} (not present locally)")
            skipped += 1
            continue
        size = local.stat().st_size
        bucket.blob(blob_path).upload_from_filename(str(local))
        print(f"[gcs_sync] uploaded {blob_path} ({size / 1024 / 1024:.2f} MB)")
        uploaded += 1
        total_bytes += size

    return {"uploaded": uploaded, "skipped": skipped, "bytes": total_bytes}


def download_outputs(only: list[str] | None = None) -> dict:
    """Pull pipeline-output JSONs from `gs://.../outputs/` to local disk.

    Used by Cloud Run Jobs that consume what an earlier Job wrote (e.g.
    finmate-ml-fuse pulls scrapers' outputs; finmate-ingest pulls
    fuse's stocks.json).

    Args:
        only: optional whitelist of basenames. If given, only those
              JSONs are downloaded.
    """
    bucket = _bucket()
    downloaded = 0
    missing = 0
    total_bytes = 0

    for blob_path, local in LOCAL_OUTPUTS.items():
        if only is not None and local.name not in only:
            continue
        blob = bucket.blob(blob_path)
        if not blob.exists():
            print(f"[gcs_sync] {blob_path} not in bucket — skipping")
            missing += 1
            continue
        local.parent.mkdir(parents=True, exist_ok=True)
        blob.download_to_filename(str(local))
        size = local.stat().st_size
        print(f"[gcs_sync] downloaded {blob_path} ({size / 1024 / 1024:.2f} MB)")
        downloaded += 1
        total_bytes += size

    return {"downloaded": downloaded, "missing": missing, "bytes": total_bytes}


# ---------- historical_data.json (the big persistent input) -------------------

def upload_historical() -> dict:
    """Push integrations/data/historical_data.json to gs://.../historical_data.json.

    Called at the end of warm/cold runs — the scraper has just appended
    today's bars, so the bucket gets the updated cache for tomorrow's
    run to download."""
    if not HISTORICAL_LOCAL.exists():
        print("[gcs_sync] historical_data.json not present locally — skip")
        return {"uploaded": 0, "bytes": 0}
    bucket = _bucket()
    size = HISTORICAL_LOCAL.stat().st_size
    bucket.blob(HISTORICAL_BLOB).upload_from_filename(str(HISTORICAL_LOCAL))
    print(f"[gcs_sync] uploaded {HISTORICAL_BLOB} ({size / 1024 / 1024:.1f} MB)")
    return {"uploaded": 1, "bytes": size}


def download_historical() -> dict:
    """Pull gs://.../historical_data.json to local. Skip if local is
    same size — lets the entrypoint call this unconditionally without
    redownloading on retries."""
    bucket = _bucket()
    blob = bucket.blob(HISTORICAL_BLOB)
    blob.reload()  # populate .size
    if HISTORICAL_LOCAL.exists() and HISTORICAL_LOCAL.stat().st_size == blob.size:
        print(f"[gcs_sync] historical_data.json already current locally — skip")
        return {"downloaded": 0, "skipped": 1, "bytes": 0}
    HISTORICAL_LOCAL.parent.mkdir(parents=True, exist_ok=True)
    blob.download_to_filename(str(HISTORICAL_LOCAL))
    size = HISTORICAL_LOCAL.stat().st_size
    print(f"[gcs_sync] downloaded historical_data.json ({size / 1024 / 1024:.1f} MB)")
    return {"downloaded": 1, "skipped": 0, "bytes": size}


# ---------- entrypoint --------------------------------------------------------

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="GCS sync for FinMate models + outputs")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("upload-models", help="Push integrations/data/models/ to GCS")
    sub.add_parser("download-models", help="Pull GCS models/ to integrations/data/models/")
    up = sub.add_parser("upload-outputs", help="Push per-run JSONs to GCS outputs/ (overwrites)")
    up.add_argument("--only", help="Comma-separated basenames to upload (e.g. stocks.json,forecasting_trend.json)")
    dn = sub.add_parser("download-outputs", help="Pull JSONs from GCS outputs/ to local")
    dn.add_argument("--only", help="Comma-separated basenames to download")
    sub.add_parser("upload-historical", help="Push historical_data.json to GCS")
    sub.add_parser("download-historical", help="Pull historical_data.json from GCS")
    args = parser.parse_args()

    def _split(s):
        return [x.strip() for x in s.split(",")] if s else None

    if args.cmd == "upload-models":
        upload_models()
    elif args.cmd == "download-models":
        download_models()
    elif args.cmd == "upload-outputs":
        upload_outputs(only=_split(args.only))
    elif args.cmd == "download-outputs":
        download_outputs(only=_split(args.only))
    elif args.cmd == "upload-historical":
        upload_historical()
    elif args.cmd == "download-historical":
        download_historical()
