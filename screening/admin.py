from django.contrib import admin

from .models import ConsentRecord, DomainResult, Referral, ScreeningSession


@admin.register(ConsentRecord)
class ConsentRecordAdmin(admin.ModelAdmin):
    list_display = ("user", "version", "accepted_at", "withdrawn_at")
    list_filter = ("version",)
    search_fields = ("user__username", "user__email")
    readonly_fields = ("user", "version", "accepted_at", "withdrawn_at")

    # Consent records are an audit trail: view only.
    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class DomainResultInline(admin.TabularInline):
    """Show a session's per-domain scores on the session page."""

    model = DomainResult
    extra = 0
    readonly_fields = ("domain", "score", "flagged", "detail")
    can_delete = False


@admin.register(ScreeningSession)
class ScreeningSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "student", "started_at", "completed_at", "flagged_count")
    search_fields = ("student__username", "student__email")
    inlines = [DomainResultInline]


@admin.register(DomainResult)
class DomainResultAdmin(admin.ModelAdmin):
    list_display = ("session", "domain", "score", "flagged")
    list_filter = ("domain", "flagged")
    search_fields = ("session__student__username",)


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = ("student", "referred", "updated_by", "updated_at")
    list_filter = ("referred",)
    search_fields = ("student__username", "student__email")