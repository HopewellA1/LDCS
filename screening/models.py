from django.conf import settings
from django.db import models
from django.utils import timezone

from .content import DOMAIN_CHOICES, DOMAIN_LOOKUP


class ConsentRecord(models.Model):

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="consent_records",
    )
    version = models.CharField(max_length=20)
    accepted_at = models.DateTimeField(default=timezone.now)
    withdrawn_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-accepted_at"]

    def __str__(self):
        state = "withdrawn" if self.withdrawn_at else "active"
        return f"{self.user} - v{self.version} ({state})"


class ScreeningSession(models.Model):
    """
    One screening attempt by one student.

    A student can screen more than once, so each attempt is its own
    session. The individual domain scores hang off it as DomainResult
    rows (see below).
    """

    # Predicted support-risk levels from the ML model (see screening/ml.py).
    RISK_CHOICES = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
    ]

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="screening_sessions",
    )
    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    # Predicted overall risk ("low"/"medium"/"high"), set by the ML model when
    # the screening completes. Blank when the model has not scored it (e.g. the
    # model has not been trained yet) - screening never depends on this.
    ml_risk = models.CharField(max_length=10, choices=RISK_CHOICES, blank=True)
    # Median time (milliseconds) the student took to answer a question in this
    # screening. Captured as a behavioural signal for the risk model - slower,
    # more hesitant responding can accompany some learning difficulties. Null
    # when timing was not captured (e.g. older sessions).
    median_response_ms = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]

    def __str__(self):
        return f"Screening #{self.pk} for {self.student.get_username()}"

    @property
    def is_complete(self):
        return self.completed_at is not None

    @property
    def flagged_count(self):
        """How many domains in this session were flagged."""
        return self.domain_results.filter(flagged=True).count()


class DomainResult(models.Model):
    """
    The score for a single domain (reading, writing, etc.) within one
    screening session.
    """

    session = models.ForeignKey(
        ScreeningSession,
        on_delete=models.CASCADE,
        related_name="domain_results",
    )
    domain = models.CharField(max_length=20, choices=DOMAIN_CHOICES)
    score = models.PositiveIntegerField()  # percentage, 0–100
    flagged = models.BooleanField(default=False)  # True when below the threshold
    # A short human-readable breakdown of how the score was reached, e.g.
    # [{"label": "Comprehension accuracy", "value": "2/3 (67%)"}]. Stored as
    # JSON because it is only ever shown, never queried.
    detail = models.JSONField(default=list, blank=True)

    class Meta:
        # A session should only have one result per domain.
        unique_together = ("session", "domain")

    def __str__(self):
        return f"{self.session.student.get_username()} · {self.domain}: {self.score}%"

    @property
    def label(self):
        """The friendly domain name, e.g. 'Reading fluency'."""
        info = DOMAIN_LOOKUP.get(self.domain)
        return info["label"] if info else self.domain


class Referral(models.Model):
    """
    The Disability Unit's triage decision for one student: have they been
    referred to the Unit for a full assessment, or not yet?

    There is one record per student (updated in place), plus a note and a
    record of which officer last changed it and when.
    """

    student = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="referral",
    )
    referred = models.BooleanField(default=False)
    note = models.TextField(blank=True)
    # Which officer last set this, and when. updated_by can be blank if the
    # officer's account is later removed.
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="referrals_updated",
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        state = "referred" if self.referred else "not referred"
        return f"{self.student.get_username()} - {state}"


class FollowUpTest(models.Model):
    """
    A targeted practice test a Disability Unit officer creates for one student,
    aimed at a domain the student struggled with in their screening.

    Officers create, view, edit and delete these (the CRUD feature). Each test
    holds a few multiple-choice questions (see FollowUpQuestion). Later the
    student can take the test to work on that specific weakness - closing the
    "fail -> practice -> improve" loop.
    """

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="follow_up_tests",
    )
    # The domain this test targets (usually one the student failed).
    domain = models.CharField(max_length=20, choices=DOMAIN_CHOICES)
    title = models.CharField(max_length=120)
    # Optional short guidance shown to the student with the test.
    note = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="follow_up_tests_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    # Officers can retire a test without deleting it.
    is_active = models.BooleanField(default=True)
    # The student's latest attempt: when they last completed it, their score,
    # and whether they passed (score met the threshold). Passing clears the
    # matching domain flag from their screening.
    completed_at = models.DateTimeField(null=True, blank=True)
    last_score = models.PositiveIntegerField(null=True, blank=True)
    passed = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} for {self.student.get_username()}"

    @property
    def taken(self):
        return self.completed_at is not None

    @property
    def domain_label(self):
        """The friendly domain name, e.g. 'Reading fluency'."""
        info = DOMAIN_LOOKUP.get(self.domain)
        return info["label"] if info else self.domain

    @property
    def question_count(self):
        return self.questions.count()


class FollowUpQuestion(models.Model):
    """One multiple-choice question inside a FollowUpTest."""

    CORRECT_CHOICES = [(0, "A"), (1, "B"), (2, "C"), (3, "D")]

    test = models.ForeignKey(
        FollowUpTest,
        on_delete=models.CASCADE,
        related_name="questions",
    )
    prompt = models.CharField(max_length=300)
    option_a = models.CharField(max_length=200)
    option_b = models.CharField(max_length=200)
    # C and D are optional, so a question can have 2, 3 or 4 options.
    option_c = models.CharField(max_length=200, blank=True)
    option_d = models.CharField(max_length=200, blank=True)
    correct_index = models.PositiveSmallIntegerField(
        choices=CORRECT_CHOICES, default=0,
        help_text="Which option is correct: A, B, C or D.",
    )
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return self.prompt[:60]

    def options_list(self):
        """The non-blank options, in order."""
        options = [self.option_a, self.option_b, self.option_c, self.option_d]
        return [o for o in options if o and o.strip()]

    def display_options(self):
        """
        Return (options, correct_index) for showing the question, dropping any
        blank option slots and re-mapping the correct answer to its position in
        the shortened list. This keeps scoring right even if, say, option C is
        left blank but D is used.
        """
        slots = [self.option_a, self.option_b, self.option_c, self.option_d]
        options, correct = [], 0
        for i, opt in enumerate(slots):
            if opt and opt.strip():
                if i == self.correct_index:
                    correct = len(options)
                options.append(opt)
        return options, correct

    def as_question(self):
        """Shape this question like the screening's questions (for reuse)."""
        options, correct = self.display_options()
        return {"q": self.prompt, "options": options, "answer": correct}
