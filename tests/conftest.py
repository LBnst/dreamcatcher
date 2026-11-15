import httpx
import pytest

from tests.outils import FauxHttp


@pytest.fixture(autouse=True)
def media_temporaire(settings, tmp_path):
    """Les fichiers envoyés pendant les tests vont dans un dossier temporaire, effacé ensuite."""
    settings.MEDIA_ROOT = tmp_path / "media"


# aucun test n'appelle une vraie API ni ne lance de thread
@pytest.fixture(autouse=True)
def aucun_appel_reel(settings):
    settings.MISTRAL_API_KEY = ""
    settings.BFL_API_KEY = ""
    settings.GEMINI_API_KEY = ""
    settings.TRAITEMENT_EN_ARRIERE_PLAN = False


@pytest.fixture(autouse=True)
def pauses_nulles(monkeypatch):
    """Supprime les pauses entre tentatives et entre interrogations : tests rapides."""
    from dreams.services import appels_api, image

    monkeypatch.setattr(appels_api, "PAUSE_ENTRE_TENTATIVES", 0)
    monkeypatch.setattr(image, "PAUSE_SUIVI", 0)


@pytest.fixture
def faux_http(monkeypatch):
    """Installe un faux httpx.request ; usage : ``faux = faux_http(reponse1, reponse2)``."""

    def installer(*resultats):
        faux = FauxHttp(*resultats)
        monkeypatch.setattr(httpx, "request", faux)
        return faux

    return installer
