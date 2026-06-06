from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="notificationpreference",
            name="in_app_enabled",
            field=models.BooleanField(default=True),
        ),
    ]
