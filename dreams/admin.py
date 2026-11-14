"""Administration des rêves et des appels API."""

from django.contrib import admin

from .models import AppelApi, Reve


@admin.register(Reve)
class ReveAdmin(admin.ModelAdmin):
    """Liste des rêves, filtrable par statut, émotion et type de média."""

    list_display = ["id", "utilisateur", "date_reve", "emotion", "type_media", "statut"]
    list_filter = ["statut", "emotion", "type_media"]
    date_hierarchy = "date_reve"


@admin.register(AppelApi)
class AppelApiAdmin(admin.ModelAdmin):
    """Suivi des appels API en lecture seule (latence, coût, erreurs)."""

    list_display = ["date_appel", "service", "statut", "latence_ms", "cout_eur"]
    list_filter = ["service", "statut"]
    date_hierarchy = "date_appel"

    def has_add_permission(self, request):
        """Interdit la création manuelle : seuls les services enregistrent des appels."""
        return False

    def has_change_permission(self, request, obj=None):
        """Interdit la modification, pour garder un historique fiable."""
        return False
