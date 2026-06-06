import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
        ("portfolio", "0003_portfolio_holdings"),
    ]

    operations = [
        # Drop old varchar symbol column
        migrations.AlterUniqueTogether(
            name="portfolioholding",
            unique_together=set(),
        ),
        migrations.RemoveField(
            model_name="portfolioholding",
            name="symbol",
        ),
        # Add FK to stock_symbol
        migrations.AddField(
            model_name="portfolioholding",
            name="symbol",
            field=models.ForeignKey(
                db_column="symbol_id",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="holdings",
                to="core.stocksymbol",
            ),
            preserve_default=False,
        ),
        migrations.AlterUniqueTogether(
            name="portfolioholding",
            unique_together={("user", "symbol")},
        ),
    ]
