"""Routes des rêves (préfixe ``/reves/``)."""

from django.urls import path

from . import views

urlpatterns = [
    path("", views.historique, name="historique"),
    path("nouveau/", views.nouveau_reve, name="nouveau_reve"),
    path("<int:pk>/", views.detail_reve, name="detail_reve"),
    path("<int:pk>/statut/", views.statut_reve, name="statut_reve"),
    path("<int:pk>/reessayer/", views.reessayer_reve, name="reessayer_reve"),
    path("<int:pk>/media/", views.media_reve, name="media_reve"),
    path("<int:pk>/supprimer/", views.supprimer_reve, name="supprimer_reve"),
    path("tableau-de-bord/", views.tableau_de_bord, name="tableau_de_bord"),
    path("<int:pk>/corriger/", views.corriger_reve, name="corriger_reve"),
    path("<int:pk>/progression/", views.progression_reve, name="progression_reve"),
    path("<int:pk>/valider/", views.valider_reve, name="valider_reve"),
]
