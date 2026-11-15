from decimal import Decimal
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from dreams.models import AppelApi, Reve

pytestmark = pytest.mark.django_db

Utilisateur = get_user_model()
MOT_DE_PASSE = "UnMotDePasseSolide!42"


@pytest.fixture
def utilisateur():
    return Utilisateur.objects.create_user(email="nom@exemple.fr", password=MOT_DE_PASSE)


@pytest.fixture
def client_connecte(client, utilisateur):
    client.force_login(utilisateur)
    return client


def supprimer(client, mot_de_passe=MOT_DE_PASSE):
    return client.post(reverse("supprimer_compte"), {"mot_de_passe": mot_de_passe})


# --- Accès et confirmation -------------------------------------------------


def test_exige_une_connexion(client):
    assert client.get(reverse("supprimer_compte")).url.startswith(reverse("connexion"))


def test_page_de_confirmation(client_connecte):
    contenu = client_connecte.get(reverse("supprimer_compte")).content.decode()

    assert "définitive" in contenu
    assert "nom@exemple.fr" in contenu


def test_lien_dans_le_pied_de_page(client_connecte):
    contenu = client_connecte.get(reverse("accueil")).content.decode()

    assert reverse("supprimer_compte") in contenu


def test_mauvais_mot_de_passe_ne_supprime_rien(client_connecte, utilisateur):
    reponse = supprimer(client_connecte, "faux")

    assert "mot_de_passe" in reponse.context["form"].errors
    assert Utilisateur.objects.filter(pk=utilisateur.pk).exists()


def test_mot_de_passe_obligatoire(client_connecte, utilisateur):
    reponse = client_connecte.post(reverse("supprimer_compte"), {})

    assert "mot_de_passe" in reponse.context["form"].errors
    assert Utilisateur.objects.filter(pk=utilisateur.pk).exists()


# --- Suppression -----------------------------------------------------------


def test_suppression_du_compte_et_des_reves(client_connecte, utilisateur):
    Reve.objects.create(utilisateur=utilisateur, transcription="Mon rêve.")

    reponse = supprimer(client_connecte)

    assert reponse.url == reverse("accueil")
    assert not Utilisateur.objects.filter(pk=utilisateur.pk).exists()
    assert not Reve.objects.exists()


def test_deconnecte_apres_suppression(client_connecte):
    supprimer(client_connecte)

    assert not client_connecte.get(reverse("accueil")).context["user"].is_authenticated


def test_fichiers_effaces_du_disque(
    client_connecte, utilisateur, django_capture_on_commit_callbacks
):
    reve = Reve.objects.create(
        utilisateur=utilisateur,
        audio=SimpleUploadedFile("reve.webm", b"audio"),
        media=SimpleUploadedFile("reve.mp4", b"video"),
    )
    chemins = [Path(reve.audio.path), Path(reve.media.path)]

    with django_capture_on_commit_callbacks(execute=True):
        supprimer(client_connecte)

    assert not any(chemin.exists() for chemin in chemins)


def test_les_autres_comptes_sont_intacts(client_connecte):
    autre = Utilisateur.objects.create_user(email="autre@exemple.fr", password="x")
    Reve.objects.create(utilisateur=autre)

    supprimer(client_connecte)

    assert Reve.objects.filter(utilisateur=autre).count() == 1


def test_traces_de_cout_conservees_sans_lien_personnel(client_connecte, utilisateur):
    reve = Reve.objects.create(utilisateur=utilisateur)
    AppelApi.objects.create(
        reve=reve,
        service=AppelApi.Service.IMAGE,
        statut=AppelApi.Statut.SUCCES,
        cout_eur=Decimal("0.0090"),
    )

    supprimer(client_connecte)

    appel = AppelApi.objects.get()
    assert appel.reve is None  # plus aucun lien vers l'utilisateur
    assert appel.cout_eur == Decimal("0.0090")  # mais le coût reste dans le budget
