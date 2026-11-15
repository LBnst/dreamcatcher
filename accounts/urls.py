"""Routes de l'authentification (préfixe ``/comptes/``)."""

from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path("inscription/", views.inscription, name="inscription"),
    path("connexion/", views.ConnexionView.as_view(), name="connexion"),
    path("deconnexion/", LogoutView.as_view(), name="deconnexion"),
    path("consentement/", views.consentement, name="consentement"),
    path("supprimer/", views.supprimer_compte, name="supprimer_compte"),
]
