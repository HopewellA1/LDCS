from django.conf import settings
from django.db import models
from django.utils import timezone


class ConsentRecord(models.Model):
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="consent_records",
    )
    version = models.CharField(max_length=20)
    accepted_at = models.DateTimeField(default=timezone.now)
    withdrawn_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-accepted_at"]

    def __str__(self):
        state = "withdrawn" if self.withdrawn_at else "active"
        return f"{self.user} - v{self.version} ({state})"