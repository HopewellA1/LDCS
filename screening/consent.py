CURRENT_CONSENT_VERSION = "1.0"


def get_active_consent(user):
    """The user's current, not-withdrawn consent for the latest text, or None."""
    if not user.is_authenticated:
        return None
    return user.consent_records.filter(
        version=CURRENT_CONSENT_VERSION,
        withdrawn_at__isnull=True,
    ).first()


def has_valid_consent(user):
    return get_active_consent(user) is not None