from decimal import Decimal

import httpx
import pytest
from django.contrib.auth import get_user_model

from dreams.models import AppelApi, Reve
from dreams.services.appels_api import ErreurApi, en_euros, requete
from tests.outils import reponse_http

pytestmark = pytest.mark.django_db


@pytest.fixture
def reve():
    utilisateur = get_user_model().objects.create_user(email="nom@exemple.fr", password="x")
    return Reve.objects.create(utilisateur=utilisateur)


def appeler(reve):
    return requete(
        "POST", "https://api.exemple.test", reve=reve, service=AppelApi.Service.IMAGE, timeout=10
    )


def statuts():
    return list(AppelApi.objects.order_by("id").values_list("statut", flat=True))


def test_succes_du_premier_coup(reve, faux_http):
    faux_http(reponse_http(200, {"ok": True}))

    reponse, debut = appeler(reve)

    assert reponse.json() == {"ok": True}
    assert isinstance(debut, float)
    assert statuts() == []  # le succès est enregistré par l'appelant, avec son coût


def test_timeout_puis_succes(reve, faux_http):
    faux = faux_http(httpx.ReadTimeout("lent"), reponse_http(200))

    appeler(reve)

    assert len(faux.appels) == 2
    assert statuts() == ["timeout"]


def test_erreur_serveur_temporaire_puis_succes(reve, faux_http):
    faux_http(reponse_http(503), reponse_http(200))

    appeler(reve)

    assert statuts() == ["erreur"]


@pytest.mark.parametrize("code", [402, 429])
def test_quota_ou_credits_epuises(reve, faux_http, code):
    faux = faux_http(reponse_http(code))

    with pytest.raises(ErreurApi) as erreur:
        appeler(reve)

    assert erreur.value.quota
    assert len(faux.appels) == 1
    assert statuts() == ["quota"]


def test_erreur_definitive_sans_nouvelle_tentative(reve, faux_http):
    faux = faux_http(reponse_http(401))

    with pytest.raises(ErreurApi) as erreur:
        appeler(reve)

    assert not erreur.value.quota
    assert len(faux.appels) == 1


def test_abandon_apres_trois_echecs(reve, faux_http):
    faux = faux_http(*[httpx.ConnectError("hors ligne")] * 3)

    with pytest.raises(ErreurApi):
        appeler(reve)

    assert len(faux.appels) == 3
    assert statuts() == ["erreur"] * 3


def test_conversion_en_euros(settings):
    settings.TAUX_USD_EUR = 0.9

    assert en_euros(0.009) == Decimal("0.0081")
