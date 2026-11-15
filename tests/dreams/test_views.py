from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from dreams import forms as forms_reves
from dreams.models import Reve

pytestmark = pytest.mark.django_db

Utilisateur = get_user_model()


@pytest.fixture
def utilisateur_consentant():
    return Utilisateur.objects.create_user(
        email="nom@exemple.fr", password="x", consentement_le=timezone.now()
    )


@pytest.fixture
def client_consentant(client, utilisateur_consentant):
    client.force_login(utilisateur_consentant)
    return client


def fichier_audio(nom="reve.mp3"):
    return SimpleUploadedFile(nom, b"faux contenu audio", content_type="audio/mpeg")


def envoyer(client, **donnees):
    donnees.setdefault("audio", fichier_audio())
    donnees.setdefault("date_reve", "2026-11-14")
    donnees.setdefault("type_media", "image")
    return client.post(reverse("nouveau_reve"), donnees)


# --- Accès -----------------------------------------------------------------


def test_nouveau_reve_exige_une_connexion(client):
    reponse = client.get(reverse("nouveau_reve"))

    assert reponse.url.startswith(reverse("connexion"))


def test_nouveau_reve_exige_le_consentement(client):
    client.force_login(Utilisateur.objects.create_user(email="sans@exemple.fr", password="x"))

    reponse = client.get(reverse("nouveau_reve"))

    assert reponse.url.startswith(reverse("consentement"))


def test_page_nouveau_reve_affiche_l_enregistreur(client_consentant):
    reponse = client_consentant.get(reverse("nouveau_reve"))

    assert reponse.status_code == 200
    assert "enr-demarrer" in reponse.content.decode()


def test_accueil_propose_de_raconter_un_reve(client_consentant):
    contenu = client_consentant.get(reverse("accueil")).content.decode()

    assert reverse("nouveau_reve") in contenu


# --- Envoi du récit --------------------------------------------------------


def test_envoyer_un_audio_cree_le_reve(client_consentant, utilisateur_consentant):
    reponse = envoyer(client_consentant, type_media="video")

    reve = Reve.objects.get()
    assert reve.utilisateur == utilisateur_consentant
    assert reve.type_media == Reve.TypeMedia.VIDEO
    assert reve.statut == Reve.Statut.EN_COURS
    assert str(reve.date_reve) == "2026-11-14"
    assert reve.audio.name.startswith("audio/")
    assert reponse.url == reverse("detail_reve", args=[reve.pk])


def test_l_enregistrement_du_navigateur_est_accepte(client_consentant):
    envoyer(client_consentant, audio=fichier_audio("enregistrement.webm"))

    assert Reve.objects.count() == 1


def test_refuse_un_format_non_audio(client_consentant):
    reponse = envoyer(client_consentant, audio=fichier_audio("notes.txt"))

    assert "audio" in reponse.context["form"].errors
    assert not Reve.objects.exists()


def test_refuse_un_fichier_trop_lourd(client_consentant, monkeypatch):
    monkeypatch.setattr(forms_reves, "TAILLE_MAX_AUDIO", 5)  # 5 octets pour le test

    reponse = envoyer(client_consentant)

    assert "audio" in reponse.context["form"].errors
    assert not Reve.objects.exists()


def test_refuse_un_envoi_sans_audio(client_consentant):
    reponse = client_consentant.post(
        reverse("nouveau_reve"), {"date_reve": "2026-11-14", "type_media": "image"}
    )

    assert "audio" in reponse.context["form"].errors
    assert not Reve.objects.exists()


def test_refuse_une_date_dans_le_futur(client_consentant):
    demain = timezone.localdate() + timedelta(days=1)

    reponse = envoyer(client_consentant, date_reve=demain.isoformat())

    assert "date_reve" in reponse.context["form"].errors
    assert not Reve.objects.exists()


# --- Consultation ----------------------------------------------------------


def test_detail_visible_par_son_proprietaire(client_consentant, utilisateur_consentant):
    reve = Reve.objects.create(utilisateur=utilisateur_consentant)

    assert client_consentant.get(reverse("detail_reve", args=[reve.pk])).status_code == 200


def test_detail_d_un_autre_utilisateur_renvoie_404(client_consentant):
    autre = Utilisateur.objects.create_user(email="autre@exemple.fr", password="x")
    reve = Reve.objects.create(utilisateur=autre)

    assert client_consentant.get(reverse("detail_reve", args=[reve.pk])).status_code == 404
