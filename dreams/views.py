"""Vues des rêves : création, consultation et suivi du traitement."""

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from accounts.decorators import consentement_requis

from .forms import ReveForm
from .models import Reve
from .services.pipeline import demarrer_traitement


@consentement_requis
def nouveau_reve(request):
    """Affiche l'enregistreur, crée le rêve et lance son traitement.

    Args:
        request: Requête HTTP reçue.

    Returns:
        HttpResponse: Le formulaire, ou une redirection vers le rêve créé.
    """
    form = ReveForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        reve = form.save(commit=False)
        reve.utilisateur = request.user
        reve.save()
        demarrer_traitement(reve)
        messages.success(request, "Votre rêve a bien été enregistré : son analyse commence.")
        return redirect("detail_reve", pk=reve.pk)
    return render(request, "dreams/nouveau.html", {"form": form})


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
    """Renvoie le statut du traitement, interrogé régulièrement par la page du rêve.

    Args:
        request: Requête HTTP reçue.
        pk: Identifiant du rêve.

    Returns:
        JsonResponse: ``{"statut": "en_cours" | "termine" | "erreur"}``.
    """
    reve = get_object_or_404(Reve, pk=pk, utilisateur=request.user)
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
    if not reve.audio:
        messages.error(
            request, "L'enregistrement n'est plus disponible : racontez à nouveau votre rêve."
        )
        return redirect("nouveau_reve")

    reve.statut = Reve.Statut.EN_COURS
    reve.message_erreur = ""
    reve.save(update_fields=["statut", "message_erreur"])
    demarrer_traitement(reve)
    return redirect("detail_reve", pk=reve.pk)
