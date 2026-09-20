from django.urls import path

from . import views

urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("consent/", views.consent, name="consent"),
    path("consent/withdraw/", views.withdraw_consent, name="withdraw_consent"),
    path("screening/", views.screening_home, name="screening_home"),
]