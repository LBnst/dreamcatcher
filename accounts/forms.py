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
