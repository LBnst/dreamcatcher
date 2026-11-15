import pytest
from django.core.management import call_command

from dreams.models import Reve
from dreams.services import emotion
from dreams.services.emotion import ErreurClassification, classer_emotion


class FauxClassifieur:
    """Imite le pipeline Hugging Face : place `libelle` en tête avec le score donné."""

    def __init__(self, libelle="fear", score=0.87654):
        self.libelle = libelle
        self.score = score
        self.appels = []

    def __call__(self, texte, candidate_labels, hypothesis_template):
        self.appels.append(
            {"texte": texte, "libelles": candidate_labels, "gabarit": hypothesis_template}
        )
        autres = [libelle for libelle in candidate_labels if libelle != self.libelle]
        reste = (1 - self.score) / len(autres)
        return {"labels": [self.libelle, *autres], "scores": [self.score] + [reste] * len(autres)}


@pytest.fixture
def faux_classifieur(monkeypatch):
    def installer(**kwargs):
        faux = FauxClassifieur(**kwargs)
        monkeypatch.setattr(emotion, "_classifieur", lambda: faux)
        return faux

    return installer


def test_renvoie_l_emotion_et_le_score(faux_classifieur):
    faux_classifieur(libelle="fear", score=0.87654)

    resultat = classer_emotion("Un homme me poursuivait dans un couloir sombre.")

    assert resultat == (Reve.Emotion.EFFRAYANT, 0.8765)


def test_utilise_les_libelles_et_l_hypothese_en_anglais(faux_classifieur):
    faux = faux_classifieur()

    classer_emotion("Je volais au-dessus de la ville.")

    assert faux.appels[0]["libelles"] == list(emotion.LIBELLES)
    assert faux.appels[0]["gabarit"] == "The emotion in this text is {}."


def test_chaque_emotion_du_modele_a_un_libelle():
    assert set(emotion.LIBELLES.values()) == set(Reve.Emotion.values)


def test_texte_vide_est_neutre_sans_appeler_le_modele(faux_classifieur):
    faux = faux_classifieur()

    assert classer_emotion("   ") == (Reve.Emotion.NEUTRE, 0.0)
    assert faux.appels == []


def test_erreur_du_modele(monkeypatch):
    def classifieur_en_panne():
        raise OSError("modèle introuvable")

    monkeypatch.setattr(emotion, "_classifieur", classifieur_en_panne)

    with pytest.raises(ErreurClassification):
        classer_emotion("Un rêve.")


def test_commande_d_evaluation(faux_classifieur, capsys):
    faux_classifieur(libelle="neutral")  # répond toujours « neutre »

    call_command("evaluer_emotions")

    assert "Précision : 2/12" in capsys.readouterr().out
