from django.apps import AppConfig


class AccountConfig(AppConfig):
    name = "account"

    def ready(self):
        # Import the signals so the auto-create-profile handler is
        # connected when Django starts.
        from . import signals  # noqa: F401
