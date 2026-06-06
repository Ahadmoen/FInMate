from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0013_add_performance_indexes"),
    ]

    operations = [
        # StockSignal: replace ASC index with DESC on generated_at so
        # DISTINCT ON (ticker) ORDER BY ticker ASC, generated_at DESC
        # can do an index-only scan instead of a full sort.
        migrations.RemoveIndex(
            model_name="stocksignal",
            name="idx_signal_ticker_gen",
        ),
        migrations.AddIndex(
            model_name="stocksignal",
            index=models.Index(fields=["ticker", "-generated_at"], name="idx_signal_ticker_gen_desc"),
        ),
        # StockForecast: same pattern — no index existed before.
        migrations.AddIndex(
            model_name="stockforecast",
            index=models.Index(fields=["ticker", "-forecast_date"], name="idx_forecast_ticker_date"),
        ),
    ]
