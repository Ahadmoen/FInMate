import uuid

from django.conf import settings
from django.db import models

from core.models import StockSymbol, TimestampMixin


class PortfolioHolding(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="portfolio_holdings",
    )
    symbol = models.ForeignKey(
        StockSymbol,
        on_delete=models.PROTECT,
        related_name="holdings",
        db_column="symbol_id",
    )
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    avg_buy_price = models.DecimalField(max_digits=10, decimal_places=2)
    added_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "portfolio_holdings"
        unique_together = ("user", "symbol")
        ordering = ["symbol"]

    def __str__(self):
        return f"{self.user.username}/{self.symbol.ticker} x {self.quantity}"


class Transaction(TimestampMixin):
    class Type(models.TextChoices):
        BUY = "BUY", "Buy"
        SELL = "SELL", "Sell"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="transactions",
        null=True,
        blank=True,
    )
    ticker = models.CharField(max_length=10)
    type = models.CharField(max_length=4, choices=Type.choices)
    quantity = models.DecimalField(max_digits=12, decimal_places=4)
    price_at_time = models.DecimalField(max_digits=12, decimal_places=4)
    transacted_at = models.DateTimeField(auto_now_add=True)
    is_sandbox = models.BooleanField(default=False)

    class Meta:
        db_table = "transaction"
        ordering = ["-transacted_at"]

    def __str__(self):
        return f"{self.type} {self.ticker} x {self.quantity} @ {self.price_at_time}"
