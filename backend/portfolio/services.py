from django.db.models import DateTimeField, FloatField, OuterRef, Subquery

from core.models import LiveMarketData

from .models import PortfolioHolding


def get_holdings_enriched(user):
    """Return the authenticated user's holdings annotated with live price data.

    Each row gains two extra attributes via subquery (single DB round-trip):
      - ``live_current_price``  Decimal  — latest LiveMarketData.close for the ticker
      - ``live_change_pct``     Float    — latest LiveMarketData.change_pct for the ticker

    The serializer derives total_invested, current_value, unrealized_pnl, and
    return_pct from these values so no extra queries are needed per holding.
    """
    latest_bar = (
        LiveMarketData.objects
        .filter(ticker=OuterRef("symbol__ticker"))
        .order_by("-date")
    )

    return (
        PortfolioHolding.objects
        .filter(user=user)
        .select_related("symbol")
        .annotate(
            live_current_price=Subquery(latest_bar.values("close")[:1]),
            live_change_pct=Subquery(
                latest_bar.values("change_pct")[:1],
                output_field=FloatField(),
            ),
            live_price_updated_at=Subquery(
                latest_bar.values("updated_at")[:1],
                output_field=DateTimeField(),
            ),
        )
        .order_by("symbol__ticker")
    )


def compute_analytics_stub(user) -> dict:
    holdings_count = PortfolioHolding.objects.filter(user=user).count()
    return {
        "sharpe_ratio": 0.0,
        "beta": 0.0,
        "value_at_risk": 0.0,
        "holdings_count": holdings_count,
        "note": "Placeholder analytics — replace with real metrics.",
    }
