"""Réécriture d'un récit de rêve en description visuelle anonymisée (Mistral AI).

Seule cette description est envoyée aux générateurs d'image et de vidéo : la
transcription brute, qui peut contenir des noms, ne quitte jamais ce service
(engagement RGPD de minimisation). Si la réécriture échoue, une description
générique, construite à partir de la seule émotion, la remplace.
"""

import logging
from decimal import Decimal

from django.conf import settings

from dreams.models import AppelApi
from dreams.services.appels_api import ErreurApi, en_euros, enregistrer_appel, requete
from dreams.services.quotas import verifier_budget

logger = logging.getLogger(__name__)

URL_CHAT = "https://api.mistral.ai/v1/chat/completions"
TIMEOUT_SECONDES = 20

CONSIGNE = (
    "You turn a dream narrative into a short visual scene for an image generator. "
    "Write in English, 40 to 80 words, describing only what can be seen: setting, "
    "generic figures, colors, lighting and atmosphere, in a dreamlike, surreal style. "
    "Never include names, ages, addresses, workplaces or any detail that could "
    "identify a real person: replace people with generic descriptions such as "
    "'a woman' or 'an old man'. Answer with the description only."
)

SCENES_GENERIQUES = {
    "heureux": "A luminous dreamscape of floating gardens under a warm golden sky.",
    "triste": "A misty, rain-soaked dreamscape with a lone silhouette on an empty pier.",
    "stressant": "A dreamlike maze of endless corridors and ticking clocks, tense lighting.",
    "effrayant": "A dark, surreal forest at night with looming shadows and pale moonlight.",
    "colere": "A stormy dreamscape of red skies, cracked ground and swirling winds.",
    "neutre": "A calm, surreal dreamscape of soft clouds drifting over a quiet landscape.",
}


def ecrire_prompt_visuel(reve):
    """Réécrit la transcription en une courte scène visuelle, sans aucun nom.

    Args:
        reve: Rêve transcrit (et si possible classé).

    Returns:
        str: Description en anglais, à envoyer au générateur d'image ou de vidéo.

    Raises:
        BudgetEpuise: Si le budget mensuel est atteint.
    """
    if not settings.MISTRAL_API_KEY:
        return _scene_generique(reve)
    verifier_budget()

    emotion = reve.get_emotion_display() or "unknown"
    recit = f"Dominant emotion: {emotion}\nDream: {reve.transcription}"
    try:
        reponse, debut = requete(
            "POST",
            URL_CHAT,
            reve=reve,
            service=AppelApi.Service.PROMPT,
            timeout=TIMEOUT_SECONDES,
            headers={"Authorization": f"Bearer {settings.MISTRAL_API_KEY}"},
            json={
                "model": settings.MISTRAL_MODELE_PROMPT,
                "messages": [
                    {"role": "system", "content": CONSIGNE},
                    {"role": "user", "content": recit},
                ],
                "max_tokens": 300,
                "temperature": 0.7,
            },
        )
    except ErreurApi:
        return _scene_generique(reve)

    donnees = reponse.json()
    cout = _cout_eur(donnees.get("usage") or {})
    enregistrer_appel(reve, AppelApi.Service.PROMPT, AppelApi.Statut.SUCCES, debut, cout=cout)
    return _extraire_texte(donnees) or _scene_generique(reve)


def _extraire_texte(donnees):
    """Extrait le texte de la réponse, qu'il soit une chaîne ou une liste de blocs.

    Args:
        donnees: Réponse JSON de l'API de chat.

    Returns:
        str: Le texte généré, ou une chaîne vide s'il est introuvable.
    """
    try:
        contenu = donnees["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return ""
    if isinstance(contenu, list):  # certains modèles renvoient réflexion + texte en blocs
        contenu = " ".join(bloc.get("text", "") for bloc in contenu if bloc.get("type") == "text")
    return (contenu or "").strip()


def _cout_eur(usage):
    """Calcule le coût de la réécriture à partir des jetons consommés.

    Args:
        usage: Bloc ``usage`` de la réponse (``prompt_tokens``, ``completion_tokens``).

    Returns:
        Decimal: Coût en euros, arrondi à 4 décimales.
    """
    prix_entree = Decimal(str(settings.PRIX_PROMPT_USD_MILLION_ENTREE))
    prix_sortie = Decimal(str(settings.PRIX_PROMPT_USD_MILLION_SORTIE))
    total_usd = (
        Decimal(usage.get("prompt_tokens") or 0) * prix_entree
        + Decimal(usage.get("completion_tokens") or 0) * prix_sortie
    ) / 1_000_000
    return en_euros(total_usd)


def _scene_generique(reve):
    """Renvoie une scène générique liée à l'émotion, sans rien du récit.

    Args:
        reve: Rêve concerné.

    Returns:
        str: Description générique en anglais.
    """
    logger.warning("Rêve %s : description générique utilisée.", reve.pk)
    return SCENES_GENERIQUES.get(reve.emotion, SCENES_GENERIQUES["neutre"])
