from pathlib import Path
from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile

from dreams.models import Reve
from dreams.services import pipeline
from dreams.services.emotion import ErreurClassification
from dreams.services.image import ErreurGeneration
from dreams.services.quotas import MESSAGE_BUDGET, BudgetEpuise
from dreams.services.transcription import ErreurTranscription

pytestmark = pytest.mark.django_db


@pytest.fixture
def reve():
    utilisateur = get_user_model().objects.create_user(email="nom@exemple.fr", password="x")
    audio = SimpleUploadedFile("reve.webm", b"faux audio")
    return Reve.objects.create(utilisateur=utilisateur, audio=audio)


def faux_generer_image(reve, prompt):
    reve.media.save("reve.jpg", ContentFile(b"image"), save=False)


@pytest.fixture
def services(monkeypatch):
    """Simule toutes les étapes ; chaque test peut en remplacer une."""

    def installer(transcrire=None, classer=None, prompt=None, image=None):
        monkeypatch.setattr(pipeline, "transcrire", transcrire or (lambda reve: "Je volais."))
        monkeypatch.setattr(
            pipeline, "classer_emotion", classer or (lambda texte: (Reve.Emotion.HEUREUX, 0.81))
        )
        monkeypatch.setattr(
            pipeline, "ecrire_prompt_visuel", prompt or (lambda reve: "A flying figure.")
        )
        monkeypatch.setattr(pipeline, "generer_image", image or faux_generer_image)

    return installer


def lever(erreur):
    def fonction(*args):
        raise erreur

    return fonction


def test_traitement_complet(reve, services):
    services()
    chemin_audio = Path(reve.audio.path)

    pipeline.traiter_reve(reve.pk)

    reve.refresh_from_db()
    assert reve.statut == Reve.Statut.TERMINE
    assert reve.transcription == "Je volais."
    assert reve.emotion == Reve.Emotion.HEUREUX
    assert reve.score_emotion == 0.81
    assert reve.media  # image générée
    assert not reve.audio  # RGPD : audio supprimé...
    assert not chemin_audio.exists()  # ...y compris le fichier sur le disque


def test_reve_video_sans_image_pour_l_instant(reve, services):
    services()
    reve.type_media = Reve.TypeMedia.VIDEO
    reve.save()

    pipeline.traiter_reve(reve.pk)

    reve.refresh_from_db()
    assert reve.statut == Reve.Statut.TERMINE
    assert not reve.media


def test_echec_de_transcription_conserve_le_reve_et_l_audio(reve, services):
    services(transcrire=lever(ErreurTranscription("Service indisponible.")))

    pipeline.traiter_reve(reve.pk)

    reve.refresh_from_db()
    assert reve.statut == Reve.Statut.ERREUR
    assert reve.message_erreur == "Service indisponible."
    assert reve.audio  # conservé pour une nouvelle tentative


def test_echec_de_classification_conserve_la_transcription(reve, services):
    services(classer=lever(ErreurClassification("modèle absent")))

    pipeline.traiter_reve(reve.pk)

    reve.refresh_from_db()
    assert reve.statut == Reve.Statut.TERMINE
    assert reve.transcription == "Je volais."
    assert reve.emotion == ""


def test_echec_de_l_image_conserve_la_transcription(reve, services):
    services(image=lever(ErreurGeneration("Génération impossible.")))

    pipeline.traiter_reve(reve.pk)

    reve.refresh_from_db()
    assert reve.statut == Reve.Statut.ERREUR
    assert reve.message_erreur == "Génération impossible."
    assert reve.transcription == "Je volais."
    assert not reve.audio


def test_nouvelle_tentative_ne_refait_pas_la_transcription(reve, services):
    services(transcrire=lever(AssertionError("la transcription ne doit pas être refaite")))
    reve.audio.delete(save=False)
    reve.transcription = "Déjà transcrit."
    reve.emotion = Reve.Emotion.TRISTE
    reve.statut = Reve.Statut.ERREUR
    reve.save()

    pipeline.traiter_reve(reve.pk)

    reve.refresh_from_db()
    assert reve.statut == Reve.Statut.TERMINE
    assert reve.transcription == "Déjà transcrit."
    assert reve.media


def test_erreur_inattendue_donne_un_message_clair(reve, services):
    services(transcrire=lever(RuntimeError("bug")))

    pipeline.traiter_reve(reve.pk)

    reve.refresh_from_db()
    assert reve.statut == Reve.Statut.ERREUR
    assert reve.message_erreur == pipeline.MESSAGE_INATTENDU


def test_budget_epuise_met_le_reve_en_erreur(reve, services):
    services(transcrire=lever(BudgetEpuise(MESSAGE_BUDGET)))

    pipeline.traiter_reve(reve.pk)

    reve.refresh_from_db()
    assert reve.statut == Reve.Statut.ERREUR
    assert reve.message_erreur == MESSAGE_BUDGET
    assert reve.audio  # conservé : on pourra réessayer le mois prochain


def test_demarrer_traitement_immediat(reve, services, settings):
    services()
    settings.TRAITEMENT_EN_ARRIERE_PLAN = False

    pipeline.demarrer_traitement(reve)

    reve.refresh_from_db()
    assert reve.statut == Reve.Statut.TERMINE


def test_demarrer_traitement_en_arriere_plan(reve, settings, monkeypatch):
    settings.TRAITEMENT_EN_ARRIERE_PLAN = True
    evenements = []

    class FauxThread:
        def __init__(self, target, args, daemon):
            evenements.append((target, args, daemon))

        def start(self):
            evenements.append("demarre")

    monkeypatch.setattr(pipeline.threading, "Thread", FauxThread)

    pipeline.demarrer_traitement(reve)

    assert evenements == [(pipeline._traiter_en_arriere_plan, (reve.pk,), True), "demarre"]


def test_le_thread_ferme_sa_connexion(monkeypatch):
    evenements = []
    monkeypatch.setattr(pipeline, "traiter_reve", evenements.append)
    monkeypatch.setattr(
        pipeline, "connection", SimpleNamespace(close=lambda: evenements.append("fermee"))
    )

    pipeline._traiter_en_arriere_plan(42)

    assert evenements == [42, "fermee"]
