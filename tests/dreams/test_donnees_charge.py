from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command

from dreams.management.commands.creer_donnees_charge import DOMAINE, MOT_DE_PASSE
from dreams.models import Reve

pytestmark = pytest.mark.django_db
Utilisateur = get_user_model()


def lancer(**options):
    call_command("creer_donnees_charge", stdout=StringIO(), **options)


def test_cree_les_comptes_et_les_reves():
    lancer(comptes=2, reves=5)

    assert Utilisateur.objects.filter(email__endswith=DOMAINE).count() == 2
    assert Reve.objects.count() == 10


def test_relancer_ne_duplique_rien():
    lancer(comptes=2, reves=5)
    lancer(comptes=2, reves=5)

    assert Reve.objects.count() == 10


def test_les_comptes_peuvent_se_connecter(client):
    lancer(comptes=1, reves=1)

    assert client.login(email=f"charge1@{DOMAINE}", password=MOT_DE_PASSE)


def test_la_suppression_epargne_les_vrais_comptes():
    Utilisateur.objects.create_user(email="nom@exemple.fr", password="x")
    lancer(comptes=2, reves=3)

    lancer(supprimer=True)

    assert list(Utilisateur.objects.values_list("email", flat=True)) == ["nom@exemple.fr"]
    assert Reve.objects.count() == 0
