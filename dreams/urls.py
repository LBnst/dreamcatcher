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
]
