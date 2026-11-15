from decimal import Decimal
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from dreams.models import AppelApi, Reve

pytestmark = pytest.mark.django_db

Utilisateur = get_user_model()


@pytest.fixture
def utilisateur():
    return Utilisateur.objects.create_user(email="nom@exemple.fr", password="x")


@pytest.fixture
def client_connecte(client, utilisateur):
    client.force_login(utilisateur)
    return client


@pytest.fixture
def reve(utilisateur):
    return Reve.objects.create(
        utilisateur=utilisateur,
        transcription="Je volais.",
        media=SimpleUploadedFile("reve.jpg", b"image"),
    )


def supprimer(client, reve):
    return client.post(reverse("supprimer_reve", args=[reve.pk]))


def test_supprimer_son_reve(client_connecte, reve):
    reponse = supprimer(client_connecte, reve)

    assert reponse.url == reverse("historique")
    assert not Reve.objects.filter(pk=reve.pk).exists()


def test_message_de_confirmation(client_connecte, reve):
    reponse = client_connecte.post(reverse("supprimer_reve", args=[reve.pk]), follow=True)

    assert "Le rêve a été supprimé." in reponse.content.decode()


def test_fichier_efface_du_disque(client_connecte, reve, django_capture_on_commit_callbacks):
    chemin = Path(reve.media.path)

    with django_capture_on_commit_callbacks(execute=True):
        supprimer(client_connecte, reve)

    assert not chemin.exists()


def test_impossible_de_supprimer_le_reve_d_un_autre(client_connecte):
    autre = Utilisateur.objects.create_user(email="autre@exemple.fr", password="x")
    reve_d_un_autre = Reve.objects.create(utilisateur=autre)

    reponse = supprimer(client_connecte, reve_d_un_autre)

    assert reponse.status_code == 404
    assert Reve.objects.filter(pk=reve_d_un_autre.pk).exists()


def test_refuse_une_requete_get(client_connecte, reve):
    reponse = client_connecte.get(reverse("supprimer_reve", args=[reve.pk]))

    assert reponse.status_code == 405
    assert Reve.objects.filter(pk=reve.pk).exists()


def test_exige_une_connexion(client, reve):
    reponse = supprimer(client, reve)

    assert reponse.url.startswith(reverse("connexion"))
    assert Reve.objects.filter(pk=reve.pk).exists()


def test_le_cout_reste_compte_dans_le_budget(client_connecte, reve):
    AppelApi.objects.create(
        reve=reve,
        service=AppelApi.Service.IMAGE,
        statut=AppelApi.Statut.SUCCES,
        cout_eur=Decimal("0.0090"),
    )

    supprimer(client_connecte, reve)

    appel = AppelApi.objects.get()
    assert appel.reve is None
    assert appel.cout_eur == Decimal("0.0090")


def test_bouton_de_suppression_sur_la_fiche(client_connecte, reve):
    contenu = client_connecte.get(reverse("detail_reve", args=[reve.pk])).content.decode()

    assert reverse("supprimer_reve", args=[reve.pk]) in contenu
