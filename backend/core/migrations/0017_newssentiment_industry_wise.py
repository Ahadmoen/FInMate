from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0016_newssentiment_industry"),
    ]

    operations = [
        migrations.AddField(
            model_name="newssentiment",
            name="industry_wise",
            field=models.CharField(blank=True, default="", max_length=40),
        ),
        migrations.AddIndex(
            model_name="newssentiment",
            index=models.Index(
                fields=["industry_wise", "published_at"],
                name="idx_news_indwise_pub",
            ),
        ),
    ]
