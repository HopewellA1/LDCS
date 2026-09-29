from django.conf import settings
from django.db import models


class Profile(models.Model):
    """
    Extra information attached to each user account.

    We keep Django's built-in User for logging in, and hang this Profile
    off it to record whether the person is a student or an educator, plus
    a student number for students. One profile is created automatically
    for every user (see account/signals.py).
    """

    class Role(models.TextChoices):
        STUDENT = "student", "Student"
        EDUCATOR = "educator", "Educator"

    class Faculty(models.TextChoices):
        # Broad groupings so the Disability Unit can see where flags cluster.
        # Edit this list to match the institution's real faculties.
        HEALTH = "health", "Health Sciences"
        ENGINEERING = "engineering", "Engineering & Built Environment"
        APPLIED = "applied", "Applied Sciences"
        ARTS = "arts", "Arts & Design"
        ACCOUNTING = "accounting", "Accounting & Informatics"
        MANAGEMENT = "management", "Management Sciences"

    class Year(models.TextChoices):
        # Year of study replaces "age group" — non-sensitive, and more
        # meaningful for early detection (first-years matter most).
        FIRST = "1", "1st year"
        SECOND = "2", "2nd year"
        THIRD = "3", "3rd year"
        FOURTH = "4", "4th year"
        POSTGRAD = "pg", "Postgraduate"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.STUDENT,
    )
    # Only students have a student number; educators can leave it blank.
    student_number = models.CharField(max_length=20, blank=True)
    # Faculty and year of study are optional; blank means "not specified".
    faculty = models.CharField(max_length=20, choices=Faculty.choices, blank=True)
    year_of_study = models.CharField(max_length=2, choices=Year.choices, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.get_username()} ({self.get_role_display()})"

    @property
    def is_student(self):
        return self.role == self.Role.STUDENT

    @property
    def is_educator(self):
        # Superusers count as educators too, so an admin can reach the
        # educator pages straight after `createsuperuser` without any
        # extra setup.
        return self.role == self.Role.EDUCATOR or self.user.is_superuser
