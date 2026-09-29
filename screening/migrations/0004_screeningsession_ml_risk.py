from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("screening", "0003_referral"),
    ]

    operations = [
        migrations.AddField(
            model_name="screeningsession",
            name="ml_risk",
            field=models.CharField(
                blank=True,
                choices=[("low", "Low"), ("medium", "Medium"), ("high", "High")],
                max_length=10,
            ),
        ),
    ]
