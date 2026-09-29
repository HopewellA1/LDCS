from django.contrib import admin

from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "student_number", "faculty", "year_of_study", "created_at")
    list_filter = ("role", "faculty", "year_of_study")
    search_fields = ("user__username", "user__email", "student_number")
    # `role` is editable here so an admin can promote someone to educator.
