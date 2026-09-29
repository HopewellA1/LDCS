from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Profile


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_profile_for_new_user(sender, instance, created, **kwargs):
    """
    Give every new user a Profile automatically.

    `created` is True only the first time a user is saved, so existing
    users are never touched. New users default to the Student role
    (set on the Profile model).
    """
    if created:
        Profile.objects.create(user=instance)
