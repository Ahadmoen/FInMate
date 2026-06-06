"""Drop dashboard caches that depend on the user's portfolio holdings."""

from .db_cache import db_cache_delete


def invalidate_dashboard_portfolio_health(user) -> None:
    """Call after holdings are created, updated, or deleted."""
    uid = user.pk
    db_cache_delete(f"dashboard:portfolio_health:v2:{uid}")
    db_cache_delete(f"dashboard:portfolio_health:{uid}")
