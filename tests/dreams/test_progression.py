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


def creer(utilisateur, **champs):
    valeurs = {"statut": Reve.Statut.EN_COURS, "type_media": "image"} | champs
    return Reve.objects.create(utilisateur=utilisateur, **valeurs)


def etats(reve):
    return [etape["etat"] for etape in reve.etapes]


def test_etape_transcription(utilisateur):
    reve = creer(utilisateur)

    assert reve.etape_courante == "transcription"
    assert etats(reve) == ["en_cours", "a_venir", "a_venir"]
    assert reve.pourcentage_progression == 17


def test_etape_emotion(utilisateur):
    reve = creer(utilisateur, transcription="Un rêve.")

    assert reve.etape_courante == "emotion"
    assert etats(reve) == ["fait", "en_cours", "a_venir"]
    assert reve.pourcentage_progression == 50


def test_etape_generation_d_une_video(utilisateur):
    reve = creer(utilisateur, transcription="Un rêve.", emotion="heureux", type_media="video")

    assert etats(reve) == ["fait", "fait", "en_cours"]
    assert reve.etapes[-1]["libelle"] == "Création de la vidéo"
    assert reve.pourcentage_progression == 83


def test_reve_termine(utilisateur):
    reve = creer(utilisateur, statut=Reve.Statut.TERMINE)

    assert reve.etape_courante is None
    assert etats(reve) == ["fait", "fait", "fait"]
    assert reve.pourcentage_progression == 100


def test_api_de_progression(client_connecte, utilisateur):
    reve = creer(utilisateur, transcription="Un rêve.")

    reponse = client_connecte.get(reverse("progression_reve", args=[reve.pk]))

    assert reponse.json() == {"statut": "en_cours", "etape": "emotion", "pourcentage": 50}


def test_api_reservee_au_proprietaire(client, utilisateur):
    reve = creer(utilisateur)
    autre = get_user_model().objects.create_user(email="autre@exemple.fr", password="x")
    client.force_login(autre)

    assert client.get(reverse("progression_reve", args=[reve.pk])).status_code == 404


def test_la_page_de_detail_affiche_la_progression(client_connecte, utilisateur):
    reve = creer(utilisateur)

    contenu = client_connecte.get(reverse("detail_reve", args=[reve.pk])).content.decode()

    assert 'id="progression"' in contenu
    assert "Transcription de votre récit" in contenu
