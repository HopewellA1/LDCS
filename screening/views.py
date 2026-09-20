from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .consent import CURRENT_CONSENT_VERSION, get_active_consent, has_valid_consent
from .decorators import consent_required
from .forms import ConsentForm
from .models import ConsentRecord


@login_required
def dashboard(request):
    consent = get_active_consent(request.user)
    return render(request, "screening/dashboard.html", {"consent": consent})


@login_required
def consent(request):
    # Where to send the student after they consent (only ever a local URL).
    next_url = request.POST.get("next") or request.GET.get("next") or ""
    if not url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        next_url = ""

    if has_valid_consent(request.user):
        return redirect(next_url or "dashboard")

    if request.method == "POST":
        form = ConsentForm(request.POST)
        if form.is_valid():
            ConsentRecord.objects.create(
                user=request.user, version=CURRENT_CONSENT_VERSION
            )
            messages.success(request, "Thank you. Your consent has been recorded.")
            return redirect(next_url or "dashboard")
    else:
        form = ConsentForm()

    return render(
        request,
        "screening/consent.html",
        {"form": form, "next": next_url, "version": CURRENT_CONSENT_VERSION},
    )


@login_required
@require_POST
def withdraw_consent(request):
    withdrawn = request.user.consent_records.filter(
        withdrawn_at__isnull=True
    ).update(withdrawn_at=timezone.now())
    if withdrawn:
        messages.info(
            request,
            "Your consent has been withdrawn. You will need to consent again before starting a screening.",
        )
    return redirect("dashboard")


@consent_required
def screening_home(request):
    return render(request, "screening/screening_home.html")