"""Vues d'authentification : inscription, connexion, déconnexion."""

from django.contrib.auth import login
from django.contrib.auth.decorators import login_not_required
from django.contrib.auth.views import LoginView
from django.shortcuts import redirect, render

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
