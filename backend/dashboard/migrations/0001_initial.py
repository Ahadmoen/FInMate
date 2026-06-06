from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="DashboardCache",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("cache_key", models.CharField(max_length=255, unique=True)),
                ("data", models.JSONField()),
                ("cached_at", models.DateTimeField(auto_now=True)),
                ("expires_at", models.DateTimeField()),
            ],
            options={
                "db_table": "dashboard_cache",
            },
        ),
        migrations.AddIndex(
            model_name="dashboardcache",
            index=models.Index(fields=["expires_at"], name="idx_dashboard_cache_expires"),
        ),
    ]
