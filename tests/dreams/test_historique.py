from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from dreams.models import Reve

pytestmark = pytest.mark.django_db

Utilisateur = get_user_model()


@pytest.fixture
def utilisateur():
    return Utilisateur.objects.create_user(email="nom@exemple.fr", password="x")


@pytest.fixture
def client_connecte(client, utilisateur):
    client.force_login(utilisateur)
    return client


def creer_reve(utilisateur, jours=0, **champs):
    nuit = date(2026, 11, 1) + timedelta(days=jours)
    return Reve.objects.create(utilisateur=utilisateur, date_reve=nuit, **champs)


def afficher(client, page=None):
    parametres = {"page": page} if page else {}
    return client.get(reverse("historique"), parametres)


def test_historique_exige_une_connexion(client):
    assert client.get(reverse("historique")).url.startswith(reverse("connexion"))


def test_historique_accessible_sans_consentement(client_connecte):
    # Droit d'accès : on consulte ses données même après un retrait du consentement.
    assert afficher(client_connecte).status_code == 200


def test_historique_vide_invite_a_raconter_un_reve(client_connecte):
    assert "aucun rêve" in afficher(client_connecte).content.decode()


def test_affiche_uniquement_mes_reves(client_connecte, utilisateur):
    creer_reve(utilisateur, transcription="Mon rêve à moi.")
    autre = Utilisateur.objects.create_user(email="autre@exemple.fr", password="x")
    creer_reve(autre, transcription="Le rêve secret.")

    contenu = afficher(client_connecte).content.decode()

    assert "Mon rêve à moi." in contenu
    assert "Le rêve secret." not in contenu


def test_du_plus_recent_au_plus_ancien(client_connecte, utilisateur):
    ancien = creer_reve(utilisateur, jours=0)
    recent = creer_reve(utilisateur, jours=5)

    page = afficher(client_connecte).context["page"]

    assert list(page.object_list) == [recent, ancien]


def test_pagination_par_dix(client_connecte, utilisateur):
    for jour in range(12):
        creer_reve(utilisateur, jours=jour)

    assert len(afficher(client_connecte).context["page"].object_list) == 10
    assert len(afficher(client_connecte, page=2).context["page"].object_list) == 2


def test_page_invalide_affiche_la_premiere(client_connecte, utilisateur):
    creer_reve(utilisateur)

    assert afficher(client_connecte, page="abc").context["page"].number == 1


def test_extrait_emotion_et_lien_vers_le_reve(client_connecte, utilisateur):
    reve = creer_reve(
        utilisateur,
        transcription="Je volais au-dessus de la mer.",
        emotion=Reve.Emotion.HEUREUX,
        statut=Reve.Statut.TERMINE,
    )

    contenu = afficher(client_connecte).content.decode()

    assert "Je volais au-dessus de la mer." in contenu
    assert "😊" in contenu
    assert reverse("detail_reve", args=[reve.pk]) in contenu


def test_lien_mes_reves_dans_la_navigation(client_connecte):
    contenu = client_connecte.get(reverse("accueil")).content.decode()

    assert reverse("historique") in contenu
