from decimal import Decimal

from rest_framework import serializers

from core.models import StockSymbol

from .models import PortfolioHolding, Transaction


class PortfolioHoldingWriteSerializer(serializers.ModelSerializer):
    """POST /api/v1/portfolio/holdings/ — accepts symbol_id, quantity, avg_buy_price.

    Validations:
      - symbol_id must reference an active StockSymbol
      - quantity > 0
      - avg_buy_price > 0
    Duplicate detection (unique_together user+symbol) is handled in the view
    so we can return a human-readable 400 instead of a 500.
    """

    symbol_id = serializers.PrimaryKeyRelatedField(
        source="symbol",
        queryset=StockSymbol.objects.filter(is_active=True),
    )

    class Meta:
        model = PortfolioHolding
        fields = ["symbol_id", "quantity", "avg_buy_price"]

    def validate_quantity(self, value: Decimal) -> Decimal:
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than 0.")
        return value

    def validate_avg_buy_price(self, value: Decimal) -> Decimal:
        if value <= 0:
            raise serializers.ValidationError("Average buy price must be greater than 0.")
        return value


class PortfolioHoldingUpdateSerializer(serializers.ModelSerializer):
    """PATCH /api/v1/portfolio/holdings/<id>/ — update quantity and avg_buy_price only.

    Symbol cannot be changed after a holding is created.
    """

    class Meta:
        model = PortfolioHolding
        fields = ["quantity", "avg_buy_price"]

    def validate_quantity(self, value: Decimal) -> Decimal:
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than 0.")
        return value

    def validate_avg_buy_price(self, value: Decimal) -> Decimal:
        if value <= 0:
            raise serializers.ValidationError("Average buy price must be greater than 0.")
        return value


class PortfolioHoldingReadSerializer(serializers.ModelSerializer):
    """GET response shape — holding details enriched with live price data.

    Live price fields (current_price, change_percent) come from subquery
    annotations added by get_holdings_enriched() in services.py.
    All computed P&L fields are derived from those annotated values.
    """

    symbol_id = serializers.UUIDField(source="symbol.id", read_only=True)
    ticker = serializers.CharField(source="symbol.ticker", read_only=True)
    name = serializers.CharField(source="symbol.company_name", read_only=True)
    industry = serializers.CharField(source="symbol.sector", read_only=True)

    total_invested = serializers.SerializerMethodField()
    current_price = serializers.SerializerMethodField()
    current_value = serializers.SerializerMethodField()
    change_percent = serializers.SerializerMethodField()
    unrealized_pnl = serializers.SerializerMethodField()
    return_pct = serializers.SerializerMethodField()
    price_updated_at = serializers.SerializerMethodField()

    class Meta:
        model = PortfolioHolding
        fields = [
            "id",
            "symbol_id",
            "ticker",
            "name",
            "industry",
            "quantity",
            "avg_buy_price",
            "total_invested",
            "current_price",
            "current_value",
            "change_percent",
            "unrealized_pnl",
            "return_pct",
            "price_updated_at",
            "added_at",
            "updated_at",
        ]

    # ── helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _qty(obj) -> float | None:
        try:
            return float(obj.quantity)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _price(obj) -> float | None:
        raw = getattr(obj, "live_current_price", None)
        if raw is None:
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    # ── computed fields ───────────────────────────────────────────────────────

    def get_total_invested(self, obj) -> float | None:
        qty = self._qty(obj)
        try:
            return round(qty * float(obj.avg_buy_price), 2) if qty is not None else None
        except (TypeError, ValueError):
            return None

    def get_current_price(self, obj) -> float | None:
        p = self._price(obj)
        return round(p, 4) if p is not None else None

    def get_current_value(self, obj) -> float | None:
        qty = self._qty(obj)
        p = self._price(obj)
        if qty is None or p is None:
            return None
        return round(qty * p, 2)

    def get_change_percent(self, obj) -> float | None:
        pct = getattr(obj, "live_change_pct", None)
        if pct is None:
            return None
        try:
            return round(float(pct), 4)
        except (TypeError, ValueError):
            return None

    def get_price_updated_at(self, obj) -> str | None:
        from core.market_utils import live_snapshot_updated_iso

        raw = getattr(obj, "live_price_updated_at", None)
        return live_snapshot_updated_iso(raw)

    def get_unrealized_pnl(self, obj) -> float | None:
        qty = self._qty(obj)
        p = self._price(obj)
        if qty is None or p is None:
            return None
        try:
            cost = qty * float(obj.avg_buy_price)
            return round(qty * p - cost, 2)
        except (TypeError, ValueError):
            return None

    def get_return_pct(self, obj) -> float | None:
        qty = self._qty(obj)
        p = self._price(obj)
        if qty is None or p is None:
            return None
        try:
            cost = qty * float(obj.avg_buy_price)
            if cost == 0:
                return None
            return round((qty * p - cost) / cost * 100, 2)
        except (TypeError, ValueError):
            return None


class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = [
            "id",
            "ticker",
            "type",
            "quantity",
            "price_at_time",
            "transacted_at",
            "is_sandbox",
        ]
        read_only_fields = ["id", "transacted_at"]
