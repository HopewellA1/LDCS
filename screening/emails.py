"""Outgoing email for the screening app."""

import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse

logger = logging.getLogger(__name__)


def send_survey_email(request, user):
    """
    Send the Disability Rights Unit survey-invitation email to a student
    after they finish a screening.

    Sends an HTML email with a plain-text fallback. Returns True only if the
    email was actually handed to the backend, False if the student has no
    address on file or the send failed.

    A mail problem must never break the screening flow, so any error is
    caught and logged (not swallowed silently) rather than raised. Note: with
    the console/file email backend (development) the message is written to the
    terminal or the sent_emails/ folder, not delivered to a real inbox - see
    settings.py for how to switch to real SMTP delivery.
    """
    if not user.email:
        logger.warning("Survey email skipped: user %s has no email address.", user)
        return False

    # Absolute links so they work from an inbox. The "portal" button takes
    # the student to their results page (which prompts login if needed).
    context = {
        "portal_url": request.build_absolute_uri(reverse("results")),
        "unsubscribe_url": request.build_absolute_uri(reverse("home")),
    }

    subject = "Students with Disabilities Survey 2026 - Disability Rights Unit"
    text_body = render_to_string("screening/emails/survey_email.txt", context)
    html_body = render_to_string("screening/emails/survey_email.html", context)

    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    message.attach_alternative(html_body, "text/html")

    try:
        # fail_silently=False so real errors reach the except below and get
        # logged, instead of vanishing.
        sent = message.send(fail_silently=False)
    except Exception:
        logger.exception("Survey email to %s failed to send.", user.email)
        return False
    return bool(sent)
