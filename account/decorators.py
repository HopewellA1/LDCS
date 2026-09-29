from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def educator_required(view_func):
    """
    Use on any view only educators (or admins) should see, such as the
    dashboard that lists students and their results.

    Not logged in   -> login page (handled by login_required).
    Logged in student -> 403 Forbidden (they can't view other people's data).
    Educator/admin  -> allowed through.
    """

    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        profile = getattr(request.user, "profile", None)
        if profile is None or not profile.is_educator:
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return _wrapped
