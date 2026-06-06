import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portfolio", "0002_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Remove unique_together before removing fields
        migrations.AlterUniqueTogether(
            name="holding",
            unique_together=set(),
        ),
        # Detach Holding from Portfolio
        migrations.RemoveField(
            model_name="holding",
            name="portfolio",
        ),
        # Detach Transaction from Portfolio, add user FK
        migrations.RemoveField(
            model_name="transaction",
            name="portfolio",
        ),
        migrations.AddField(
            model_name="transaction",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="transactions",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        # Drop old tables
        migrations.DeleteModel(
            name="Holding",
        ),
        migrations.DeleteModel(
            name="Portfolio",
        ),
        # Create portfolio_holdings
        migrations.CreateModel(
            name="PortfolioHolding",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("symbol", models.CharField(max_length=20)),
                ("quantity", models.DecimalField(decimal_places=2, max_digits=10)),
                ("avg_buy_price", models.DecimalField(decimal_places=2, max_digits=10)),
                ("added_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="portfolio_holdings",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "portfolio_holdings",
                "ordering": ["symbol"],
            },
        ),
        migrations.AlterUniqueTogether(
            name="portfolioholding",
            unique_together={("user", "symbol")},
        ),
    ]
