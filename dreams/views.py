"""Vues des rêves : création et consultation."""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import consentement_requis

from .forms import ReveForm
from .models import Reve


@consentement_requis
def nouveau_reve(request):
    """Affiche l'enregistreur et crée le rêve à partir du récit audio envoyé.

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
        messages.success(request, "Votre rêve a bien été enregistré.")
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
