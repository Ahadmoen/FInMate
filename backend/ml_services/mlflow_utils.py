"""MLflow integration helpers.

Centralizes tracking-URI + auth setup so each ML script can opt in with
one decorator/context manager. Safe to call when MLflow env vars are
unset — `tracking_enabled()` returns False and all helpers become no-ops
so local dev / CI without DagsHub credentials still runs cleanly.

**Non-fatal by design**: every call swallows exceptions. If the tracking
server returns 500 / times out / refuses auth, the training script
continues unaffected — models still train, artifacts still write to
disk, just nothing lands in MLflow. The alternative (letting MLflow
exceptions kill a 5-hour cold retrain after symbol 8) is worse than
losing tracking data.

Env vars (set these via .env or process env):
  MLFLOW_TRACKING_URI       e.g. https://dagshub.com/<user>/<repo>.mlflow
  MLFLOW_TRACKING_USERNAME  DagsHub username
  MLFLOW_TRACKING_PASSWORD  DagsHub access token (NOT the account password)

The DagsHub MLflow tracking server reads basic-auth headers via the
standard MLFLOW_TRACKING_USERNAME / MLFLOW_TRACKING_PASSWORD pair, so no
extra `dagshub` SDK install is required — vanilla `mlflow` is enough.
"""
from __future__ import annotations

import contextlib
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

try:
    import mlflow  # type: ignore
    _MLFLOW_IMPORTED = True
except ImportError:
    mlflow = None  # type: ignore
    _MLFLOW_IMPORTED = False

# Disable runaway retries inside mlflow's own HTTP layer — 2 retries is
# plenty; the default (5+) compounds delays when the server is flaky.
os.environ.setdefault("MLFLOW_HTTP_REQUEST_MAX_RETRIES", "2")
os.environ.setdefault("MLFLOW_HTTP_REQUEST_TIMEOUT", "10")

# Once we've seen N consecutive MLflow failures, disable tracking for
# the rest of this process. Avoids retrying for every per-symbol run
# when the server is clearly down.
_consecutive_failures = 0
_DISABLE_THRESHOLD = int(os.environ.get("MLFLOW_DISABLE_AFTER_FAILURES", "5"))
_tracking_disabled = False


def tracking_enabled() -> bool:
    """Tracking is enabled iff mlflow is installed AND a tracking URI is set
    AND we haven't tripped the consecutive-failure circuit breaker."""
    return (
        _MLFLOW_IMPORTED
        and bool(os.environ.get("MLFLOW_TRACKING_URI"))
        and not _tracking_disabled
    )


def _record_success() -> None:
    global _consecutive_failures
    _consecutive_failures = 0


def _record_failure(op: str, exc: BaseException) -> None:
    """Log + count a failure. Trips the circuit breaker if too many in a row."""
    global _consecutive_failures, _tracking_disabled
    _consecutive_failures += 1
    short = repr(exc).split("\n")[0][:160]
    logger.warning(
        "mlflow %s failed (%d/%d): %s",
        op, _consecutive_failures, _DISABLE_THRESHOLD, short,
    )
    print(f"  [mlflow warn] {op} failed: {short}")
    if _consecutive_failures >= _DISABLE_THRESHOLD:
        _tracking_disabled = True
        logger.warning(
            "mlflow disabled for the rest of this process — %d consecutive failures",
            _consecutive_failures,
        )
        print(
            f"  [mlflow warn] disabling tracking after {_consecutive_failures} "
            "consecutive failures; training continues without MLflow"
        )


def configure(experiment: str) -> bool:
    """Point MLflow at the configured tracking server + experiment.

    Returns True if tracking is active, False if env vars are missing
    or the tracking server is unreachable."""
    if not tracking_enabled():
        return False
    try:
        mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
        mlflow.set_experiment(experiment)
        _record_success()
        return True
    except Exception as exc:
        _record_failure(f"configure({experiment})", exc)
        return False


@contextlib.contextmanager
def run(experiment: str, run_name: str, *, nested: bool = False, tags: dict | None = None):
    """Context manager that opens an MLflow run when tracking is enabled.
    Yields None and is a no-op if tracking is disabled OR if the
    server fails to start the run. Exceptions inside the `with` block
    propagate normally — only MLflow's own API calls are swallowed."""
    if not configure(experiment):
        yield None
        return
    try:
        active = mlflow.start_run(run_name=run_name, nested=nested)
    except Exception as exc:
        _record_failure(f"start_run({run_name})", exc)
        yield None
        return
    try:
        if tags:
            try:
                mlflow.set_tags(tags)
            except Exception as exc:
                _record_failure("set_tags", exc)
        _record_success()
        yield active
    finally:
        try:
            mlflow.end_run()
        except Exception as exc:
            _record_failure(f"end_run({run_name})", exc)


def log_params(params: dict[str, Any]) -> None:
    if not tracking_enabled():
        return
    try:
        if mlflow.active_run() is None:
            return
        mlflow.log_params({k: v for k, v in params.items() if v is not None})
        _record_success()
    except Exception as exc:
        _record_failure("log_params", exc)


def log_metrics(metrics: dict[str, float]) -> None:
    if not tracking_enabled():
        return
    try:
        if mlflow.active_run() is None:
            return
        clean = {k: float(v) for k, v in metrics.items()
                 if v is not None and isinstance(v, (int, float)) and not _is_nan(v)}
        if clean:
            mlflow.log_metrics(clean)
            _record_success()
    except Exception as exc:
        _record_failure("log_metrics", exc)


def log_artifact(path: str | os.PathLike, artifact_path: str | None = None) -> None:
    if not tracking_enabled():
        return
    try:
        if mlflow.active_run() is None:
            return
        mlflow.log_artifact(str(path), artifact_path=artifact_path)
        _record_success()
    except Exception as exc:
        _record_failure(f"log_artifact({path})", exc)


def _is_nan(v: float) -> bool:
    try:
        return v != v  # NaN is the only float not equal to itself
    except Exception:
        return False
