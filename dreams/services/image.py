"""Génération de l'illustration d'un rêve avec FLUX 3 Image Klein (Black Forest Labs).

L'API est asynchrone : on soumet la demande, on interroge l'adresse de suivi
jusqu'à ce que l'image soit prête, puis on la télécharge aussitôt (son lien expire).
"""

import time

import httpx
from django.conf import settings
from django.core.files.base import ContentFile

from dreams.models import AppelApi
from dreams.services.appels_api import ErreurApi, en_euros, enregistrer_appel, requete
from dreams.services.quotas import verifier_budget

URL_BFL = "https://api.bfl.ai/v1"
TIMEOUT_SECONDES = 30
DUREE_MAX_GENERATION = 60  # secondes : exigence « timeout de 60 s » pour l'image
PAUSE_SUIVI = 1  # secondes entre deux interrogations
STATUTS_ECHEC = {"Error", "Failed", "Task not found"}

MESSAGE_INDISPONIBLE = (
    "La génération de l'image a échoué. Votre récit est conservé : réessayez dans quelques minutes."
)
MESSAGE_CREDITS = (
    "Le service d'illustration est momentanément indisponible (crédits épuisés). "
    "Votre récit est conservé."
)
MESSAGE_MODERATION = "Le générateur d'images a refusé ce contenu. Votre récit est conservé."


class ErreurGeneration(Exception):
    """Échec de la génération d'un visuel ; le message peut être affiché à l'utilisateur.

    Attributes:
        detail: Détail technique, enregistré dans ``AppelApi`` (sans donnée personnelle).
    """

    def __init__(self, message, detail=""):
        """Initialise l'erreur.

        Args:
            message: Message destiné à l'utilisateur.
            detail: Détail technique de l'échec.
        """
        super().__init__(message)
        self.detail = detail


def generer_image(reve, prompt):
    """Génère l'illustration d'un rêve et l'attache à son champ ``media``.

    Le rêve n'est pas sauvegardé ici : c'est le pipeline qui s'en charge.

    Args:
        reve: Rêve à illustrer.
        prompt: Description visuelle anonymisée (jamais la transcription brute).

    Raises:
        ErreurGeneration: Si la génération échoue, est refusée ou dépasse le délai.
        BudgetEpuise: Si le budget mensuel est atteint (aucun appel n'est fait).
    """
    if not settings.BFL_API_KEY:
        raise ErreurGeneration(MESSAGE_INDISPONIBLE, "BFL_API_KEY absente")
    verifier_budget()
    entetes = {"x-key": settings.BFL_API_KEY}

    try:
        soumission, debut = requete(
            "POST",
            f"{URL_BFL}/{settings.BFL_MODELE_IMAGE}",
            reve=reve,
            service=AppelApi.Service.IMAGE,
            timeout=TIMEOUT_SECONDES,
            headers=entetes,
            json={"prompt": prompt, "aspect_ratio": "16:9", "output_format": "jpeg"},
        )
    except ErreurApi as erreur:
        message = MESSAGE_CREDITS if erreur.quota else MESSAGE_INDISPONIBLE
        raise ErreurGeneration(message, str(erreur)) from erreur

    # La demande a été acceptée : on la considère facturée, même si la suite échoue.
    cout = en_euros(settings.PRIX_IMAGE_USD)
    try:
        url_image = _attendre_image(soumission.json()["polling_url"], entetes)
        fichier = httpx.request("GET", url_image, timeout=TIMEOUT_SECONDES)
        fichier.raise_for_status()
    except (ErreurGeneration, httpx.HTTPError, KeyError, ValueError) as erreur:
        if isinstance(erreur, ErreurGeneration):
            detail = erreur.detail
        else:
            detail = type(erreur).__name__
        enregistrer_appel(
            reve, AppelApi.Service.IMAGE, AppelApi.Statut.ERREUR, debut, cout=cout, message=detail
        )
        if isinstance(erreur, ErreurGeneration):
            raise
        raise ErreurGeneration(MESSAGE_INDISPONIBLE, detail) from erreur

    enregistrer_appel(reve, AppelApi.Service.IMAGE, AppelApi.Statut.SUCCES, debut, cout=cout)
    reve.media.save(f"reve-{reve.pk}.jpg", ContentFile(fichier.content), save=False)


def _attendre_image(url_suivi, entetes):
    """Interroge l'adresse de suivi jusqu'à ce que l'image soit prête.

    Args:
        url_suivi: Adresse ``polling_url`` renvoyée à la soumission.
        entetes: En-têtes d'authentification.

    Returns:
        str: Lien signé vers l'image, valable quelques minutes seulement.

    Raises:
        ErreurGeneration: Si le contenu est refusé, si la génération échoue
            ou si elle dépasse ``DUREE_MAX_GENERATION``.
    """
    limite = time.monotonic() + DUREE_MAX_GENERATION
    while time.monotonic() < limite:
        time.sleep(PAUSE_SUIVI)
        try:
            suivi = httpx.request(
                "GET", url_suivi, headers=entetes, timeout=TIMEOUT_SECONDES
            ).json()
        except (httpx.HTTPError, ValueError):
            continue  # incident passager : on réessaie au tour suivant
        statut = suivi.get("status")
        if statut == "Ready":
            return suivi["result"]["sample"]
        if statut and "Moderated" in statut:
            raise ErreurGeneration(MESSAGE_MODERATION, f"Statut : {statut}")
        if statut in STATUTS_ECHEC:
            raise ErreurGeneration(MESSAGE_INDISPONIBLE, f"Statut : {statut}")
    raise ErreurGeneration(MESSAGE_INDISPONIBLE, f"Image non prête en {DUREE_MAX_GENERATION} s")
