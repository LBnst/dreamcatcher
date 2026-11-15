"""Formulaires d'inscription et de connexion."""

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import Utilisateur


class BootstrapMixin:
    """Ajoute la classe CSS Bootstrap ``form-control`` à tous les champs."""

    def __init__(self, *args, **kwargs):
        """Initialise le formulaire puis applique le style Bootstrap.

        Args:
            *args: Arguments positionnels du formulaire Django.
            **kwargs: Arguments nommés du formulaire Django.
        """
        super().__init__(*args, **kwargs)
        for champ in self.fields.values():
            champ.widget.attrs.setdefault("class", "form-control")


class InscriptionForm(BootstrapMixin, UserCreationForm):
    """Création d'un compte avec e-mail et mot de passe (saisi deux fois)."""

    class Meta:
        model = Utilisateur
        fields = ["email"]

    def clean_email(self):
        """Refuse un e-mail déjà utilisé, sans tenir compte des majuscules.

        Returns:
            str: L'e-mail saisi.

        Raises:
            forms.ValidationError: Si un compte utilise déjà cet e-mail.
        """
        email = self.cleaned_data["email"]
        if Utilisateur.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Un compte existe déjà avec cette adresse e-mail.")
        return email


class ConnexionForm(BootstrapMixin, AuthenticationForm):
    """Connexion par e-mail et mot de passe."""


class SuppressionCompteForm(forms.Form):
    """Confirmation de la suppression du compte par le mot de passe."""

    mot_de_passe = forms.CharField(
        label="Confirmez avec votre mot de passe",
        widget=forms.PasswordInput(
            attrs={"class": "form-control", "autocomplete": "current-password"}
        ),
    )

    def __init__(self, utilisateur, *args, **kwargs):
        """Initialise le formulaire pour un utilisateur donné.

        Args:
            utilisateur: Utilisateur qui demande la suppression de son compte.
            *args: Arguments positionnels du formulaire Django.
            **kwargs: Arguments nommés du formulaire Django.
        """
        super().__init__(*args, **kwargs)
        self.utilisateur = utilisateur

    def clean_mot_de_passe(self):
        """Vérifie le mot de passe saisi.

        Returns:
            str: Le mot de passe, s'il est correct.

        Raises:
            forms.ValidationError: Si le mot de passe est incorrect.
        """
        mot_de_passe = self.cleaned_data["mot_de_passe"]
        if not self.utilisateur.check_password(mot_de_passe):
            raise forms.ValidationError("Mot de passe incorrect.")
        return mot_de_passe
