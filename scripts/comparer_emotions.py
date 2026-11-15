"""Compare plusieurs réglages de classification émotionnelle sur les rêves annotés.

Script d'expérimentation, non utilisé par l'application : il télécharge les modèles
nécessaires, puis affiche la précision de chaque réglage.

Usage :
    python scripts/comparer_emotions.py
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django  # noqa: E402

django.setup()

from transformers import pipeline  # noqa: E402

from dreams.management.commands.evaluer_emotions import REVES_ANNOTES  # noqa: E402

MINILM = "MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli"
MDEBERTA = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"

EMOTION_BASE = {
    "joy": "heureux",
    "sadness": "triste",
    "stress": "stressant",
    "fear": "effrayant",
    "neutral": "neutre",
}
EMOTION_COLERE = {**EMOTION_BASE, "anger": "colere"}
GABARIT = "The emotion in this text is {}."

REGLAGES = [
    {
        "nom": "1. mDeBERTa avec colère",
        "modele": MDEBERTA,
        "gabarit": GABARIT,
        "libelles": EMOTION_COLERE,
    },
    {
        "nom": "2. MiniLM avec colère",
        "modele": MINILM,
        "gabarit": GABARIT,
        "libelles": EMOTION_COLERE,
    },
]


def evaluer(classifieur, reglage):
    """Classe chaque rêve annoté avec un réglage donné.

    Args:
        classifieur: Pipeline zero-shot de Hugging Face.
        reglage: Dictionnaire décrivant le gabarit, les libellés et les options.

    Returns:
        tuple[int, list[str]]: Nombre de bonnes réponses et émotions prédites.
    """
    libelles = reglage["libelles"]
    seuil = reglage.get("seuil_neutre")
    predictions = []
    for texte, _ in REVES_ANNOTES:
        resultat = classifieur(
            texte,
            candidate_labels=list(libelles),
            hypothesis_template=reglage["gabarit"],
            multi_label=reglage.get("multi_label", False),
        )
        libelle, score = resultat["labels"][0], resultat["scores"][0]
        predictions.append("neutre" if seuil and score < seuil else libelles[libelle])
    corrects = sum(
        predite == attendue for predite, (_, attendue) in zip(predictions, REVES_ANNOTES)
    )
    return corrects, predictions


def main():
    """Évalue chaque réglage et affiche un tableau récapitulatif."""
    classifieurs = {}
    print(f"{'':6} {'Attendu':<36} {' '.join(a[:4] for _, a in REVES_ANNOTES)}")
    for reglage in REGLAGES:
        modele = reglage["modele"]
        if modele not in classifieurs:
            classifieurs[modele] = pipeline("zero-shot-classification", model=modele, device="cpu")
        corrects, predictions = evaluer(classifieurs[modele], reglage)
        print(f"{corrects:>2}/12  {reglage['nom']:<36} {' '.join(p[:4] for p in predictions)}")


if __name__ == "__main__":
    main()
