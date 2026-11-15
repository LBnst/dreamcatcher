import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

Utilisateur = get_user_model()

pytestmark = pytest.mark.django_db

MOT_DE_PASSE = "UnMotDePasseSolide!42"


@pytest.fixture
def utilisateur():
    return Utilisateur.objects.create_user(email="nom@exemple.fr", password=MOT_DE_PASSE)


# --- Inscription -----------------------------------------------------------


def test_page_inscription_accessible_sans_connexion(client):
    assert client.get(reverse("inscription")).status_code == 200


def test_inscription_cree_le_compte_et_connecte(client):
    reponse = client.post(
        reverse("inscription"),
        {"email": "nouveau@exemple.fr", "password1": MOT_DE_PASSE, "password2": MOT_DE_PASSE},
    )

    assert reponse.status_code == 302
    assert reponse.url == reverse("accueil")
    assert Utilisateur.objects.filter(email="nouveau@exemple.fr").exists()
    assert client.get(reverse("accueil")).context["user"].is_authenticated


def test_inscription_refuse_un_email_deja_utilise_meme_en_majuscules(client, utilisateur):
    reponse = client.post(
        reverse("inscription"),
        {"email": "NOM@exemple.fr", "password1": MOT_DE_PASSE, "password2": MOT_DE_PASSE},
    )

    assert reponse.status_code == 200
    assert "email" in reponse.context["form"].errors
    assert Utilisateur.objects.count() == 1


def test_inscription_refuse_des_mots_de_passe_differents(client):
    reponse = client.post(
        reverse("inscription"),
        {"email": "nouveau@exemple.fr", "password1": MOT_DE_PASSE, "password2": "autre"},
    )

    assert reponse.status_code == 200
    assert not Utilisateur.objects.exists()


def test_inscription_refuse_un_mot_de_passe_trop_faible(client):
    reponse = client.post(
        reverse("inscription"),
        {"email": "nouveau@exemple.fr", "password1": "123", "password2": "123"},
    )

    assert reponse.status_code == 200
    assert not Utilisateur.objects.exists()


def test_inscription_redirige_un_utilisateur_deja_connecte(client, utilisateur):
    client.force_login(utilisateur)

    assert client.get(reverse("inscription")).url == reverse("accueil")


# --- Connexion / déconnexion -----------------------------------------------


def test_connexion_avec_email_et_mot_de_passe(client, utilisateur):
    reponse = client.post(
        reverse("connexion"), {"username": "nom@exemple.fr", "password": MOT_DE_PASSE}
    )

    assert reponse.status_code == 302
    assert reponse.url == reverse("accueil")


def test_connexion_refusee_avec_mauvais_mot_de_passe(client, utilisateur):
    reponse = client.post(reverse("connexion"), {"username": "nom@exemple.fr", "password": "faux"})

    assert reponse.status_code == 200
    assert not reponse.context["user"].is_authenticated


def test_deconnexion(client, utilisateur):
    client.force_login(utilisateur)

    reponse = client.post(reverse("deconnexion"))

    assert reponse.url == reverse("connexion")
    assert client.get(reverse("accueil")).status_code == 302  # plus connecté


# --- Accès réservé ---------------------------------------------------------


def test_accueil_redirige_vers_la_connexion_si_anonyme(client):
    reponse = client.get(reverse("accueil"))

    assert reponse.status_code == 302
    assert reponse.url.startswith(reverse("connexion"))


def test_accueil_accessible_une_fois_connecte(client, utilisateur):
    client.force_login(utilisateur)

    reponse = client.get(reverse("accueil"))

    assert reponse.status_code == 200
    assert "nom@exemple.fr" in reponse.content.decode()
