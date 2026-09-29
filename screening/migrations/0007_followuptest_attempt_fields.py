from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("screening", "0006_followuptest_followupquestion"),
    ]

    operations = [
        migrations.AddField(
            model_name="followuptest",
            name="completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="followuptest",
            name="last_score",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="followuptest",
            name="passed",
            field=models.BooleanField(default=False),
        ),
    ]
