from django.urls import path

from . import views

urlpatterns = [
    # Consent lifecycle
    path("dashboard/", views.dashboard, name="dashboard"),
    path("consent/", views.consent, name="consent"),
    path("consent/withdraw/", views.withdraw_consent, name="withdraw_consent"),

    # Screening menu + finishing
    path("screening/", views.screening_home, name="screening_home"),
    path("screening/finish/", views.screening_finish, name="screening_finish"),

    # Numeracy & executive-function tests (share one view)
    path("screening/test/<slug:domain>/", views.test_mcq, name="test_mcq"),

    # Reading fluency (timed passage + comprehension)
    path("screening/reading/", views.reading_test, name="reading_test"),
    path("screening/reading/start/", views.reading_start, name="reading_start"),
    path("screening/reading/finish/", views.reading_finish, name="reading_finish"),
    path("screening/reading/answer/", views.reading_answer, name="reading_answer"),

    # Writing & language (grammar + copy-typing)
    path("screening/writing/", views.writing_test, name="writing_test"),
    path("screening/writing/grammar/", views.writing_grammar_answer, name="writing_grammar_answer"),
    path("screening/writing/typing/", views.writing_typing_submit, name="writing_typing_submit"),

    # Working memory (digit-span)
    path("screening/memory/", views.memory_test, name="memory_test"),
    path("screening/memory/answer/", views.memory_answer, name="memory_answer"),

    # Student results
    path("results/", views.results, name="results"),

    # Educator dashboard
    path("educator/", views.educator_dashboard, name="educator_dashboard"),
    path("educator/student/<int:student_id>/", views.educator_student, name="educator_student"),

    # Follow-up practice tests (officer-side CRUD)
    path("educator/follow-ups/", views.followup_list, name="followup_list"),
    path("educator/student/<int:student_id>/follow-ups/new/", views.followup_create, name="followup_create"),
    path("educator/follow-ups/<int:pk>/edit/", views.followup_edit, name="followup_edit"),
    path("educator/follow-ups/<int:pk>/delete/", views.followup_delete, name="followup_delete"),

    # Follow-up practice test: student takes it
    path("practice/<int:pk>/", views.followup_take, name="followup_take"),
]
