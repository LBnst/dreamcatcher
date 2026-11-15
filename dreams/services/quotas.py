"""Garde-fous financiers : quota quotidien par utilisateur et budget mensuel global.

Le budget est calculé à partir des coûts réels enregistrés dans ``AppelApi`` ;
il est vérifié avant chaque appel payant, et dès l'envoi d'un nouveau rêve.
"""

from decimal import Decimal

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone

from dreams.models import AppelApi, Reve

MESSAGE_BUDGET = (
    "Le service a atteint son budget mensuel : "
    "les nouveaux rêves pourront de nouveau être analysés le mois prochain."
)


class BudgetEpuise(Exception):
    """Le budget mensuel des API est atteint : plus aucun appel payant ce mois-ci."""


def depense_du_mois():
    """Calcule le total des coûts API depuis le début du mois en cours.

    Returns:
        Decimal: Dépense du mois, en euros.
    """
    debut_du_mois = timezone.localtime().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    total = AppelApi.objects.filter(date_appel__gte=debut_du_mois).aggregate(total=Sum("cout_eur"))[
        "total"
    ]
    return total or Decimal("0")


def budget_atteint():
    """Indique si le budget mensuel est consommé.

    Returns:
        bool: Vrai si la dépense du mois atteint ou dépasse le budget.
    """
    return depense_du_mois() >= Decimal(str(settings.BUDGET_MENSUEL_EUR))


def verifier_budget():
    """Bloque un appel payant si le budget mensuel est atteint.

    Raises:
        BudgetEpuise: Si le budget du mois est consommé.
    """
    if budget_atteint():
        raise BudgetEpuise(MESSAGE_BUDGET)


def message_quota(utilisateur, type_media):
    """Vérifie le quota quotidien d'un utilisateur avant la création d'un rêve.

    Args:
        utilisateur: Utilisateur qui envoie un nouveau rêve.
        type_media: Rendu demandé (``Reve.TypeMedia``).

    Returns:
        str | None: Le message à afficher si le quota est atteint, sinon ``None``.
    """
    debut_du_jour = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    reves_du_jour = Reve.objects.filter(utilisateur=utilisateur, date_creation__gte=debut_du_jour)

    if reves_du_jour.count() >= settings.QUOTA_REVES_PAR_JOUR:
        return (
            f"Vous avez atteint la limite de {settings.QUOTA_REVES_PAR_JOUR} rêves par jour. "
            "À demain !"
        )
    videos_du_jour = reves_du_jour.filter(type_media=Reve.TypeMedia.VIDEO).count()
    if type_media == Reve.TypeMedia.VIDEO and videos_du_jour >= settings.QUOTA_VIDEOS_PAR_JOUR:
        return (
            f"Vous avez atteint la limite de {settings.QUOTA_VIDEOS_PAR_JOUR} vidéos par jour : "
            "choisissez une image pour ce rêve."
        )
    return None
