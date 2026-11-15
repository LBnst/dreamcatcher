from django.apps import AppConfig


class AccountsConfig(AppConfig):
    """Application de gestion des comptes utilisateurs."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"
    verbose_name = "Comptes"
