"""Modèle utilisateur de Dreamcatcher : connexion par e-mail."""

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UtilisateurManager(BaseUserManager):
    """Crée des utilisateurs identifiés par leur e-mail (sans nom d'utilisateur)."""

    use_in_migrations = True

    def _creer(self, email, password, **champs):
        """Crée et enregistre un utilisateur.

        Args:
            email: Adresse e-mail, utilisée comme identifiant.
            password: Mot de passe en clair, haché avant enregistrement.
            **champs: Autres champs du modèle.

        Returns:
            Utilisateur: L'utilisateur créé.

        Raises:
            ValueError: Si l'e-mail est vide.
        """
        if not email:
            raise ValueError("L'adresse e-mail est obligatoire.")
        utilisateur = self.model(email=self.normalize_email(email), **champs)
        utilisateur.set_password(password)
        utilisateur.save(using=self._db)
        return utilisateur

    def create_user(self, email, password=None, **champs):
        """Crée un utilisateur standard.

        Args:
            email: Adresse e-mail.
            password: Mot de passe en clair.
            **champs: Autres champs du modèle.

        Returns:
            Utilisateur: L'utilisateur créé.
        """
        champs.setdefault("is_staff", False)
        champs.setdefault("is_superuser", False)
        return self._creer(email, password, **champs)

    def create_superuser(self, email, password=None, **champs):
        """Crée un administrateur ayant accès à l'administration Django.

        Args:
            email: Adresse e-mail.
            password: Mot de passe en clair.
            **champs: Autres champs du modèle.

        Returns:
            Utilisateur: L'administrateur créé.
        """
        champs.setdefault("is_staff", True)
        champs.setdefault("is_superuser", True)
        return self._creer(email, password, **champs)


class Utilisateur(AbstractUser):
    """Utilisateur de l'application, identifié par son adresse e-mail.

    Attributes:
        email: Adresse de connexion, unique.
        consentement_le: Date d'acceptation de la politique de confidentialité,
            vide tant que l'utilisateur n'a pas consenti (preuve RGPD).
    """

    username = None
    first_name = None
    last_name = None
    email = models.EmailField("adresse e-mail", unique=True)
    consentement_le = models.DateTimeField("consentement donné le", null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UtilisateurManager()

    class Meta:
        verbose_name = "utilisateur"
        verbose_name_plural = "utilisateurs"

    def __str__(self):
        return self.email

    @property
    def a_consenti(self):
        """bool: Vrai si l'utilisateur a accepté la politique de confidentialité."""
        return self.consentement_le is not None
