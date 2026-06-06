"""Shared helpers for live market snapshot fields."""

from django.utils import timezone as dj_tz


def effective_change_pct(change_pct, open_price, close) -> float | None:
    """Day change % from DB, or session open→close when stored value is 0/null."""
    pct: float | None
    try:
        pct = None if change_pct is None else float(change_pct)
    except (TypeError, ValueError):
        pct = None

    if pct is not None and pct != 0:
        return pct

    if open_price is not None and close is not None:
        try:
            o, c = float(open_price), float(close)
            if o > 0:
                computed = (c - o) / o * 100.0
                if abs(computed) >= 1e-9:
                    return round(computed, 4)
        except (TypeError, ValueError):
            pass

    return pct


def live_snapshot_updated_iso(dt) -> str | None:
    """ISO timestamp for when the live row was last written (DB ``updated_at``).

    Use this for "Updated …" UI — not ``LiveMarketData.date``, which is the
    hourly bar bucket (often floored to the top of the hour).
    """
    if dt is None:
        return None
    if dj_tz.is_naive(dt):
        dt = dj_tz.make_aware(dt, dj_tz.get_current_timezone())
    return dt.isoformat()
