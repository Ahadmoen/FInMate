from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0015_merge_leaves"),
    ]

    operations = [
        migrations.AddField(
            model_name="newssentiment",
            name="industry",
            field=models.CharField(blank=True, default="", max_length=80),
        ),
        migrations.AddIndex(
            model_name="newssentiment",
            index=models.Index(
                fields=["industry", "published_at"],
                name="idx_news_industry_pub",
            ),
        ),
    ]
