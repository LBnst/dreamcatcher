import base64
from datetime import timedelta
from decimal import Decimal

import httpx
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from dreams.models import AppelApi, Reve
from dreams.services import video
from dreams.services.image import ErreurGeneration
from dreams.services.quotas import BudgetEpuise
from dreams.services.video import lancer_video, suivre_video
from tests.outils import reponse_http

pytestmark = pytest.mark.django_db

URL_SUIVI = f"{video.URL_INTERACTIONS}/int-123"
VIDEO_INLINE = {
    "type": "video",
    "mime_type": "video/mp4",
    "data": base64.b64encode(b"octets-mp4").decode(),
}
VIDEO_HEBERGEE = {
    "type": "video",
    "uri": "https://generativelanguage.googleapis.com/v1beta/files/fichier-9",
}


def interaction(statut, *contenu):
    """Réponse de l'API Interactions : un statut et, éventuellement, des blocs de sortie."""
    return reponse_http(
        200,
        {
            "id": "int-123",
            "status": statut,
            "steps": [{"type": "model_output", "content": list(contenu)}],
        },
    )


@pytest.fixture(autouse=True)
def configuration(settings):
    settings.GEMINI_API_KEY = "cle-gemini"
    settings.GEMINI_MODELE_VIDEO = "omni-test"
    settings.RESOLUTION_VIDEO = "360p"
    settings.DUREE_VIDEO_SECONDES = 8
    settings.PRIX_VIDEO_USD_SECONDE = 0.023
    settings.TAUX_USD_EUR = 1.0
    settings.DUREE_MAX_VIDEO = 180


@pytest.fixture
def utilisateur():
    return get_user_model().objects.create_user(email="nom@exemple.fr", password="x")


@pytest.fixture
def reve(utilisateur):
    return Reve.objects.create(
        utilisateur=utilisateur, type_media=Reve.TypeMedia.VIDEO, transcription="Un rêve."
    )


@pytest.fixture
def reve_lance(utilisateur):
    return Reve.objects.create(
        utilisateur=utilisateur,
        type_media=Reve.TypeMedia.VIDEO,
        transcription="Un rêve.",
        id_tache_externe="int-123",
        generation_lancee_le=timezone.now(),
    )


def suivre(reve):
    suivre_video(reve.pk)
    reve.refresh_from_db()
    return reve


# --- Lancement -------------------------------------------------------------


def test_lancement_de_la_video(reve, faux_http):
    faux = faux_http(reponse_http(200, {"id": "int-123", "status": "in_progress"}))

    lancer_video(reve, "A scene.")

    assert reve.id_tache_externe == "int-123"
    assert reve.generation_lancee_le is not None
    envoi = faux.appels[0]
    assert envoi["url"] == video.URL_INTERACTIONS
    assert envoi["headers"] == {"x-goog-api-key": "cle-gemini"}
    assert envoi["json"]["model"] == "omni-test"
    assert envoi["json"]["input"] == "A scene."
    assert envoi["json"]["background"] is True
    assert envoi["json"]["response_format"]["duration"] == "8s"
    assert envoi["json"]["response_format"]["resolution"] == "360p"
    appel = AppelApi.objects.get()
    assert appel.statut == AppelApi.Statut.SUCCES
    assert appel.cout_eur == Decimal("0.1840")  # 8 s x 0,023 $


def test_quota_atteint_au_lancement(reve, faux_http):
    faux_http(reponse_http(429))

    with pytest.raises(ErreurGeneration, match="quota"):
        lancer_video(reve, "A scene.")

    assert not reve.id_tache_externe


def test_reponse_sans_identifiant(reve, faux_http):
    faux_http(reponse_http(200, {"status": "in_progress"}))

    with pytest.raises(ErreurGeneration):
        lancer_video(reve, "A scene.")

    assert AppelApi.objects.get().statut == AppelApi.Statut.ERREUR


def test_sans_cle_api_aucun_appel(reve, faux_http, settings):
    settings.GEMINI_API_KEY = ""
    faux = faux_http()

    with pytest.raises(ErreurGeneration):
        lancer_video(reve, "A scene.")

    assert faux.appels == []


def test_budget_epuise(reve, faux_http, settings):
    settings.BUDGET_MENSUEL_EUR = 0
    faux_http()

    with pytest.raises(BudgetEpuise):
        lancer_video(reve, "A scene.")


# --- Suivi -----------------------------------------------------------------


def test_video_encore_en_cours(reve_lance, faux_http):
    faux = faux_http(interaction("in_progress"))

    assert suivre(reve_lance).statut == Reve.Statut.EN_COURS
    assert faux.appels[0]["url"] == URL_SUIVI


def test_video_terminee_en_base64(reve_lance, faux_http):
    faux_http(interaction("completed", VIDEO_INLINE))

    reve = suivre(reve_lance)

    assert reve.statut == Reve.Statut.TERMINE
    assert reve.media.name.endswith(".mp4")
    with reve.media.open("rb") as fichier:
        assert fichier.read() == b"octets-mp4"


def test_video_terminee_hebergee_chez_google(reve_lance, faux_http):
    faux = faux_http(
        interaction("completed", VIDEO_HEBERGEE), reponse_http(200, content=b"octets-mp4")
    )

    reve = suivre(reve_lance)

    assert reve.statut == Reve.Statut.TERMINE
    telechargement = faux.appels[1]
    assert telechargement["url"] == f"{video.URL_FICHIERS}/fichier-9:download"
    assert telechargement["params"] == {"alt": "media"}


def test_fichier_heberge_pas_encore_pret(reve_lance, faux_http):
    faux_http(interaction("completed", VIDEO_HEBERGEE), reponse_http(404))

    assert suivre(reve_lance).statut == Reve.Statut.EN_COURS


def test_echec_signale_par_google(reve_lance, faux_http):
    faux_http(interaction("failed"))

    reve = suivre(reve_lance)

    assert reve.statut == Reve.Statut.ERREUR
    assert reve.message_erreur == video.MESSAGE_INDISPONIBLE
    assert reve.id_tache_externe == ""  # une nouvelle tentative relancera la génération
    assert AppelApi.objects.get().message_erreur == "Statut : failed"


def test_reponse_terminee_sans_video(reve_lance, faux_http):
    faux_http(interaction("completed"))

    assert suivre(reve_lance).statut == Reve.Statut.ERREUR


def test_delai_depasse(reve_lance, faux_http):
    reve_lance.generation_lancee_le = timezone.now() - timedelta(seconds=181)
    reve_lance.save()
    faux_http(interaction("in_progress"))

    reve = suivre(reve_lance)

    assert reve.statut == Reve.Statut.ERREUR
    assert reve.message_erreur == video.MESSAGE_DELAI


def test_incident_reseau_passager(reve_lance, faux_http):
    faux_http(httpx.ConnectError("coupure"))

    assert suivre(reve_lance).statut == Reve.Statut.EN_COURS
    assert not AppelApi.objects.exists()


def test_reve_deja_termine_aucun_appel(reve_lance, faux_http):
    reve_lance.statut = Reve.Statut.TERMINE
    reve_lance.save()
    faux = faux_http()

    suivre(reve_lance)

    assert faux.appels == []


# --- Cas limites -----------------------------------------------------------


def test_reponse_illisible_au_lancement(reve, faux_http):
    faux_http(reponse_http(200, content=b"pas du json"))

    with pytest.raises(ErreurGeneration):
        lancer_video(reve, "A scene.")


def test_erreur_inattendue_pendant_le_suivi(reve_lance, monkeypatch):
    def avancer_en_panne(reve):
        raise RuntimeError("bug")

    monkeypatch.setattr(video, "_avancer", avancer_en_panne)

    reve = suivre(reve_lance)

    assert reve.statut == Reve.Statut.ERREUR
    assert reve.message_erreur == video.MESSAGE_INDISPONIBLE
    assert AppelApi.objects.get().message_erreur == "Erreur inattendue"


def test_suivi_sans_date_de_lancement(reve_lance, faux_http):
    reve_lance.generation_lancee_le = None
    reve_lance.save()
    faux_http(interaction("in_progress"))

    assert suivre(reve_lance).statut == Reve.Statut.EN_COURS
