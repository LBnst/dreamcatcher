"""Décorateurs de contrôle d'accès liés au RGPD."""

from functools import wraps
from urllib.parse import urlencode

from django.shortcuts import redirect
from django.urls import reverse


def consentement_requis(vue):
    """Réserve une vue aux utilisateurs ayant accepté la politique de confidentialité.

    Un utilisateur sans consentement est redirigé vers l'écran de consentement,
    puis renvoyé vers la page demandée une fois son accord donné.

    Args:
        vue: Vue Django à protéger.

    Returns:
        callable: La vue protégée.
    """

    @wraps(vue)
    def vue_protegee(request, *args, **kwargs):
        if not getattr(request.user, "a_consenti", False):
            parametres = urlencode({"next": request.get_full_path()})
            return redirect(f"{reverse('consentement')}?{parametres}")
        return vue(request, *args, **kwargs)

    return vue_protegee
