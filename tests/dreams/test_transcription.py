from decimal import Decimal

import httpx
import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from dreams.models import AppelApi, Reve
from dreams.services import transcription
from dreams.services.transcription import ErreurTranscription, transcrire

pytestmark = pytest.mark.django_db


class FauxPost:
    """Remplace httpx.post : renvoie (ou lève) les résultats prévus, dans l'ordre."""

    def __init__(self, *resultats):
        self.resultats = list(resultats)
        self.appels = []

    def __call__(self, url, **kwargs):
        self.appels.append(kwargs)
        resultat = self.resultats.pop(0)
        if isinstance(resultat, Exception):
            raise resultat
        return resultat


def reponse(code, json=None):
    requete = httpx.Request("POST", transcription.URL_TRANSCRIPTION)
    return httpx.Response(code, json=json or {}, request=requete)


SUCCES = reponse(200, {"text": " J'étais dans une forêt. ", "usage": {"prompt_audio_seconds": 90}})


@pytest.fixture(autouse=True)
def configuration(settings, monkeypatch):
    settings.MISTRAL_API_KEY = "cle-de-test"
    settings.MISTRAL_MODELE_TRANSCRIPTION = "voxtral-test"
    settings.PRIX_TRANSCRIPTION_USD_MINUTE = 0.0035
    settings.TAUX_USD_EUR = 1.0
    monkeypatch.setattr(transcription, "PAUSE_ENTRE_TENTATIVES", 0)  # tests rapides


@pytest.fixture
def reve():
    utilisateur = get_user_model().objects.create_user(email="nom@exemple.fr", password="x")
    audio = SimpleUploadedFile("enregistrement.webm", b"faux audio")
    return Reve.objects.create(utilisateur=utilisateur, audio=audio)


@pytest.fixture
def faux_post(monkeypatch):
    def installer(*resultats):
        faux = FauxPost(*resultats)
        monkeypatch.setattr(transcription.httpx, "post", faux)
        return faux

    return installer


def statuts_enregistres():
    return list(AppelApi.objects.order_by("id").values_list("statut", flat=True))


# --- Succès ----------------------------------------------------------------


def test_transcription_reussie(reve, faux_post):
    faux_post(SUCCES)

    texte = transcrire(reve)

    assert texte == "J'étais dans une forêt."
    appel = AppelApi.objects.get()
    assert appel.statut == AppelApi.Statut.SUCCES
    assert appel.service == AppelApi.Service.TRANSCRIPTION
    assert appel.cout_eur == Decimal("0.0053")  # 1,5 min x 0,0035
    assert appel.latence_ms is not None


def test_requete_envoyee_a_l_api(reve, faux_post):
    faux = faux_post(SUCCES)

    transcrire(reve)

    envoi = faux.appels[0]
    assert envoi["headers"]["Authorization"] == "Bearer cle-de-test"
    assert envoi["data"] == {"model": "voxtral-test", "language": "fr"}
    assert envoi["files"]["file"][1] == b"faux audio"
    assert envoi["timeout"] == 30


# --- Nouvelles tentatives --------------------------------------------------


def test_timeout_puis_succes(reve, faux_post):
    faux = faux_post(httpx.ReadTimeout("lent"), SUCCES)

    assert transcrire(reve) == "J'étais dans une forêt."
    assert len(faux.appels) == 2
    assert statuts_enregistres() == ["timeout", "succes"]


def test_erreur_serveur_temporaire_puis_succes(reve, faux_post):
    faux_post(reponse(503), SUCCES)

    assert transcrire(reve) == "J'étais dans une forêt."
    assert statuts_enregistres() == ["erreur", "succes"]


def test_abandon_apres_trois_timeouts(reve, faux_post):
    faux = faux_post(*[httpx.ReadTimeout("lent")] * 3)

    with pytest.raises(ErreurTranscription):
        transcrire(reve)

    assert len(faux.appels) == 3  # 1 essai + 2 nouvelles tentatives
    assert statuts_enregistres() == ["timeout"] * 3


def test_abandon_apres_erreurs_reseau(reve, faux_post):
    faux_post(*[httpx.ConnectError("hors ligne")] * 3)

    with pytest.raises(ErreurTranscription):
        transcrire(reve)

    assert statuts_enregistres() == ["erreur"] * 3


# --- Erreurs définitives (pas de nouvelle tentative) -----------------------


def test_quota_depasse_ne_reessaie_pas(reve, faux_post):
    faux = faux_post(reponse(429))

    with pytest.raises(ErreurTranscription, match="quota"):
        transcrire(reve)

    assert len(faux.appels) == 1
    assert statuts_enregistres() == ["quota"]


def test_cle_invalide_ne_reessaie_pas(reve, faux_post):
    faux = faux_post(reponse(401))

    with pytest.raises(ErreurTranscription):
        transcrire(reve)

    assert len(faux.appels) == 1
    assert AppelApi.objects.get().message_erreur == "HTTP 401"


def test_aucune_parole_detectee(reve, faux_post):
    faux_post(reponse(200, {"text": "  ", "usage": {"prompt_audio_seconds": 5}}))

    with pytest.raises(ErreurTranscription, match="parole"):
        transcrire(reve)

    assert statuts_enregistres() == ["succes"]  # l'appel a quand même été facturé


def test_sans_cle_api_aucun_appel(reve, faux_post, settings):
    settings.MISTRAL_API_KEY = ""
    faux = faux_post()

    with pytest.raises(ErreurTranscription):
        transcrire(reve)

    assert faux.appels == []
    assert not AppelApi.objects.exists()
