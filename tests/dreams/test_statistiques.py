from datetime import date

import pytest
from django.contrib.auth import get_user_model

from dreams.models import Reve
from dreams.services.statistiques import ORDRE_EMOTIONS, statistiques

pytestmark = pytest.mark.django_db

AUJOURDHUI = date(2026, 11, 15)
Utilisateur = get_user_model()


@pytest.fixture
def utilisateur():
    return Utilisateur.objects.create_user(email="nom@exemple.fr", password="x")


def creer(utilisateur, nuit, emotion=Reve.Emotion.HEUREUX):
    return Reve.objects.create(utilisateur=utilisateur, date_reve=nuit, emotion=emotion)


def serie(stats, emotion):
    return next(s for s in stats["evolution"]["series"] if s["emotion"] == emotion)


def test_sans_reve(utilisateur):
    stats = statistiques(utilisateur, AUJOURDHUI)

    assert stats["total"] == 0
    assert stats["emotion_dominante"] is None
    assert all(sum(s["valeurs"]) == 0 for s in stats["evolution"]["series"])


def test_les_six_derniers_mois(utilisateur):
    mois = statistiques(utilisateur, AUJOURDHUI)["evolution"]["mois"]

    assert mois == [
        "juin 2026",
        "juillet 2026",
        "août 2026",
        "septembre 2026",
        "octobre 2026",
        "novembre 2026",
    ]


def test_passage_d_une_annee_a_l_autre(utilisateur):
    mois = statistiques(utilisateur, date(2026, 2, 10))["evolution"]["mois"]

    assert mois[0] == "septembre 2025"
    assert mois[-1] == "février 2026"


def test_repartition_et_emotion_dominante(utilisateur):
    creer(utilisateur, date(2026, 11, 1), Reve.Emotion.TRISTE)
    creer(utilisateur, date(2026, 11, 2), Reve.Emotion.TRISTE)
    creer(utilisateur, date(2026, 10, 5), Reve.Emotion.HEUREUX)

    stats = statistiques(utilisateur, AUJOURDHUI)

    nombres = {ligne["emotion"]: ligne["nombre"] for ligne in stats["repartition"]}
    assert nombres["triste"] == 2
    assert nombres["heureux"] == 1
    assert nombres["colere"] == 0
    assert stats["emotion_dominante"]["emotion"] == "triste"


def test_evolution_mois_par_mois(utilisateur):
    creer(utilisateur, date(2026, 11, 3), Reve.Emotion.TRISTE)
    creer(utilisateur, date(2026, 6, 20), Reve.Emotion.TRISTE)
    creer(utilisateur, date(2026, 5, 31), Reve.Emotion.TRISTE)  # mai : hors des six mois

    stats = statistiques(utilisateur, AUJOURDHUI)

    assert serie(stats, "triste")["valeurs"] == [1, 0, 0, 0, 0, 1]
    assert stats["total"] == 3  # le total, lui, compte tous les rêves


def test_compteurs_et_reves_sans_emotion(utilisateur):
    creer(utilisateur, date(2026, 11, 2))
    creer(utilisateur, date(2026, 10, 30))
    Reve.objects.create(utilisateur=utilisateur, date_reve=date(2026, 11, 5))  # sans émotion

    stats = statistiques(utilisateur, AUJOURDHUI)

    assert stats["total"] == 3
    assert stats["ce_mois"] == 2
    assert sum(ligne["nombre"] for ligne in stats["repartition"]) == 2


def test_les_reves_des_autres_sont_ignores(utilisateur):
    autre = Utilisateur.objects.create_user(email="autre@exemple.fr", password="x")
    creer(autre, date(2026, 11, 1))

    assert statistiques(utilisateur, AUJOURDHUI)["total"] == 0


def test_vue_en_tableau(utilisateur):
    creer(utilisateur, date(2026, 11, 3), Reve.Emotion.COLERE)

    ligne = statistiques(utilisateur, AUJOURDHUI)["tableau"][-1]

    assert ligne["mois"] == "novembre 2026"
    assert ligne["valeurs"][ORDRE_EMOTIONS.index("colere")] == 1
