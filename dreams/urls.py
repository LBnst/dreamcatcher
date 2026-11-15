"""Routes des rêves (préfixe ``/reves/``)."""

from django.urls import path

from . import views

urlpatterns = [
    path("nouveau/", views.nouveau_reve, name="nouveau_reve"),
    path("<int:pk>/", views.detail_reve, name="detail_reve"),
]
