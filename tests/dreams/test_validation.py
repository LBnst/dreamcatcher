import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from dreams import views
from dreams.models import Reve
from dreams.services import pipeline

pytestmark = pytest.mark.django_db


@pytest.fixture
def utilisateur():
    return get_user_model().objects.create_user(email="nom@exemple.fr", password="x")


@pytest.fixture
def client_connecte(client, utilisateur):
    client.force_login(utilisateur)
    return client


@pytest.fixture
def a_valider(utilisateur):
    return Reve.objects.create(
        utilisateur=utilisateur,
        transcription="Je volais au-dessus de la mere.",
        emotion=Reve.Emotion.TRISTE,
        statut=Reve.Statut.A_VALIDER,
        type_media="image",
    )


@pytest.fixture
def lancements(monkeypatch):
    """Remplace le lancement du traitement pour n'appeler aucune API."""
    appels = []
    monkeypatch.setattr(views, "demarrer_traitement", lambda reve: appels.append(reve.pk))
    return appels


@pytest.fixture
def faux_services(monkeypatch):
    """Simule la transcription, l'émotion, le prompt et l'image dans le pipeline."""
    images = []
    monkeypatch.setattr(pipeline, "transcrire", lambda reve: "Un rêve de forêt.")
    monkeypatch.setattr(pipeline, "classer_emotion", lambda texte: ("heureux", 0.9))
    monkeypatch.setattr(pipeline, "ecrire_prompt_visuel", lambda reve: "a forest")
    monkeypatch.setattr(pipeline, "generer_image", lambda reve, prompt: images.append(prompt))
    return images


def url(reve):
    return reverse("valider_reve", args=[reve.pk])


# --- Pipeline ---------------------------------------------------------------


def test_le_pipeline_s_arrete_avant_le_visuel(utilisateur, faux_services):
    reve = Reve.objects.create(
        utilisateur=utilisateur, statut=Reve.Statut.EN_COURS, type_media="image"
    )

    pipeline.traiter_reve(reve.pk)

    reve.refresh_from_db()
    assert reve.statut == Reve.Statut.A_VALIDER
    assert reve.transcription == "Un rêve de forêt."
    assert reve.emotion == "heureux"
    assert faux_services == []  # aucune image générée


def test_le_pipeline_genere_apres_validation(utilisateur, faux_services):
    reve = Reve.objects.create(
        utilisateur=utilisateur,
        transcription="Un rêve de forêt.",
        emotion="heureux",
        valide=True,
        statut=Reve.Statut.EN_COURS,
        type_media="image",
    )

    pipeline.traiter_reve(reve.pk)

    reve.refresh_from_db()
    assert reve.statut == Reve.Statut.TERMINE
    assert faux_services == ["a forest"]


# --- Page de validation -----------------------------------------------------


def test_formulaire_pre_rempli(client_connecte, a_valider):
    contenu = client_connecte.get(url(a_valider)).content.decode()

    assert "Je volais au-dessus de la mere." in contenu
    assert "Générer le visuel" in contenu


def test_valider_lance_la_generation(client_connecte, a_valider, lancements):
    donnees = {"transcription": "Je volais au-dessus de la mer.", "emotion": "heureux"}

    reponse = client_connecte.post(url(a_valider), donnees)

    assert reponse.url == reverse("detail_reve", args=[a_valider.pk])
    a_valider.refresh_from_db()
    assert a_valider.statut == Reve.Statut.EN_COURS
    assert a_valider.valide is True
    assert a_valider.transcription == "Je volais au-dessus de la mer."
    assert a_valider.emotion_corrigee is True
    assert lancements == [a_valider.pk]


def test_valider_sans_changer_l_emotion(client_connecte, a_valider, lancements):
    donnees = {"transcription": "Je volais au-dessus de la mer.", "emotion": "triste"}

    client_connecte.post(url(a_valider), donnees)

    a_valider.refresh_from_db()
    assert a_valider.emotion_corrigee is False


def test_un_double_clic_ne_lance_qu_une_generation(client_connecte, a_valider, lancements):
    donnees = {"transcription": "Un rêve.", "emotion": "heureux"}

    client_connecte.post(url(a_valider), donnees)
    client_connecte.post(url(a_valider), donnees)

    assert lancements == [a_valider.pk]


def test_formulaire_invalide_ne_lance_rien(client_connecte, a_valider, lancements):
    reponse = client_connecte.post(url(a_valider), {"transcription": "", "emotion": ""})

    assert reponse.status_code == 200
    assert lancements == []
    a_valider.refresh_from_db()
    assert a_valider.statut == Reve.Statut.A_VALIDER


def test_reve_d_un_autre_utilisateur(client, a_valider):
    autre = get_user_model().objects.create_user(email="autre@exemple.fr", password="x")
    client.force_login(autre)

    assert client.get(url(a_valider)).status_code == 404


def test_le_detail_invite_a_valider(client_connecte, a_valider):
    contenu = client_connecte.get(reverse("detail_reve", args=[a_valider.pk])).content.decode()

    assert url(a_valider) in contenu


def test_corriger_renvoie_vers_la_validation(client_connecte, a_valider):
    reponse = client_connecte.get(reverse("corriger_reve", args=[a_valider.pk]))

    assert reponse.url == url(a_valider)
