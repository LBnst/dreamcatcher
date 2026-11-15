"""Vues des rêves : création, consultation et suivi du traitement."""

from django.contrib import messages
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from accounts.decorators import consentement_requis

from .forms import ReveForm
from .models import Reve
from .services.pipeline import demarrer_traitement
from .services.quotas import MESSAGE_BUDGET, budget_atteint, message_quota
from .services.video import suivre_video

TAILLE_PAGE_HISTORIQUE = 10


def historique(request):
    """Liste les rêves de l'utilisateur, du plus récent au plus ancien, 10 par page.

    Accessible même sans consentement : chacun doit pouvoir consulter ses
    propres données (droit d'accès RGPD).

    Args:
        request: Requête HTTP reçue.

    Returns:
        HttpResponse: La page de l'historique.
    """
    reves = Reve.objects.filter(utilisateur=request.user)
    page = Paginator(reves, TAILLE_PAGE_HISTORIQUE).get_page(request.GET.get("page"))
    return render(request, "dreams/historique.html", {"page": page})


@consentement_requis
def nouveau_reve(request):
    """Affiche l'enregistreur, crée le rêve et lance son traitement.

    Le rêve est refusé, avec un message clair, si le budget mensuel ou le quota
    quotidien de l'utilisateur est atteint.

    Args:
        request: Requête HTTP reçue.

    Returns:
        HttpResponse: Le formulaire, ou une redirection vers le rêve créé.
    """
    form = ReveForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        refus = _motif_de_refus(request.user, form.cleaned_data["type_media"])
        if refus is None:
            reve = form.save(commit=False)
            reve.utilisateur = request.user
            reve.save()
            demarrer_traitement(reve)
            messages.success(request, "Votre rêve a bien été enregistré : son analyse commence.")
            return redirect("detail_reve", pk=reve.pk)
        form.add_error(None, refus)
    return render(request, "dreams/nouveau.html", {"form": form})


def _motif_de_refus(utilisateur, type_media):
    """Renvoie la raison d'un refus (budget ou quota atteint), ou ``None``.

    Args:
        utilisateur: Utilisateur qui envoie le rêve.
        type_media: Rendu demandé.

    Returns:
        str | None: Le message de refus, ou ``None`` si le rêve peut être créé.
    """
    if budget_atteint():
        return MESSAGE_BUDGET
    return message_quota(utilisateur, type_media)


def detail_reve(request, pk):
    """Affiche un rêve, uniquement à son propriétaire.

    Args:
        request: Requête HTTP reçue.
        pk: Identifiant du rêve.

    Returns:
        HttpResponse: La fiche du rêve (erreur 404 si le rêve appartient à un autre utilisateur).
    """
    reve = get_object_or_404(Reve, pk=pk, utilisateur=request.user)
    return render(request, "dreams/detail.html", {"reve": reve})


@require_GET
def statut_reve(request, pk):
    """Renvoie le statut du traitement, interrogé toutes les 5 s par la page du rêve.

    Pour une vidéo en cours de génération, c'est aussi l'occasion de demander
    son avancement à Google.

    Args:
        request: Requête HTTP reçue.
        pk: Identifiant du rêve.

    Returns:
        JsonResponse: ``{"statut": "en_cours" | "termine" | "erreur"}``.
    """
    reve = get_object_or_404(Reve, pk=pk, utilisateur=request.user)
    if reve.statut == Reve.Statut.EN_COURS and reve.id_tache_externe:
        reve = suivre_video(reve.pk)
    return JsonResponse({"statut": reve.statut})


@require_POST
@consentement_requis
def reessayer_reve(request, pk):
    """Relance le traitement d'un rêve en erreur, si son audio est encore disponible.

    Args:
        request: Requête HTTP reçue.
        pk: Identifiant du rêve.

    Returns:
        HttpResponse: Redirection vers le rêve, ou vers un nouvel enregistrement.
    """
    reve = get_object_or_404(Reve, pk=pk, utilisateur=request.user)
    if reve.statut != Reve.Statut.ERREUR:
        return redirect("detail_reve", pk=reve.pk)
    if not reve.audio and not reve.transcription:
        messages.error(
            request, "L'enregistrement n'est plus disponible : racontez à nouveau votre rêve."
        )
        return redirect("nouveau_reve")

    reve.statut = Reve.Statut.EN_COURS
    reve.message_erreur = ""
    reve.save(update_fields=["statut", "message_erreur"])
    demarrer_traitement(reve)
    return redirect("detail_reve", pk=reve.pk)
