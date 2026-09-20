from django.contrib import admin

from .models import ConsentRecord


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