import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from dreams.models import Reve

pytestmark = pytest.mark.django_db
ICONE_TRISTE = "img/emotions/triste.png"


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
        utilisateur=utilisateur, emotion=Reve.Emotion.TRISTE, statut=Reve.Statut.TERMINE
    )


def test_icone_dans_l_historique(client_connecte, reve):
    assert ICONE_TRISTE in client_connecte.get(reverse("historique")).content.decode()


def test_icone_dans_le_detail(client_connecte, reve):
    contenu = client_connecte.get(reverse("detail_reve", args=[reve.pk])).content.decode()

    assert ICONE_TRISTE in contenu


def test_icone_de_l_emotion_dominante(client_connecte, reve):
    assert ICONE_TRISTE in client_connecte.get(reverse("tableau_de_bord")).content.decode()
