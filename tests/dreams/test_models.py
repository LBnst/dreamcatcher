from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone

from dreams.models import AppelApi, Reve

pytestmark = pytest.mark.django_db


@pytest.fixture
def utilisateur():
    return get_user_model().objects.create_user(email="nathan@exemple.fr", password="x")


def test_reve_valeurs_par_defaut(utilisateur):
    reve = Reve.objects.create(utilisateur=utilisateur)

    assert reve.date_reve == timezone.localdate()
    assert reve.type_media == Reve.TypeMedia.IMAGE
    assert reve.statut == Reve.Statut.EN_COURS
    assert "nathan@exemple.fr" in str(reve)


def test_supprimer_le_compte_supprime_ses_reves(utilisateur):
    Reve.objects.create(utilisateur=utilisateur)

    utilisateur.delete()

    assert Reve.objects.count() == 0


def test_supprimer_un_reve_conserve_le_cout_de_ses_appels(utilisateur):
    reve = Reve.objects.create(utilisateur=utilisateur)
    appel = AppelApi.objects.create(
        reve=reve,
        service=AppelApi.Service.IMAGE,
        statut=AppelApi.Statut.SUCCES,
        cout_eur=Decimal("0.0080"),
    )

    reve.delete()
    appel.refresh_from_db()

    assert appel.reve is None
    assert appel.cout_eur == Decimal("0.0080")
    assert str(appel) == "Image – Succès"


@pytest.mark.parametrize("type_media", [Reve.TypeMedia.IMAGE, Reve.TypeMedia.VIDEO])
def test_reve_accepte_image_et_video(utilisateur, type_media):
    reve = Reve(utilisateur=utilisateur, type_media=type_media)

    reve.full_clean()  # lève une ValidationError si une valeur est invalide
    reve.save()

    assert Reve.objects.get(pk=reve.pk).type_media == type_media


def test_reve_refuse_un_type_de_media_inconnu(utilisateur):
    reve = Reve(utilisateur=utilisateur, type_media="gif")

    with pytest.raises(ValidationError):
        reve.full_clean()


def test_reve_video_conserve_l_identifiant_de_tache(utilisateur):
    reve = Reve.objects.create(
        utilisateur=utilisateur,
        type_media=Reve.TypeMedia.VIDEO,
        id_tache_externe="operations/abc123",
    )

    assert Reve.objects.get(pk=reve.pk).id_tache_externe == "operations/abc123"


@pytest.mark.parametrize(
    "service", [AppelApi.Service.TRANSCRIPTION, AppelApi.Service.IMAGE, AppelApi.Service.VIDEO]
)
def test_appel_api_accepte_chaque_service(utilisateur, service):
    reve = Reve.objects.create(utilisateur=utilisateur)
    appel = AppelApi(reve=reve, service=service, statut=AppelApi.Statut.SUCCES)

    appel.full_clean()
    appel.save()

    assert reve.appels_api.get().service == service
