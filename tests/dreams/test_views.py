from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone

from dreams import forms as forms_reves
from dreams import views
from dreams.models import Reve

pytestmark = pytest.mark.django_db

Utilisateur = get_user_model()


@pytest.fixture(autouse=True)
def traitements_lances(monkeypatch):
    """Remplace le lancement du traitement : on vérifie seulement qu'il est demandé."""
    lances = []
    monkeypatch.setattr(views, "demarrer_traitement", lances.append)
    return lances


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


def creer_reve(utilisateur, **champs):
    champs.setdefault("audio", SimpleUploadedFile("reve.webm", b"audio"))
    return Reve.objects.create(utilisateur=utilisateur, **champs)


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


def test_envoyer_un_audio_cree_le_reve(
    client_consentant, utilisateur_consentant, traitements_lances
):
    reponse = envoyer(client_consentant, type_media="video")

    reve = Reve.objects.get()
    assert reve.utilisateur == utilisateur_consentant
    assert reve.type_media == Reve.TypeMedia.VIDEO
    assert reve.statut == Reve.Statut.EN_COURS
    assert str(reve.date_reve) == "2026-11-14"
    assert reve.audio.name.startswith("audio/")
    assert reponse.url == reverse("detail_reve", args=[reve.pk])
    assert traitements_lances == [reve]


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


# --- Garde-fous à l'envoi --------------------------------------------------


def test_refuse_un_reve_si_le_quota_est_atteint(
    client_consentant, utilisateur_consentant, settings, traitements_lances
):
    settings.QUOTA_REVES_PAR_JOUR = 1
    creer_reve(utilisateur_consentant)

    reponse = envoyer(client_consentant)

    assert "limite" in reponse.content.decode()
    assert Reve.objects.count() == 1
    assert traitements_lances == []


def test_refuse_un_reve_si_le_budget_est_atteint(client_consentant, settings):
    settings.BUDGET_MENSUEL_EUR = 0

    reponse = envoyer(client_consentant)

    assert "budget mensuel" in reponse.content.decode()
    assert not Reve.objects.exists()


# --- Consultation ----------------------------------------------------------


def test_detail_visible_par_son_proprietaire(client_consentant, utilisateur_consentant):
    reve = Reve.objects.create(utilisateur=utilisateur_consentant)

    assert client_consentant.get(reverse("detail_reve", args=[reve.pk])).status_code == 200


def test_detail_d_un_autre_utilisateur_renvoie_404(client_consentant):
    autre = Utilisateur.objects.create_user(email="autre@exemple.fr", password="x")
    reve = Reve.objects.create(utilisateur=autre)

    assert client_consentant.get(reverse("detail_reve", args=[reve.pk])).status_code == 404


def test_detail_en_cours_affiche_le_suivi(client_consentant, utilisateur_consentant):
    reve = creer_reve(utilisateur_consentant)

    contenu = client_consentant.get(reverse("detail_reve", args=[reve.pk])).content.decode()

    assert "traitement-en-cours" in contenu


def test_detail_termine_affiche_emotion_et_recit(client_consentant, utilisateur_consentant):
    reve = creer_reve(
        utilisateur_consentant,
        statut=Reve.Statut.TERMINE,
        transcription="Je hurlais sur mon frère.",
        emotion=Reve.Emotion.COLERE,
        score_emotion=0.72,
    )

    contenu = client_consentant.get(reverse("detail_reve", args=[reve.pk])).content.decode()

    assert "Colère" in contenu
    assert "😠" in contenu
    assert "72 %" in contenu
    assert "Je hurlais sur mon frère." in contenu
    assert "traitement-en-cours" not in contenu


def test_detail_en_erreur_propose_de_reessayer(client_consentant, utilisateur_consentant):
    reve = creer_reve(
        utilisateur_consentant, statut=Reve.Statut.ERREUR, message_erreur="Service indisponible."
    )

    contenu = client_consentant.get(reverse("detail_reve", args=[reve.pk])).content.decode()

    assert "Service indisponible." in contenu
    assert reverse("reessayer_reve", args=[reve.pk]) in contenu


# --- Suivi du statut -------------------------------------------------------


def test_statut_renvoie_le_statut_en_json(client_consentant, utilisateur_consentant):
    reve = creer_reve(utilisateur_consentant)

    reponse = client_consentant.get(reverse("statut_reve", args=[reve.pk]))

    assert reponse.json() == {"statut": "en_cours"}


def test_statut_d_un_autre_utilisateur_renvoie_404(client_consentant):
    autre = Utilisateur.objects.create_user(email="autre@exemple.fr", password="x")
    reve = creer_reve(autre)

    assert client_consentant.get(reverse("statut_reve", args=[reve.pk])).status_code == 404


# --- Nouvelle tentative ----------------------------------------------------


def test_reessayer_relance_le_traitement(
    client_consentant, utilisateur_consentant, traitements_lances
):
    reve = creer_reve(utilisateur_consentant, statut=Reve.Statut.ERREUR, message_erreur="Panne.")

    client_consentant.post(reverse("reessayer_reve", args=[reve.pk]))

    reve.refresh_from_db()
    assert reve.statut == Reve.Statut.EN_COURS
    assert reve.message_erreur == ""
    assert traitements_lances == [reve]


def test_reessayer_sans_audio_demande_un_nouvel_enregistrement(
    client_consentant, utilisateur_consentant, traitements_lances
):
    reve = creer_reve(utilisateur_consentant, statut=Reve.Statut.ERREUR, audio="")

    reponse = client_consentant.post(reverse("reessayer_reve", args=[reve.pk]))

    assert reponse.url == reverse("nouveau_reve")
    assert traitements_lances == []


def test_reessayer_un_reve_termine_ne_fait_rien(
    client_consentant, utilisateur_consentant, traitements_lances
):
    reve = creer_reve(utilisateur_consentant, statut=Reve.Statut.TERMINE)

    client_consentant.post(reverse("reessayer_reve", args=[reve.pk]))

    assert traitements_lances == []


def test_reessayer_refuse_une_requete_get(client_consentant, utilisateur_consentant):
    reve = creer_reve(utilisateur_consentant, statut=Reve.Statut.ERREUR)

    assert client_consentant.get(reverse("reessayer_reve", args=[reve.pk])).status_code == 405
