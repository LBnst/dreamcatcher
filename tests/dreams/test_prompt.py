from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from dreams.models import AppelApi, Reve
from dreams.services.prompt import SCENES_GENERIQUES, ecrire_prompt_visuel
from dreams.services.quotas import BudgetEpuise
from tests.outils import reponse_http

pytestmark = pytest.mark.django_db

TRANSCRIPTION = "Mon amie et moi marchions dans la ville sous la neige."


@pytest.fixture(autouse=True)
def configuration(settings):
    settings.MISTRAL_API_KEY = "cle-de-test"
    settings.MISTRAL_MODELE_PROMPT = "mistral-test"
    settings.PRIX_PROMPT_USD_MILLION_ENTREE = 0.15
    settings.PRIX_PROMPT_USD_MILLION_SORTIE = 0.60
    settings.TAUX_USD_EUR = 1.0


@pytest.fixture
def reve():
    utilisateur = get_user_model().objects.create_user(email="nom@exemple.fr", password="x")
    return Reve.objects.create(
        utilisateur=utilisateur, transcription=TRANSCRIPTION, emotion=Reve.Emotion.HEUREUX
    )


def reponse_mistral(contenu, entree=400, sortie=100):
    return reponse_http(
        200,
        {
            "choices": [{"message": {"content": contenu}}],
            "usage": {"prompt_tokens": entree, "completion_tokens": sortie},
        },
    )


# --- Réécriture réussie ----------------------------------------------------


def test_renvoie_la_description_visuelle(reve, faux_http):
    faux_http(reponse_mistral("  Two figures walk through a snowy city at dusk.  "))

    assert ecrire_prompt_visuel(reve) == "Two figures walk through a snowy city at dusk."


def test_envoie_la_consigne_d_anonymisation_et_le_recit(reve, faux_http):
    faux = faux_http(reponse_mistral("A scene."))

    ecrire_prompt_visuel(reve)

    envoi = faux.appels[0]
    consigne, recit = envoi["json"]["messages"]
    assert envoi["json"]["model"] == "mistral-test"
    assert "Never include names" in consigne["content"]
    assert TRANSCRIPTION in recit["content"]
    assert envoi["timeout"] == 20


def test_trace_l_appel_avec_son_cout(reve, faux_http):
    faux_http(reponse_mistral("A scene.", entree=400, sortie=100))

    ecrire_prompt_visuel(reve)

    appel = AppelApi.objects.get()
    assert appel.service == AppelApi.Service.PROMPT
    assert appel.statut == AppelApi.Statut.SUCCES
    assert appel.cout_eur == Decimal("0.0001")  # 400 x 0,15 + 100 x 0,60 par million


def test_accepte_une_reponse_en_blocs(reve, faux_http):
    blocs = [{"type": "thinking", "thinking": "..."}, {"type": "text", "text": "A quiet lake."}]
    faux_http(reponse_mistral(blocs))

    assert ecrire_prompt_visuel(reve) == "A quiet lake."


# --- Repli sur une scène générique (le récit ne part jamais) ---------------


def test_echec_de_l_api_donne_une_scene_generique_sans_le_recit(reve, faux_http):
    faux_http(reponse_http(401))

    prompt = ecrire_prompt_visuel(reve)

    assert prompt == SCENES_GENERIQUES["heureux"]
    assert "Clara" not in prompt  # la transcription brute ne part jamais


def test_reponse_mal_formee_donne_une_scene_generique(reve, faux_http):
    faux_http(reponse_http(200, {"choices": []}))

    assert ecrire_prompt_visuel(reve) == SCENES_GENERIQUES["heureux"]


def test_sans_cle_api_scene_generique_sans_appel(reve, faux_http, settings):
    settings.MISTRAL_API_KEY = ""
    faux = faux_http()

    assert ecrire_prompt_visuel(reve) == SCENES_GENERIQUES["heureux"]
    assert faux.appels == []


def test_emotion_inconnue_donne_une_scene_neutre(reve, faux_http, settings):
    settings.MISTRAL_API_KEY = ""
    reve.emotion = ""
    faux_http()

    assert ecrire_prompt_visuel(reve) == SCENES_GENERIQUES["neutre"]


# --- Garde-fou budgétaire --------------------------------------------------


def test_budget_epuise(reve, faux_http, settings):
    settings.BUDGET_MENSUEL_EUR = 0
    faux_http()

    with pytest.raises(BudgetEpuise):
        ecrire_prompt_visuel(reve)
