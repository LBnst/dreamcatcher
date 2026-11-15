"""Vues générales du site : supervision et pages publiques."""

from django.contrib.auth.decorators import login_not_required
from django.http import JsonResponse


@login_not_required
def health(request):
    """Indique à l'hébergeur que le service répond.

    Args:
        request: Requête HTTP reçue.

    Returns:
        JsonResponse: ``{"status": "ok"}`` avec le code 200.
    """
    return JsonResponse({"status": "ok"})
