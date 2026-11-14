"""Administration des utilisateurs."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Utilisateur


@admin.register(Utilisateur)
class UtilisateurAdmin(UserAdmin):
    """Administration adaptée à un utilisateur sans nom d'utilisateur."""

    ordering = ["email"]
    list_display = ["email", "date_joined", "consentement_le", "is_staff"]
    search_fields = ["email"]
    readonly_fields = ["date_joined", "last_login"]
    fieldsets = [
        (None, {"fields": ["email", "password"]}),
        ("RGPD", {"fields": ["consentement_le"]}),
        ("Permissions", {"fields": ["is_active", "is_staff", "is_superuser", "groups"]}),
        ("Dates", {"fields": ["date_joined", "last_login"]}),
    ]
    add_fieldsets = [
        (None, {"classes": ["wide"], "fields": ["email", "password1", "password2"]}),
    ]
