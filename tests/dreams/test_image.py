from decimal import Decimal

import httpx
import pytest
from django.contrib.auth import get_user_model

from dreams.models import AppelApi, Reve
from dreams.services import image
from dreams.services.image import ErreurGeneration, generer_image
from dreams.services.quotas import BudgetEpuise
from tests.outils import reponse_http

pytestmark = pytest.mark.django_db

URL_SUIVI = "https://api.bfl.ai/v1/get_result?id=abc"
SOUMISSION = reponse_http(200, {"id": "abc", "polling_url": URL_SUIVI})
EN_ATTENTE = reponse_http(200, {"status": "Pending"})
PRETE = reponse_http(200, {"status": "Ready", "result": {"sample": "https://cdn.bfl.ai/abc.jpg"}})
FICHIER = reponse_http(200, content=b"octets-jpeg")


@pytest.fixture(autouse=True)
def configuration(settings):
    settings.BFL_API_KEY = "cle-bfl"
    settings.BFL_MODELE_IMAGE = "flux-test"
    settings.PRIX_IMAGE_USD = 0.009
    settings.TAUX_USD_EUR = 1.0


@pytest.fixture
def reve():
    utilisateur = get_user_model().objects.create_user(email="nom@exemple.fr", password="x")
    return Reve.objects.create(utilisateur=utilisateur, transcription="Un rêve.")


def test_image_generee_et_enregistree(reve, faux_http):
    faux = faux_http(SOUMISSION, EN_ATTENTE, PRETE, FICHIER)

    generer_image(reve, "A snowy city.")

    with reve.media.open("rb") as fichier:
        assert fichier.read() == b"octets-jpeg"
    appel = AppelApi.objects.get()
    assert appel.service == AppelApi.Service.IMAGE
    assert appel.statut == AppelApi.Statut.SUCCES
    assert appel.cout_eur == Decimal("0.0090")
    soumission = faux.appels[0]
    assert soumission["url"] == "https://api.bfl.ai/v1/flux-test"
    assert soumission["headers"] == {"x-key": "cle-bfl"}
    assert soumission["json"]["prompt"] == "A snowy city."
    assert faux.appels[1]["url"] == URL_SUIVI


def test_incident_passager_pendant_le_suivi(reve, faux_http):
    faux_http(SOUMISSION, httpx.ConnectError("coupure"), PRETE, FICHIER)

    generer_image(reve, "A scene.")

    assert reve.media


def test_contenu_refuse_par_la_moderation(reve, faux_http):
    faux_http(SOUMISSION, reponse_http(200, {"status": "Content Moderated"}))

    with pytest.raises(ErreurGeneration, match="refusé"):
        generer_image(reve, "A scene.")

    appel = AppelApi.objects.get()
    assert appel.statut == AppelApi.Statut.ERREUR
    assert appel.message_erreur == "Statut : Content Moderated"
    assert not reve.media


def test_delai_de_generation_depasse(reve, faux_http, monkeypatch):
    monkeypatch.setattr(image, "DUREE_MAX_GENERATION", 0)
    faux_http(SOUMISSION)

    with pytest.raises(ErreurGeneration):
        generer_image(reve, "A scene.")

    assert AppelApi.objects.get().message_erreur == "Image non prête en 0 s"


def test_credits_epuises(reve, faux_http):
    faux_http(reponse_http(402))

    with pytest.raises(ErreurGeneration, match="crédits"):
        generer_image(reve, "A scene.")


def test_sans_cle_api_aucun_appel(reve, faux_http, settings):
    settings.BFL_API_KEY = ""
    faux = faux_http()

    with pytest.raises(ErreurGeneration):
        generer_image(reve, "A scene.")

    assert faux.appels == []


def test_budget_epuise(reve, faux_http, settings):
    settings.BUDGET_MENSUEL_EUR = 0
    faux_http()

    with pytest.raises(BudgetEpuise):
        generer_image(reve, "A scene.")


def test_statut_intermediaire_inconnu_continue_d_attendre(reve, faux_http):
    # Cas réel rencontré en test manuel : FLUX 3 renvoie « Generating ».
    faux_http(SOUMISSION, reponse_http(200, {"status": "Generating"}), PRETE, FICHIER)

    generer_image(reve, "A scene.")

    assert reve.media


def test_echec_signale_par_le_fournisseur(reve, faux_http):
    faux_http(SOUMISSION, reponse_http(200, {"status": "Error"}))

    with pytest.raises(ErreurGeneration):
        generer_image(reve, "A scene.")

    assert AppelApi.objects.get().message_erreur == "Statut : Error"


def test_echec_du_telechargement_de_l_image(reve, faux_http):
    faux_http(SOUMISSION, PRETE, reponse_http(404))

    with pytest.raises(ErreurGeneration):
        generer_image(reve, "A scene.")

    assert AppelApi.objects.get().message_erreur == "HTTPStatusError"
    assert not reve.media
