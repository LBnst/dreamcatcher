"""Statistiques du tableau de bord : fréquence des rêves et évolution des émotions."""

from datetime import date

from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.utils import formats, timezone

from dreams.models import Reve

NOMBRE_MOIS = 6
# Ordre fixe des émotions dans les graphiques : chaque émotion garde toujours la même
# couleur, et cet ordre a été vérifié pour rester lisible par les personnes daltoniennes.
ORDRE_EMOTIONS = ["triste", "stressant", "neutre", "heureux", "effrayant", "colere"]


def statistiques(utilisateur, aujourdhui=None):
    """Calcule les indicateurs et les séries du tableau de bord d'un utilisateur.

    Args:
        utilisateur: Utilisateur dont on analyse les rêves.
        aujourdhui: Date de référence (par défaut, la date du jour).

    Returns:
        dict: ``total``, ``ce_mois``, ``emotion_dominante``, ``repartition``,
        ``evolution`` (mois et séries par émotion) et ``tableau`` (mêmes données,
        ligne par ligne, pour la vue en tableau).
    """
    aujourdhui = aujourdhui or timezone.localdate()
    reves = Reve.objects.filter(utilisateur=utilisateur)
    mois = _derniers_mois(aujourdhui, NOMBRE_MOIS)
    libelles_mois = [formats.date_format(premier_jour, "F Y") for premier_jour in mois]

    comptes = dict(
        reves.exclude(emotion="").order_by().values_list("emotion").annotate(nombre=Count("id"))
    )
    repartition = [
        {
            "emotion": emotion,
            "libelle": Reve.Emotion(emotion).label,
            "nombre": comptes.get(emotion, 0),
        }
        for emotion in ORDRE_EMOTIONS
    ]

    par_mois = (
        reves.filter(date_reve__gte=mois[0])
        .exclude(emotion="")
        .annotate(mois=TruncMonth("date_reve"))
        .order_by()
        .values("mois", "emotion")
        .annotate(nombre=Count("id"))
    )
    grille = {(ligne["mois"], ligne["emotion"]): ligne["nombre"] for ligne in par_mois}

    evolution = {
        "mois": libelles_mois,
        "series": [
            {
                "emotion": emotion,
                "libelle": Reve.Emotion(emotion).label,
                "valeurs": [grille.get((premier_jour, emotion), 0) for premier_jour in mois],
            }
            for emotion in ORDRE_EMOTIONS
        ],
    }
    tableau = [
        {
            "mois": libelle,
            "valeurs": [grille.get((premier_jour, emotion), 0) for emotion in ORDRE_EMOTIONS],
        }
        for premier_jour, libelle in zip(mois, libelles_mois)
    ]

    dominante = max(repartition, key=lambda ligne: ligne["nombre"])
    return {
        "total": reves.count(),
        "ce_mois": reves.filter(date_reve__gte=aujourdhui.replace(day=1)).count(),
        "emotion_dominante": dominante if dominante["nombre"] else None,
        "repartition": repartition,
        "evolution": evolution,
        "tableau": tableau,
    }


def _derniers_mois(aujourdhui, nombre):
    """Premiers jours des derniers mois, du plus ancien au plus récent.

    Args:
        aujourdhui: Date de référence (son mois est le dernier de la liste).
        nombre: Nombre de mois.

    Returns:
        list[date]: Le 1er de chaque mois.
    """
    annee, mois = aujourdhui.year, aujourdhui.month
    premiers_jours = []
    for _ in range(nombre):
        premiers_jours.append(date(annee, mois, 1))
        annee, mois = (annee - 1, 12) if mois == 1 else (annee, mois - 1)
    return premiers_jours[::-1]
