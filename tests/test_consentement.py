import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone

from accounts.decorators import consentement_requis

pytestmark = pytest.mark.django_db


@pytest.fixture
def utilisateur():
    return get_user_model().objects.create_user(email="nom@exemple.fr", password="x")


@pytest.fixture
def client_connecte(client, utilisateur):
    client.force_login(utilisateur)
    return client


# --- Écran de consentement -------------------------------------------------


def test_ecran_de_consentement_affiche_les_deux_choix(client_connecte):
    contenu = client_connecte.get(reverse("consentement")).content.decode()

    assert "J'accepte" in contenu
    assert "Je refuse" in contenu


def test_accepter_enregistre_la_date_de_consentement(client_connecte, utilisateur):
    reponse = client_connecte.post(reverse("consentement"), {"action": "accepter"})

    utilisateur.refresh_from_db()
    assert utilisateur.a_consenti
    assert reponse.url == reverse("accueil")


def test_accepter_renvoie_vers_la_page_demandee(client_connecte):
    reponse = client_connecte.post(
        reverse("consentement"), {"action": "accepter", "next": "/confidentialite/"}
    )

    assert reponse.url == "/confidentialite/"


def test_accepter_ignore_une_redirection_vers_un_site_externe(client_connecte):
    reponse = client_connecte.post(
        reverse("consentement"), {"action": "accepter", "next": "https://site-pirate.com/"}
    )

    assert reponse.url == reverse("accueil")


def test_refuser_n_enregistre_aucun_consentement(client_connecte, utilisateur):
    reponse = client_connecte.post(reverse("consentement"), {"action": "refuser"})

    utilisateur.refresh_from_db()
    assert not utilisateur.a_consenti
    assert reponse.url == reverse("accueil")


def test_retirer_son_consentement(client_connecte, utilisateur):
    utilisateur.consentement_le = timezone.now()
    utilisateur.save()

    client_connecte.post(reverse("consentement"), {"action": "retirer"})

    utilisateur.refresh_from_db()
    assert not utilisateur.a_consenti


def test_ecran_affiche_la_date_si_deja_consenti(client_connecte, utilisateur):
    utilisateur.consentement_le = timezone.now()
    utilisateur.save()

    contenu = client_connecte.get(reverse("consentement")).content.decode()

    assert "Retirer mon consentement" in contenu


# --- Décorateur consentement_requis ----------------------------------------


@consentement_requis
def vue_de_test(request):
    return HttpResponse("contenu protégé")


def test_decorateur_redirige_sans_consentement(utilisateur):
    requete = RequestFactory().get("/reves/nouveau/")
    requete.user = utilisateur

    reponse = vue_de_test(requete)

    assert reponse.status_code == 302
    assert reponse.url == f"{reverse('consentement')}?next=%2Freves%2Fnouveau%2F"


def test_decorateur_laisse_passer_avec_consentement(utilisateur):
    utilisateur.consentement_le = timezone.now()
    requete = RequestFactory().get("/reves/nouveau/")
    requete.user = utilisateur

    assert vue_de_test(requete).status_code == 200


def test_decorateur_redirige_un_anonyme():
    requete = RequestFactory().get("/reves/nouveau/")
    requete.user = AnonymousUser()

    assert vue_de_test(requete).status_code == 302
