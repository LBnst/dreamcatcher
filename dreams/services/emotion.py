"""Classification émotionnelle d'un récit de rêve, exécutée localement.

Le modèle zero-shot multilingue tourne sur le serveur : aucun récit n'est envoyé
à un service externe, sans coût ni quota.
"""

import logging
import time
from functools import lru_cache

from dreams.models import Reve

logger = logging.getLogger(__name__)

MODELE = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"
# Réglage choisi après comparaison de 13 variantes sur des rêves annotés
# (voir scripts/comparer_emotions.py). Hypothèse et libellés en anglais : plus
# fiables, même pour un texte en français (« English Prompts are Better for
# NLI-based Zero-Shot Emotion Classification », 2024).
GABARIT_HYPOTHESE = "The emotion in this text is {}."
LIBELLES = {
    "joy": Reve.Emotion.HEUREUX,
    "sadness": Reve.Emotion.TRISTE,
    "stress": Reve.Emotion.STRESSANT,
    "fear": Reve.Emotion.EFFRAYANT,
    "neutral": Reve.Emotion.NEUTRE,
    "anger": Reve.Emotion.COLERE,
}


class ErreurClassification(Exception):
    """Le modèle de classification n'a pas pu être chargé ou exécuté."""


@lru_cache(maxsize=1)
def _classifieur():
    """Charge le modèle une seule fois, puis le garde en mémoire.

    Returns:
        Pipeline: Le pipeline de classification zero-shot de Hugging Face.
    """
    # Import tardif : transformers et torch sont lents à charger, inutile de le faire
    # au démarrage de Django ni pendant les tests.
    from transformers import pipeline

    return pipeline("zero-shot-classification", model=MODELE, device="cpu")


def classer_emotion(texte):
    """Détermine l'émotion dominante d'un récit de rêve.

    Args:
        texte: Transcription du rêve.

    Returns:
        tuple[str, float]: L'émotion (valeur de ``Reve.Emotion``) et la confiance
        du modèle, entre 0 et 1.

    Raises:
        ErreurClassification: Si le modèle ne peut pas être chargé ou exécuté.
    """
    if not texte.strip():
        return Reve.Emotion.NEUTRE, 0.0

    debut = time.monotonic()
    try:
        resultat = _classifieur()(
            texte, candidate_labels=list(LIBELLES), hypothesis_template=GABARIT_HYPOTHESE
        )
    except Exception as erreur:
        logger.exception("Classification émotionnelle impossible.")
        raise ErreurClassification("Classification émotionnelle impossible.") from erreur

    libelle, score = resultat["labels"][0], resultat["scores"][0]
    logger.info("Émotion classée en %s ms", round((time.monotonic() - debut) * 1000))
    return LIBELLES[libelle], round(float(score), 4)
