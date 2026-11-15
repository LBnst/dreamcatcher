"""Vues des comptes : inscription, connexion et consentement RGPD."""

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_not_required
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods

from .forms import ConnexionForm, InscriptionForm


@login_not_required
def inscription(request):
    """Affiche le formulaire d'inscription et connecte l'utilisateur créé.

    Args:
        request: Requête HTTP reçue.

    Returns:
        HttpResponse: Le formulaire, ou une redirection vers l'accueil après inscription.
    """
    if request.user.is_authenticated:
        return redirect("accueil")

    form = InscriptionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        utilisateur = form.save()
        login(request, utilisateur)
        return redirect("accueil")
    return render(request, "accounts/inscription.html", {"form": form})


class ConnexionView(LoginView):
    """Page de connexion par e-mail ; un utilisateur déjà connecté est redirigé."""

    form_class = ConnexionForm
    template_name = "accounts/connexion.html"
    redirect_authenticated_user = True


def _url_de_retour(request):
    """Renvoie l'adresse ``next`` si elle pointe vers ce site, sinon l'accueil.

    Empêche une redirection vers un site externe malveillant (open redirect).

    Args:
        request: Requête HTTP reçue.

    Returns:
        str: URL ou nom de route vers laquelle rediriger.
    """
    suivant = request.POST.get("next") or request.GET.get("next")
    if suivant and url_has_allowed_host_and_scheme(
        suivant, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return suivant
    return "accueil"


@require_http_methods(["GET", "POST"])
def consentement(request):
    """Affiche l'écran de consentement et enregistre le choix de l'utilisateur.

    Trois actions possibles : accepter (date enregistrée), refuser (aucune
    captation possible) ou retirer un consentement déjà donné.

    Args:
        request: Requête HTTP reçue.

    Returns:
        HttpResponse: L'écran de consentement ou une redirection.
    """
    utilisateur = request.user

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "accepter":
            utilisateur.consentement_le = timezone.now()
            utilisateur.save(update_fields=["consentement_le"])
            messages.success(request, "Merci, votre consentement a bien été enregistré.")
            return redirect(_url_de_retour(request))
        if action == "retirer":
            utilisateur.consentement_le = None
            utilisateur.save(update_fields=["consentement_le"])
            messages.info(request, "Votre consentement a été retiré.")
        else:
            messages.info(
                request,
                "Vous avez refusé : vous ne pourrez pas enregistrer de rêve. "
                "Vous pouvez changer d'avis à tout moment.",
            )
        return redirect("accueil")

    return render(request, "accounts/consentement.html", {"next": request.GET.get("next", "")})
