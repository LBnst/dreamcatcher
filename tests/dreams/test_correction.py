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


@pytest.fixture
def reve(utilisateur):
    return Reve.objects.create(
        utilisateur=utilisateur,
        transcription="Je volais au-dessus de la mere.",
        emotion=Reve.Emotion.TRISTE,
        statut=Reve.Statut.TERMINE,
    )


def url(reve):
    return reverse("corriger_reve", args=[reve.pk])


def test_formulaire_pre_rempli(client_connecte, reve):
    contenu = client_connecte.get(url(reve)).content.decode()

    assert "Je volais au-dessus de la mere." in contenu


def test_corriger_la_transcription_et_l_emotion(client_connecte, reve):
    donnees = {"transcription": "Je volais au-dessus de la mer.", "emotion": "heureux"}

    reponse = client_connecte.post(url(reve), donnees)

    assert reponse.url == reverse("detail_reve", args=[reve.pk])
    reve.refresh_from_db()
    assert reve.transcription == "Je volais au-dessus de la mer."
    assert reve.emotion == "heureux"
    assert reve.emotion_corrigee is True


def test_corriger_seulement_la_transcription(client_connecte, reve):
    donnees = {"transcription": "Je volais au-dessus de la mer.", "emotion": "triste"}

    client_connecte.post(url(reve), donnees)

    reve.refresh_from_db()
    assert reve.emotion_corrigee is False


def test_champs_obligatoires(client_connecte, reve):
    reponse = client_connecte.post(url(reve), {"transcription": "", "emotion": ""})

    assert reponse.status_code == 200
    reve.refresh_from_db()
    assert reve.transcription == "Je volais au-dessus de la mere."


def test_emotion_inconnue_refusee(client_connecte, reve):
    reponse = client_connecte.post(url(reve), {"transcription": "Texte.", "emotion": "joyeux"})

    assert reponse.status_code == 200
    reve.refresh_from_db()
    assert reve.emotion == "triste"


def test_impossible_pendant_le_traitement(client_connecte, reve):
    reve.statut = Reve.Statut.EN_COURS
    reve.save()

    reponse = client_connecte.post(url(reve), {"transcription": "Texte.", "emotion": "heureux"})

    assert reponse.url == reverse("detail_reve", args=[reve.pk])
    reve.refresh_from_db()
    assert reve.emotion == "triste"


def test_reve_d_un_autre_utilisateur(client, reve):
    autre = get_user_model().objects.create_user(email="autre@exemple.fr", password="x")
    client.force_login(autre)

    assert client.get(url(reve)).status_code == 404
