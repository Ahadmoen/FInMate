from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("alerts", "0004_alert_symbols"),
    ]

    operations = [
        migrations.AlterField(
            model_name="alertlog",
            name="channel",
            field=models.CharField(
                choices=[
                    ("WHATSAPP", "WhatsApp"),
                    ("EMAIL", "Email"),
                    ("SLACK", "Slack"),
                    ("PUSH", "Push"),
                ],
                max_length=10,
            ),
        ),
    ]
