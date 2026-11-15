"""Traitement complet d'un rêve : transcription, puis classification émotionnelle.

Le traitement tourne dans un fil d'exécution (thread) séparé pour que la page réponde
immédiatement ; la page du rêve interroge ensuite son statut toutes les 5 secondes.
"""

import logging
import threading

from django.conf import settings
from django.db import connection

from dreams.models import Reve
from dreams.services.emotion import ErreurClassification, classer_emotion
from dreams.services.transcription import ErreurTranscription, transcrire

logger = logging.getLogger(__name__)

MESSAGE_INATTENDU = (
    "Une erreur inattendue est survenue. Votre rêve est conservé : réessayez plus tard."
)


def demarrer_traitement(reve):
    """Lance le traitement d'un rêve, en arrière-plan ou immédiatement selon la configuration.

    Args:
        reve: Rêve à traiter.
    """
    if settings.TRAITEMENT_EN_ARRIERE_PLAN:
        threading.Thread(target=_traiter_en_arriere_plan, args=(reve.pk,), daemon=True).start()
    else:
        traiter_reve(reve.pk)


def _traiter_en_arriere_plan(reve_id):
    """Traite le rêve puis ferme la connexion à la base ouverte par ce thread.

    Args:
        reve_id: Identifiant du rêve.
    """
    try:
        traiter_reve(reve_id)
    finally:
        connection.close()


def traiter_reve(reve_id):
    """Transcrit le rêve, supprime l'audio, puis classe son émotion.

    Ne lève jamais d'exception : en cas d'échec, le rêve passe au statut « erreur »
    avec un message clair, et reste conservé pour une nouvelle tentative.

    Args:
        reve_id: Identifiant du rêve.
    """
    reve = Reve.objects.get(pk=reve_id)
    try:
        _executer(reve)
    except ErreurTranscription as erreur:
        _marquer_en_erreur(reve, str(erreur))
    except Exception:
        logger.exception("Erreur inattendue pendant le traitement du rêve %s.", reve_id)
        _marquer_en_erreur(reve, MESSAGE_INATTENDU)


def _executer(reve):
    """Enchaîne les étapes du traitement et enregistre le résultat.

    Args:
        reve: Rêve à traiter.

    Raises:
        ErreurTranscription: Si la transcription échoue (l'audio est alors conservé).
    """
    reve.transcription = transcrire(reve)
    reve.audio.delete(save=False)  # RGPD : l'audio n'est plus utile une fois transcrit

    try:
        reve.emotion, reve.score_emotion = classer_emotion(reve.transcription)
    except ErreurClassification:
        logger.warning("Rêve %s conservé sans émotion.", reve.pk)

    reve.statut = Reve.Statut.TERMINE
    reve.message_erreur = ""
    reve.save()


def _marquer_en_erreur(reve, message):
    """Passe le rêve au statut « erreur » avec un message destiné à l'utilisateur.

    Args:
        reve: Rêve concerné.
        message: Explication affichée sur la page du rêve.
    """
    reve.statut = Reve.Statut.ERREUR
    reve.message_erreur = message[:255]
    reve.save()
