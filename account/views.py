from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth.views import (
    PasswordChangeView,
    PasswordResetConfirmView,
    PasswordResetView,
)
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import redirect, render
from django.urls import reverse_lazy

from .forms import (
    SignupForm,
    StyledPasswordChangeForm,
    StyledPasswordResetForm,
    StyledSetPasswordForm,
)


def signup(request):
    if request.user.is_authenticated:
        return redirect(settings.LOGIN_REDIRECT_URL)

    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            messages.success(request, f"Welcome to LDCS, {user.get_username()}!")
            return redirect(settings.LOGIN_REDIRECT_URL)
    else:
        form = SignupForm()

    return render(request, "account/signup.html", {"form": form})


class ChangePasswordView(SuccessMessageMixin, PasswordChangeView):
    template_name = "account/changePassword.html"
    form_class = StyledPasswordChangeForm
    success_url = reverse_lazy("home")
    success_message = "Your password was changed successfully."


class ForgotPasswordView(PasswordResetView):
    template_name = "account/password_reset_form.html"
    form_class = StyledPasswordResetForm
    email_template_name = "account/emails/password_reset_email.txt"
    html_email_template_name = "account/emails/password_reset_email.html"
    subject_template_name = "account/emails/password_reset_subject.txt"
    extra_email_context = {"expiry_minutes": settings.PASSWORD_RESET_TIMEOUT // 60}


class ResetPasswordConfirmView(PasswordResetConfirmView):
    template_name = "account/password_reset_confirm.html"
    form_class = StyledSetPasswordForm