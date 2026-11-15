from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from dreams.models import Reve

pytestmark = pytest.mark.django_db


@pytest.fixture
def utilisateur():
    return get_user_model().objects.create_user(email="nom@exemple.fr", password="x")


def test_supprimer_un_reve_efface_ses_fichiers(utilisateur, django_capture_on_commit_callbacks):
    reve = Reve.objects.create(
        utilisateur=utilisateur,
        audio=SimpleUploadedFile("reve.webm", b"audio"),
        media=SimpleUploadedFile("reve.jpg", b"image"),
    )
    chemins = [Path(reve.audio.path), Path(reve.media.path)]
    assert all(chemin.exists() for chemin in chemins)

    with django_capture_on_commit_callbacks(execute=True):
        reve.delete()

    assert not any(chemin.exists() for chemin in chemins)


def test_supprimer_un_reve_sans_fichier(utilisateur, django_capture_on_commit_callbacks):
    reve = Reve.objects.create(utilisateur=utilisateur)

    with django_capture_on_commit_callbacks(execute=True) as rappels:
        reve.delete()

    assert rappels == []
