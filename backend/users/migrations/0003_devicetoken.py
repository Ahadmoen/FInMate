import django.db.models.deletion
import uuid

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0002_notificationpreference_in_app_enabled"),
    ]

    operations = [
        migrations.CreateModel(
            name="DeviceToken",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("token", models.TextField()),
                ("platform", models.CharField(
                    blank=True,
                    choices=[("ios", "iOS"), ("android", "Android")],
                    max_length=10,
                )),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="device_tokens",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                "db_table": "device_token",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AlterUniqueTogether(
            name="devicetoken",
            unique_together={("user", "token")},
        ),
    ]
