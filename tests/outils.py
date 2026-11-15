"""Outils de test partagés : simulation des appels HTTP."""

import httpx


class FauxHttp:
    """Remplace httpx.request : renvoie (ou lève) les résultats prévus, dans l'ordre."""

    def __init__(self, *resultats):
        self.resultats = list(resultats)
        self.appels = []

    def __call__(self, methode, url, **options):
        self.appels.append({"methode": methode, "url": url, **options})
        resultat = self.resultats.pop(0)
        if isinstance(resultat, Exception):
            raise resultat
        return resultat


def reponse_http(code=200, json=None, content=None):
    """Fabrique une réponse httpx simulée, en JSON ou en octets bruts."""
    requete = httpx.Request("GET", "https://api.exemple.test")
    if content is not None:
        return httpx.Response(code, content=content, request=requete)
    return httpx.Response(code, json=json or {}, request=requete)
