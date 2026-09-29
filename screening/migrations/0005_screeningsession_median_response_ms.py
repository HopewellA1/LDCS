from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("screening", "0004_screeningsession_ml_risk"),
    ]

    operations = [
        migrations.AddField(
            model_name="screeningsession",
            name="median_response_ms",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
