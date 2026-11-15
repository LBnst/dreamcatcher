"""Signaux des rêves : effacement des fichiers associés (RGPD)."""

from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Reve


@receiver(post_delete, sender=Reve)
def effacer_fichiers_du_reve(sender, instance, **kwargs):
    """Efface du disque l'audio et le média d'un rêve supprimé.

    Django supprime la ligne en base mais laisse les fichiers sur le disque :
    ce signal les efface, quelle que soit l'origine de la suppression (compte
    supprimé, rêve supprimé, administration). L'effacement attend la validation
    de la transaction, pour ne rien perdre si la suppression est annulée.

    Args:
        sender: Classe du modèle (``Reve``).
        instance: Rêve supprimé.
        **kwargs: Arguments transmis par Django.
    """
    fichiers = [(champ.storage, champ.name) for champ in (instance.audio, instance.media) if champ]
    if not fichiers:
        return

    def effacer():
        """Supprime les fichiers une fois la suppression validée en base."""
        for stockage, nom in fichiers:
            stockage.delete(nom)

    transaction.on_commit(effacer)
