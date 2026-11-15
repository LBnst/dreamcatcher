import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

pytestmark = pytest.mark.django_db


@pytest.fixture
def client_admin(client):
    admin = get_user_model().objects.create_superuser(email="admin@exemple.fr", password="x")
    client.force_login(admin)
    return client


@pytest.mark.parametrize(
    "nom_url",
    [
        "admin:accounts_utilisateur_changelist",
        "admin:accounts_utilisateur_add",
        "admin:dreams_reve_changelist",
        "admin:dreams_appelapi_changelist",
    ],
)
def test_pages_admin_accessibles(client_admin, nom_url):
    assert client_admin.get(reverse(nom_url)).status_code == 200


def test_fiche_utilisateur_admin_accessible(client_admin):
    utilisateur = get_user_model().objects.get(email="admin@exemple.fr")
    url = reverse("admin:accounts_utilisateur_change", args=[utilisateur.pk])

    assert client_admin.get(url).status_code == 200
