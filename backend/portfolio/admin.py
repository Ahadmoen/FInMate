from django.contrib import admin

from .models import PortfolioHolding, Transaction


@admin.register(PortfolioHolding)
class PortfolioHoldingAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "symbol", "quantity", "avg_buy_price", "updated_at")
    list_filter = ("symbol",)
    search_fields = ("symbol", "user__username")


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "ticker",
        "type",
        "quantity",
        "price_at_time",
        "is_sandbox",
        "transacted_at",
    )
    list_filter = ("type", "is_sandbox")
    search_fields = ("ticker", "user__username")
