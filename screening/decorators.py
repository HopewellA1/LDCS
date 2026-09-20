from functools import wraps

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import urlencode

from .consent import has_valid_consent


def consent_required(view_func):
    """
    Use on any view that collects or shows screening data.
    Not logged in  -> login page.
    No valid consent -> consent page, then back to where they were going.
    """

    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not has_valid_consent(request.user):
            query = urlencode({"next": request.get_full_path()})
            return redirect(f"{reverse('consent')}?{query}")
        return view_func(request, *args, **kwargs)

    return _wrapped