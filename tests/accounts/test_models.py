import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

Utilisateur = get_user_model()

pytestmark = pytest.mark.django_db


def test_create_user_utilise_l_email_comme_identifiant():
    utilisateur = Utilisateur.objects.create_user(email="Nom@Exemple.FR", password="motdepasse")

    assert utilisateur.email == "Nom@exemple.fr"  # domaine normalisé en minuscules
    assert utilisateur.check_password("motdepasse")
    assert not utilisateur.is_staff
    assert str(utilisateur) == "Nom@exemple.fr"


def test_create_user_sans_email_leve_une_erreur():
    with pytest.raises(ValueError):
        Utilisateur.objects.create_user(email="", password="motdepasse")


def test_create_superuser_a_les_droits_admin():
    admin = Utilisateur.objects.create_superuser(email="admin@exemple.fr", password="motdepasse")

    assert admin.is_staff
    assert admin.is_superuser


def test_a_consenti_depend_de_la_date_de_consentement():
    utilisateur = Utilisateur.objects.create_user(email="aurelia@exemple.fr", password="x")
    assert not utilisateur.a_consenti

    utilisateur.consentement_le = timezone.now()
    assert utilisateur.a_consenti
