import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("nom_url", ["accueil", "confidentialite", "connexion", "inscription"])
def test_pages_publiques_accessibles_sans_connexion(client, nom_url):
    assert client.get(reverse(nom_url)).status_code == 200


def test_accueil_anonyme_propose_de_creer_un_compte(client):
    contenu = client.get(reverse("accueil")).content.decode()

    assert reverse("inscription") in contenu


def test_accueil_demande_le_consentement_si_absent(client):
    utilisateur = get_user_model().objects.create_user(email="nom@exemple.fr", password="x")
    client.force_login(utilisateur)

    contenu = client.get(reverse("accueil")).content.decode()

    assert "Donner mon consentement" in contenu
