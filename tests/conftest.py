import pytest


# supprime les fichiers créés pendant les tests
@pytest.fixture(autouse=True)
def media_temporaire(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
