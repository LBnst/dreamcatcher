from django.apps import AppConfig


class DreamsConfig(AppConfig):
    """Application de gestion des rêves et des appels aux API."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "dreams"
    verbose_name = "Rêves"

    def ready(self):
        """Branche les signaux de l'application au démarrage de Django."""
        from . import signals  # noqa: F401
