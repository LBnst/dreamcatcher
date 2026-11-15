import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from dreams.models import Reve

pytestmark = pytest.mark.django_db


@pytest.fixture
def utilisateur():
    return get_user_model().objects.create_user(email="nom@exemple.fr", password="x")


@pytest.fixture
def client_connecte(client, utilisateur):
    client.force_login(utilisateur)
    return client


def test_exige_une_connexion(client):
    assert client.get(reverse("tableau_de_bord")).url.startswith(reverse("connexion"))


def test_etat_vide(client_connecte):
    contenu = client_connecte.get(reverse("tableau_de_bord")).content.decode()

    assert "Aucun rêve pour l'instant" in contenu
    assert "graphique-evolution" not in contenu


def test_graphiques_et_donnees(client_connecte, utilisateur):
    Reve.objects.create(utilisateur=utilisateur, emotion=Reve.Emotion.HEUREUX)

    contenu = client_connecte.get(reverse("tableau_de_bord")).content.decode()

    assert 'id="graphique-evolution"' in contenu
    assert 'id="graphique-repartition"' in contenu
    assert 'id="donnees-tableau-de-bord"' in contenu  # données transmises aux graphiques
    assert "Voir les données sous forme de tableau" in contenu


def test_lien_dans_la_navigation(client_connecte):
    contenu = client_connecte.get(reverse("accueil")).content.decode()

    assert reverse("tableau_de_bord") in contenu
