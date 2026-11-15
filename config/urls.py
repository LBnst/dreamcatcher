"""Routes principales du projet Dreamcatcher."""

from django.contrib import admin
from django.contrib.auth.decorators import login_not_required
from django.http import JsonResponse
from django.urls import include, path
from django.views.generic import TemplateView


@login_not_required
def health(request):
    """Indique à l'hébergeur que le service répond.

    Args:
        request: Requête HTTP reçue.

    Returns:
        JsonResponse: ``{"status": "ok"}`` avec le code 200.
    """
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("", TemplateView.as_view(template_name="accueil.html"), name="accueil"),
    path("comptes/", include("accounts.urls")),
    path("admin/", admin.site.urls),
    path("health", health, name="health"),
]
