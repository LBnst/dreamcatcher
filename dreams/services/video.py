"""Génération vidéo d'un rêve avec Gemini Omni 1.2 Flash (Google).

La génération dure jusqu'à quelques minutes : elle est lancée en arrière-plan chez
Google (``background: true``) et son identifiant est conservé dans
``Reve.id_tache_externe``. La page du rêve en demande ensuite l'avancement toutes
les 5 secondes : ce suivi reprend même après un redémarrage du serveur.
"""

import base64
import logging
import time
from datetime import timedelta
from decimal import Decimal

import httpx
from django.conf import settings
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from dreams.models import AppelApi, Reve
from dreams.services.appels_api import ErreurApi, en_euros, enregistrer_appel, requete
from dreams.services.image import ErreurGeneration
from dreams.services.quotas import verifier_budget

logger = logging.getLogger(__name__)

URL_INTERACTIONS = "https://generativelanguage.googleapis.com/v1beta/interactions"
URL_FICHIERS = "https://generativelanguage.googleapis.com/v1beta/files"
TIMEOUT_SECONDES = 30
STATUTS_ECHEC = {"failed", "cancelled", "incomplete"}

MESSAGE_INDISPONIBLE = (
    "La génération de la vidéo a échoué. Votre récit est conservé : "
    "réessayez plus tard, ou choisissez une image."
)
MESSAGE_CREDITS = (
    "Le service vidéo est momentanément indisponible (quota atteint). Votre récit est conservé."
)
MESSAGE_DELAI = (
    "La vidéo n'a pas pu être générée dans le délai prévu. Votre récit est conservé : réessayez."
)


def lancer_video(reve, prompt):
    """Lance la génération chez Google et conserve son identifiant.

    Le rêve n'est pas sauvegardé ici : c'est le pipeline qui s'en charge.

    Args:
        reve: Rêve à mettre en vidéo.
        prompt: Description visuelle anonymisée (jamais la transcription brute).

    Raises:
        ErreurGeneration: Si Google refuse ou ne répond pas.
        BudgetEpuise: Si le budget mensuel est atteint (aucun appel n'est fait).
    """
    if not settings.GEMINI_API_KEY:
        raise ErreurGeneration(MESSAGE_INDISPONIBLE, "GEMINI_API_KEY absente")
    verifier_budget()

    try:
        reponse, debut = requete(
            "POST",
            URL_INTERACTIONS,
            reve=reve,
            service=AppelApi.Service.VIDEO,
            timeout=TIMEOUT_SECONDES,
            headers=_entetes(),
            json={
                "model": settings.GEMINI_MODELE_VIDEO,
                "input": prompt,
                "background": True,
                "response_format": {
                    "type": "video",
                    "resolution": settings.RESOLUTION_VIDEO,
                    "duration": f"{settings.DUREE_VIDEO_SECONDES}s",
                    "aspect_ratio": "16:9",
                },
            },
        )
    except ErreurApi as erreur:
        message = MESSAGE_CREDITS if erreur.quota else MESSAGE_INDISPONIBLE
        raise ErreurGeneration(message, str(erreur)) from erreur

    try:
        identifiant = reponse.json().get("id")
    except ValueError:
        identifiant = None
    if not identifiant:
        enregistrer_appel(
            reve,
            AppelApi.Service.VIDEO,
            AppelApi.Statut.ERREUR,
            debut,
            message="Identifiant absent de la réponse",
        )
        raise ErreurGeneration(MESSAGE_INDISPONIBLE, "Identifiant absent de la réponse")

    # Demande acceptée par Google : son coût est compté dès maintenant.
    enregistrer_appel(reve, AppelApi.Service.VIDEO, AppelApi.Statut.SUCCES, debut, cout=_cout_eur())
    reve.id_tache_externe = identifiant
    reve.generation_lancee_le = timezone.now()


def suivre_video(reve_id):
    """Demande à Google l'avancement d'une vidéo en cours et met le rêve à jour.

    Appelée à chaque interrogation de la page du rêve ; ne lève jamais d'exception.
    Le verrou ``select_for_update`` empêche deux onglets ouverts de traiter
    la même vidéo en même temps.

    Args:
        reve_id: Identifiant du rêve.

    Returns:
        Reve: Le rêve à jour.
    """
    with transaction.atomic():
        reve = Reve.objects.select_for_update().get(pk=reve_id)
        if reve.statut != Reve.Statut.EN_COURS or not reve.id_tache_externe:
            return reve  # déjà traité, par exemple depuis un autre onglet
        try:
            _avancer(reve)
        except ErreurGeneration as erreur:
            _echouer(reve, str(erreur), erreur.detail)
        except Exception:
            logger.exception("Erreur inattendue pendant le suivi vidéo du rêve %s.", reve.pk)
            _echouer(reve, MESSAGE_INDISPONIBLE, "Erreur inattendue")
        return reve


def _avancer(reve):
    """Interroge Google une fois et applique le résultat au rêve.

    Args:
        reve: Rêve dont la vidéo est en cours de génération.

    Raises:
        ErreurGeneration: Si Google signale un échec ou si le délai est dépassé.
    """
    try:
        reponse = httpx.request(
            "GET",
            f"{URL_INTERACTIONS}/{reve.id_tache_externe}",
            headers=_entetes(),
            timeout=TIMEOUT_SECONDES,
        )
        reponse.raise_for_status()
        interaction = reponse.json()
    except (httpx.HTTPError, ValueError) as erreur:
        logger.warning("Suivi vidéo du rêve %s : %s", reve.pk, type(erreur).__name__)
        _verifier_delai(reve)
        return  # incident passager : nouvelle tentative au prochain passage

    statut = interaction.get("status")
    if statut in STATUTS_ECHEC:
        raise ErreurGeneration(MESSAGE_INDISPONIBLE, f"Statut : {statut}")
    if statut != "completed":
        _verifier_delai(reve)
        return

    contenu = _extraire_video(interaction)
    if contenu is None:  # fichier hébergé pas encore disponible
        _verifier_delai(reve)
        return
    reve.media.save(f"reve-{reve.pk}.mp4", ContentFile(contenu), save=False)
    reve.statut = Reve.Statut.TERMINE
    reve.message_erreur = ""
    reve.save()
    logger.info("Vidéo du rêve %s prête en %s s.", reve.pk, round(_secondes_ecoulees(reve)))


def _extraire_video(interaction):
    """Récupère les octets de la vidéo, en base64 dans la réponse ou hébergée chez Google.

    Args:
        interaction: Réponse JSON de l'API, au statut « completed ».

    Returns:
        bytes | None: La vidéo, ou ``None`` si le fichier hébergé n'est pas encore prêt.

    Raises:
        ErreurGeneration: Si la réponse ne contient aucune vidéo.
    """
    bloc = _trouver_bloc_video(interaction)
    if bloc is None:
        raise ErreurGeneration(MESSAGE_INDISPONIBLE, "Vidéo absente de la réponse")
    if bloc.get("data"):
        return base64.b64decode(bloc["data"])
    return _telecharger_fichier(bloc["uri"])


def _trouver_bloc_video(element):
    """Cherche, à n'importe quelle profondeur, le bloc vidéo qui porte un contenu.

    Args:
        element: Fragment de la réponse JSON (dictionnaire, liste ou valeur).

    Returns:
        dict | None: Le bloc ``{"type": "video", "data" ou "uri": ...}``, s'il existe.
    """
    if isinstance(element, dict):
        if element.get("type") == "video" and (element.get("data") or element.get("uri")):
            return element
        enfants = element.values()
    elif isinstance(element, list):
        enfants = element
    else:
        return None
    for enfant in enfants:
        bloc = _trouver_bloc_video(enfant)
        if bloc is not None:
            return bloc
    return None


def _telecharger_fichier(uri):
    """Télécharge une vidéo hébergée par l'API Files de Google.

    Args:
        uri: Adresse du fichier renvoyée par Google.

    Returns:
        bytes | None: La vidéo, ou ``None`` si elle n'est pas encore disponible.
    """
    identifiant = uri.rstrip("/").split("/")[-1]
    try:
        reponse = httpx.request(
            "GET",
            f"{URL_FICHIERS}/{identifiant}:download",
            params={"alt": "media"},
            headers=_entetes(),
            timeout=60,
            follow_redirects=True,
        )
        reponse.raise_for_status()
    except httpx.HTTPError:
        return None
    return reponse.content


def _verifier_delai(reve):
    """Abandonne la génération si elle dépasse ``DUREE_MAX_VIDEO``.

    Args:
        reve: Rêve dont la vidéo est en cours.

    Raises:
        ErreurGeneration: Si le délai maximal est dépassé.
    """
    if _secondes_ecoulees(reve) > settings.DUREE_MAX_VIDEO:
        raise ErreurGeneration(MESSAGE_DELAI, f"Vidéo non prête en {settings.DUREE_MAX_VIDEO} s")


def _echouer(reve, message, detail):
    """Trace l'échec et passe le rêve en erreur, prêt pour une nouvelle tentative.

    Args:
        reve: Rêve concerné.
        message: Message destiné à l'utilisateur.
        detail: Détail technique, sans donnée personnelle.
    """
    debut = time.monotonic() - _secondes_ecoulees(reve)  # latence = durée totale
    enregistrer_appel(reve, AppelApi.Service.VIDEO, AppelApi.Statut.ERREUR, debut, message=detail)
    reve.statut = Reve.Statut.ERREUR
    reve.message_erreur = message[:255]
    reve.id_tache_externe = ""  # une nouvelle tentative relancera la génération
    reve.generation_lancee_le = None
    reve.save()


def _secondes_ecoulees(reve):
    """Durée écoulée depuis le lancement de la génération, en secondes."""
    if reve.generation_lancee_le is None:
        return 0.0
    return (timezone.now() - reve.generation_lancee_le) / timedelta(seconds=1)


def _cout_eur():
    """Coût d'une vidéo : durée demandée multipliée par le prix à la seconde."""
    prix = Decimal(str(settings.PRIX_VIDEO_USD_SECONDE)) * settings.DUREE_VIDEO_SECONDES
    return en_euros(prix)


def _entetes():
    """En-têtes d'authentification de l'API Gemini."""
    return {"x-goog-api-key": settings.GEMINI_API_KEY}
