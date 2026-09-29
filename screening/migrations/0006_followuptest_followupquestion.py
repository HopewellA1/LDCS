import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("screening", "0005_screeningsession_median_response_ms"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="FollowUpTest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("domain", models.CharField(choices=[("math", "Numeracy"), ("reading", "Reading fluency"), ("writing", "Writing & language"), ("memory", "Working memory"), ("scenario", "Executive function")], max_length=20)),
                ("title", models.CharField(max_length=120)),
                ("note", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="follow_up_tests_created", to=settings.AUTH_USER_MODEL)),
                ("student", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="follow_up_tests", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="FollowUpQuestion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("prompt", models.CharField(max_length=300)),
                ("option_a", models.CharField(max_length=200)),
                ("option_b", models.CharField(max_length=200)),
                ("option_c", models.CharField(blank=True, max_length=200)),
                ("option_d", models.CharField(blank=True, max_length=200)),
                ("correct_index", models.PositiveSmallIntegerField(choices=[(0, "A"), (1, "B"), (2, "C"), (3, "D")], default=0, help_text="Which option is correct: A, B, C or D.")),
                ("order", models.PositiveSmallIntegerField(default=0)),
                ("test", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="questions", to="screening.followuptest")),
            ],
            options={"ordering": ["order", "id"]},
        ),
    ]
