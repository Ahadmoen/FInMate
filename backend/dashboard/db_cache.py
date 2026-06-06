import threading
from datetime import timedelta

from django.db import close_old_connections
from django.utils import timezone


def db_cache_get(key: str):
    """Return (data, is_stale). data is None on complete miss."""
    from dashboard.models import DashboardCache
    try:
        entry = DashboardCache.objects.get(cache_key=key)
        return entry.data, entry.expires_at < timezone.now()
    except DashboardCache.DoesNotExist:
        return None, False


def db_cache_delete(key: str) -> None:
    from dashboard.models import DashboardCache

    DashboardCache.objects.filter(cache_key=key).delete()


def db_cache_set(key: str, data: dict, timeout: int) -> None:
    from dashboard.models import DashboardCache
    # DashboardCache.data is NOT NULL — never try to persist a null payload
    # (a compute_fn returning None would otherwise raise IntegrityError and
    # 500 the whole dashboard). Skip caching; the value is still returned.
    if data is None:
        return
    now = timezone.now()
    expires_at = now + timedelta(seconds=timeout)
    DashboardCache.objects.filter(expires_at__lt=now).delete()
    DashboardCache.objects.update_or_create(
        cache_key=key,
        defaults={"data": data, "expires_at": expires_at},
    )


def db_cache_get_or_compute(key: str, compute_fn, timeout: int):
    """
    Stale-while-revalidate:
    - Fresh hit  → return immediately.
    - Stale hit  → return stale data, kick off background recompute.
    - Miss       → compute synchronously, store, return.
    """
    data, is_stale = db_cache_get(key)
    if data is not None:
        if is_stale:
            threading.Thread(
                target=_background_refresh,
                args=(key, compute_fn, timeout),
                daemon=True,
            ).start()
        return data

    result = compute_fn()
    db_cache_set(key, result, timeout)
    return result


def _background_refresh(key: str, compute_fn, timeout: int) -> None:
    close_old_connections()
    try:
        result = compute_fn()
        db_cache_set(key, result, timeout)
    finally:
        close_old_connections()
