"""Transcription d'un récit audio avec l'API Voxtral de Mistral AI.

L'appel passe directement par l'API HTTP (et non par le SDK ``mistralai``) pour
maîtriser le délai d'attente, les nouvelles tentatives et les codes d'erreur.
Chaque tentative est enregistrée dans ``AppelApi`` (latence, coût, statut).
"""

import logging
import time
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import httpx
from django.conf import settings

from dreams.models import AppelApi

logger = logging.getLogger(__name__)

URL_TRANSCRIPTION = "https://api.mistral.ai/v1/audio/transcriptions"
LANGUE = "fr"
TIMEOUT_SECONDES = 30
NOUVELLES_TENTATIVES = 2
PAUSE_ENTRE_TENTATIVES = 1  # en secondes, doublée à chaque nouvelle tentative
CODES_TEMPORAIRES = {500, 502, 503, 504}

MESSAGE_INDISPONIBLE = (
    "Le service de transcription est momentanément indisponible. "
    "Votre rêve est conservé : réessayez dans quelques minutes."
)
MESSAGE_QUOTA = (
    "Le quota de transcription est atteint. Votre rêve est conservé : réessayez plus tard."
)
MESSAGE_SILENCE = (
    "Aucune parole n'a été détectée dans l'enregistrement. Essayez de parler plus près du micro."
)


class ErreurTranscription(Exception):
    """Échec de la transcription ; le message peut être affiché à l'utilisateur."""


def transcrire(reve):
    """Transcrit le récit audio d'un rêve.

    Args:
        reve: Rêve dont le champ ``audio`` contient le récit.

    Returns:
        str: Le texte transcrit.

    Raises:
        ErreurTranscription: Si l'API est injoignable, refuse la requête,
            signale un quota dépassé ou ne détecte aucune parole.
    """
    if not settings.MISTRAL_API_KEY:
        logger.error("MISTRAL_API_KEY absente : transcription impossible.")
        raise ErreurTranscription(MESSAGE_INDISPONIBLE)

    with reve.audio.open("rb") as fichier:
        contenu = fichier.read()
    nom_fichier = Path(reve.audio.name).name

    for tentative in range(NOUVELLES_TENTATIVES + 1):
        if tentative:
            time.sleep(PAUSE_ENTRE_TENTATIVES * 2 ** (tentative - 1))
        debut = time.monotonic()
        try:
            reponse = httpx.post(
                URL_TRANSCRIPTION,
                headers={"Authorization": f"Bearer {settings.MISTRAL_API_KEY}"},
                data={"model": settings.MISTRAL_MODELE_TRANSCRIPTION, "language": LANGUE},
                files={"file": (nom_fichier, contenu)},
                timeout=TIMEOUT_SECONDES,
            )
        except httpx.TimeoutException:
            _enregistrer_appel(
                reve,
                AppelApi.Statut.TIMEOUT,
                debut,
                message=f"Aucune réponse en {TIMEOUT_SECONDES} s",
            )
            continue
        except httpx.HTTPError as erreur:
            _enregistrer_appel(
                reve,
                AppelApi.Statut.ERREUR,
                debut,
                message=f"Erreur réseau : {type(erreur).__name__}",
            )
            continue

        if reponse.status_code == 200:
            return _traiter_succes(reve, reponse, debut)
        if reponse.status_code == 429:
            _enregistrer_appel(reve, AppelApi.Statut.QUOTA, debut, message="HTTP 429")
            raise ErreurTranscription(MESSAGE_QUOTA)

        _enregistrer_appel(
            reve, AppelApi.Statut.ERREUR, debut, message=f"HTTP {reponse.status_code}"
        )
        if reponse.status_code not in CODES_TEMPORAIRES:
            # Erreur définitive (clé invalide, fichier refusé...) : inutile de réessayer.
            raise ErreurTranscription(MESSAGE_INDISPONIBLE)

    raise ErreurTranscription(MESSAGE_INDISPONIBLE)


def _traiter_succes(reve, reponse, debut):
    """Enregistre un appel réussi et extrait le texte de la réponse.

    Args:
        reve: Rêve concerné.
        reponse: Réponse HTTP 200 de l'API.
        debut: Instant de départ de l'appel (``time.monotonic()``).

    Returns:
        str: Le texte transcrit, sans espaces superflus.

    Raises:
        ErreurTranscription: Si aucune parole n'a été détectée.
    """
    donnees = reponse.json()
    secondes = (donnees.get("usage") or {}).get("prompt_audio_seconds") or 0
    _enregistrer_appel(reve, AppelApi.Statut.SUCCES, debut, cout=_cout_eur(secondes))

    texte = (donnees.get("text") or "").strip()
    if not texte:
        raise ErreurTranscription(MESSAGE_SILENCE)
    return texte


def _cout_eur(secondes):
    """Calcule le coût d'une transcription à partir de la durée de l'audio.

    Args:
        secondes: Durée de l'audio facturée par l'API.

    Returns:
        Decimal: Coût en euros, arrondi à 4 décimales.
    """
    cout = (
        Decimal(str(secondes))
        / 60
        * Decimal(str(settings.PRIX_TRANSCRIPTION_USD_MINUTE))
        * Decimal(str(settings.TAUX_USD_EUR))
    )
    return cout.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


def _enregistrer_appel(reve, statut, debut, cout=Decimal("0"), message=""):
    """Trace une tentative d'appel dans ``AppelApi`` et dans les journaux.

    Args:
        reve: Rêve concerné.
        statut: Résultat de la tentative (``AppelApi.Statut``).
        debut: Instant de départ de l'appel (``time.monotonic()``).
        cout: Coût de l'appel en euros.
        message: Détail technique de l'erreur, sans donnée personnelle.
    """
    latence_ms = round((time.monotonic() - debut) * 1000)
    AppelApi.objects.create(
        reve=reve,
        service=AppelApi.Service.TRANSCRIPTION,
        statut=statut,
        latence_ms=latence_ms,
        cout_eur=cout,
        message_erreur=message[:255],
    )
    journaliser = logger.info if statut == AppelApi.Statut.SUCCES else logger.warning
    journaliser("Transcription %s (rêve %s, %s ms)", statut, reve.pk, latence_ms)
