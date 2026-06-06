"""
Idempotent seeder for local development.

Usage:
    python manage.py seed_data

Creates:
  1. Superuser admin / admin123
  2. Test user testuser / test123 with NotificationPreference (all channels on)
  3. Ten StockSymbol rows for the default universe
  4. A Portfolio for testuser with three Holdings (AAPL/MSFT/TSLA)
  5. One HOLD StockSignal per symbol with reason "Awaiting ML integration"
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from alerts.models import Alert  # noqa: F401  (ensures app is loaded)
from core.models import StockSignal, StockSymbol
from portfolio.models import PortfolioHolding
from users.models import NotificationPreference


User = get_user_model()


SEED_SYMBOLS = [
    ("AAPL", "Apple Inc.", "Technology"),
    ("MSFT", "Microsoft Corporation", "Technology"),
    ("GOOGL", "Alphabet Inc.", "Communication Services"),
    ("AMZN", "Amazon.com, Inc.", "Consumer Discretionary"),
    ("TSLA", "Tesla, Inc.", "Consumer Discretionary"),
    ("META", "Meta Platforms, Inc.", "Communication Services"),
    ("NVDA", "NVIDIA Corporation", "Technology"),
    ("JPM", "JPMorgan Chase & Co.", "Financials"),
    ("NFLX", "Netflix, Inc.", "Communication Services"),
    ("BRK-B", "Berkshire Hathaway Inc.", "Financials"),
]


SEED_HOLDINGS = [
    ("AAPL", Decimal("10"), Decimal("180")),
    ("MSFT", Decimal("5"), Decimal("350")),
    ("TSLA", Decimal("8"), Decimal("250")),
]


class Command(BaseCommand):
    help = "Seed FinMate with admin/test user, default symbols, sample portfolio and signals."

    def handle(self, *args, **options):
        self._seed_superuser()
        self._seed_test_user()
        self._seed_symbols()
        self._seed_portfolio()
        self._seed_signals()
        self.stdout.write(self.style.SUCCESS("Seeding complete."))

    def _seed_superuser(self):
        if User.objects.filter(username="admin").exists():
            self.stdout.write("Superuser 'admin' already exists — skipping.")
            return
        User.objects.create_superuser(
            username="admin",
            email="admin@finmate.com",
            password="admin123",
        )
        self.stdout.write(self.style.SUCCESS("Created superuser admin / admin123."))

    def _seed_test_user(self):
        user, created = User.objects.get_or_create(
            username="testuser",
            defaults={"email": "test@finmate.com"},
        )
        if created:
            user.set_password("test123")
            user.save()
            self.stdout.write(self.style.SUCCESS("Created test user testuser / test123."))
        else:
            self.stdout.write("Test user 'testuser' already exists — skipping.")

        prefs, _ = NotificationPreference.objects.get_or_create(user=user)
        prefs.email_enabled = True
        prefs.whatsapp_enabled = True
        prefs.slack_enabled = True
        prefs.pre_market = True
        prefs.mid_session = True
        prefs.post_market = True
        prefs.save()
        self.stdout.write(self.style.SUCCESS("Configured notification preferences for testuser."))

    def _seed_symbols(self):
        created_count = 0
        for ticker, name, sector in SEED_SYMBOLS:
            _, created = StockSymbol.objects.get_or_create(
                ticker=ticker,
                defaults={
                    "company_name": name,
                    "sector": sector,
                    "is_active": True,
                },
            )
            if created:
                created_count += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {created_count} new stock symbols (total: {StockSymbol.objects.count()})."
            )
        )

    def _seed_portfolio(self):
        user = User.objects.filter(username="testuser").first()
        if not user:
            self.stdout.write(self.style.WARNING("testuser not found — skipping portfolio seed."))
            return

        for ticker, qty, price in SEED_HOLDINGS:
            stock = StockSymbol.objects.filter(ticker=ticker).first()
            if not stock:
                self.stdout.write(self.style.WARNING(f"{ticker} not in stock_symbol — skipping."))
                continue
            PortfolioHolding.objects.get_or_create(
                user=user,
                symbol=stock,
                defaults={"quantity": qty, "avg_buy_price": price},
            )

        self.stdout.write(self.style.SUCCESS("Seeded portfolio holdings for testuser."))

    def _seed_signals(self):
        valid_until = timezone.now() + timedelta(days=1)
        created_count = 0
        for ticker, _, _ in SEED_SYMBOLS:
            if StockSignal.objects.filter(ticker=ticker).exists():
                continue
            StockSignal.objects.create(
                ticker=ticker,
                signal=StockSignal.Signal.HOLD,
                confidence=0.5,
                reason="Awaiting ML integration",
                forecast_score=0.0,
                sentiment_score=0.0,
                valid_until=valid_until,
            )
            created_count += 1
        self.stdout.write(
            self.style.SUCCESS(f"Seeded {created_count} new stock signals.")
        )
