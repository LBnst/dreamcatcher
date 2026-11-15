from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from dreams.models import AppelApi, Reve
from dreams.services.quotas import (
    BudgetEpuise,
    budget_atteint,
    depense_du_mois,
    message_quota,
    verifier_budget,
)

pytestmark = pytest.mark.django_db

Utilisateur = get_user_model()


@pytest.fixture
def utilisateur():
    return Utilisateur.objects.create_user(email="nom@exemple.fr", password="x")


@pytest.fixture(autouse=True)
def quotas(settings):
    settings.QUOTA_REVES_PAR_JOUR = 3
    settings.QUOTA_VIDEOS_PAR_JOUR = 1
    settings.BUDGET_MENSUEL_EUR = 1.0


def creer_appel(cout, il_y_a=timedelta(0)):
    appel = AppelApi.objects.create(
        service=AppelApi.Service.IMAGE, statut=AppelApi.Statut.SUCCES, cout_eur=Decimal(cout)
    )
    # date_appel est remplie automatiquement : on la recule après coup.
    AppelApi.objects.filter(pk=appel.pk).update(date_appel=timezone.now() - il_y_a)


def creer_reves(utilisateur, nombre, type_media=Reve.TypeMedia.IMAGE, il_y_a=timedelta(0)):
    for _ in range(nombre):
        reve = Reve.objects.create(utilisateur=utilisateur, type_media=type_media)
        Reve.objects.filter(pk=reve.pk).update(date_creation=timezone.now() - il_y_a)


# --- Budget mensuel --------------------------------------------------------


def test_depense_nulle_en_debut_de_mois():
    assert depense_du_mois() == Decimal("0")


def test_depense_du_mois_ignore_les_mois_precedents():
    creer_appel("0.5000")
    creer_appel("0.2500")
    creer_appel("9.0000", il_y_a=timedelta(days=40))  # toujours le mois précédent

    assert depense_du_mois() == Decimal("0.75")


def test_budget_atteint_au_centime_pres():
    creer_appel("0.9999")
    assert not budget_atteint()

    creer_appel("0.0001")
    assert budget_atteint()


def test_verifier_budget_bloque_quand_il_est_atteint():
    creer_appel("1.0000")

    with pytest.raises(BudgetEpuise):
        verifier_budget()


# --- Quota quotidien -------------------------------------------------------


def test_sous_le_quota_aucun_message(utilisateur):
    creer_reves(utilisateur, 2)

    assert message_quota(utilisateur, Reve.TypeMedia.IMAGE) is None


def test_quota_de_reves_atteint(utilisateur):
    creer_reves(utilisateur, 3)

    assert "3 rêves" in message_quota(utilisateur, Reve.TypeMedia.IMAGE)


def test_les_reves_d_hier_ne_comptent_pas(utilisateur):
    creer_reves(utilisateur, 3, il_y_a=timedelta(days=1))

    assert message_quota(utilisateur, Reve.TypeMedia.IMAGE) is None


def test_les_reves_des_autres_ne_comptent_pas(utilisateur):
    autre = Utilisateur.objects.create_user(email="autre@exemple.fr", password="x")
    creer_reves(autre, 3)

    assert message_quota(utilisateur, Reve.TypeMedia.IMAGE) is None


def test_quota_video_atteint_mais_image_encore_possible(utilisateur):
    creer_reves(utilisateur, 1, type_media=Reve.TypeMedia.VIDEO)

    assert "vidéos" in message_quota(utilisateur, Reve.TypeMedia.VIDEO)
    assert message_quota(utilisateur, Reve.TypeMedia.IMAGE) is None
