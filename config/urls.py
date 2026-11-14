from django.contrib import admin
from django.http import JsonResponse
from django.urls import path


def health(request):
    """Indique à l'hébergeur que le service répond.

    Args:
        request: Requête HTTP reçue.

    Returns:
        JsonResponse: ``{"status": "ok"}`` avec le code 200.
    """
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("admin/", admin.site.urls),
    path("health", health, name="health"),
]
