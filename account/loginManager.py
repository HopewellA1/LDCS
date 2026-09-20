from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

UserModel = get_user_model()


class EmailOrUsernameBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username and "@" in username:
            matches = list(
                UserModel._default_manager.filter(email__iexact=username.strip())[:2]
            )
            if len(matches) == 1:
                username = matches[0].get_username()
        return super().authenticate(
            request, username=username, password=password, **kwargs
        )