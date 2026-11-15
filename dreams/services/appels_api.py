"""Outils communs aux appels d'API payantes : nouvelles tentatives et traçabilité.

Chaque tentative échouée est enregistrée dans ``AppelApi`` ; le succès est
enregistré par le service appelant, qui connaît le coût réel de l'appel.
"""

import logging
import time
from decimal import ROUND_HALF_UP, Decimal

import httpx
from django.conf import settings

from dreams.models import AppelApi

logger = logging.getLogger(__name__)

NOUVELLES_TENTATIVES = 2
PAUSE_ENTRE_TENTATIVES = 1  # en secondes, doublée à chaque nouvelle tentative
CODES_TEMPORAIRES = {500, 502, 503, 504}
CODES_QUOTA = {402, 429}  # crédits épuisés ou limite atteinte chez le fournisseur


class ErreurApi(Exception):
    """Échec définitif d'un appel d'API, après les nouvelles tentatives éventuelles.

    Attributes:
        quota: Vrai si le fournisseur a refusé pour quota, crédits ou plafond atteint.
    """

    def __init__(self, message, quota=False):
        """Initialise l'erreur.

        Args:
            message: Détail technique de l'échec.
            quota: Vrai si l'échec vient d'un quota ou de crédits épuisés.
        """
        super().__init__(message)
        self.quota = quota


def requete(methode, url, *, reve, service, timeout, **options):
    """Envoie une requête HTTP, avec 2 nouvelles tentatives en cas de panne passagère.

    Args:
        methode: Méthode HTTP (``"GET"``, ``"POST"``...).
        url: Adresse de l'API.
        reve: Rêve concerné, pour la traçabilité.
        service: Service appelé (``AppelApi.Service``).
        timeout: Délai d'attente maximal de chaque tentative, en secondes.
        **options: Options transmises à ``httpx.request`` (headers, json, files...).

    Returns:
        tuple[httpx.Response, float]: La réponse réussie et l'instant de départ
        de la tentative (``time.monotonic()``), pour mesurer la latence.

    Raises:
        ErreurApi: Si le fournisseur refuse la requête ou reste injoignable.
    """
    for tentative in range(NOUVELLES_TENTATIVES + 1):
        if tentative:
            time.sleep(PAUSE_ENTRE_TENTATIVES * 2 ** (tentative - 1))
        debut = time.monotonic()
        try:
            reponse = httpx.request(methode, url, timeout=timeout, **options)
        except httpx.TimeoutException:
            enregistrer_appel(
                reve,
                service,
                AppelApi.Statut.TIMEOUT,
                debut,
                message=f"Aucune réponse en {timeout} s",
            )
            continue
        except httpx.HTTPError as erreur:
            enregistrer_appel(
                reve,
                service,
                AppelApi.Statut.ERREUR,
                debut,
                message=f"Erreur réseau : {type(erreur).__name__}",
            )
            continue

        if reponse.is_success:
            return reponse, debut
        code = reponse.status_code
        if code in CODES_QUOTA:
            enregistrer_appel(reve, service, AppelApi.Statut.QUOTA, debut, message=f"HTTP {code}")
            raise ErreurApi(f"HTTP {code}", quota=True)
        enregistrer_appel(reve, service, AppelApi.Statut.ERREUR, debut, message=f"HTTP {code}")
        if code not in CODES_TEMPORAIRES:
            # Erreur définitive (clé invalide, requête refusée...) : inutile de réessayer.
            raise ErreurApi(f"HTTP {code}")

    raise ErreurApi("Service injoignable après plusieurs tentatives")


def enregistrer_appel(reve, service, statut, debut, cout=Decimal("0"), message=""):
    """Trace un appel dans ``AppelApi`` et dans les journaux.

    Args:
        reve: Rêve concerné.
        service: Service appelé (``AppelApi.Service``).
        statut: Résultat de l'appel (``AppelApi.Statut``).
        debut: Instant de départ de l'appel (``time.monotonic()``).
        cout: Coût de l'appel en euros.
        message: Détail technique de l'erreur, sans donnée personnelle.
    """
    latence_ms = round((time.monotonic() - debut) * 1000)
    AppelApi.objects.create(
        reve=reve,
        service=service,
        statut=statut,
        latence_ms=latence_ms,
        cout_eur=cout,
        message_erreur=message[:255],
    )
    journaliser = logger.info if statut == AppelApi.Statut.SUCCES else logger.warning
    journaliser("Appel %s : %s (rêve %s, %s ms)", service, statut, reve.pk, latence_ms)


def en_euros(montant_usd):
    """Convertit un montant en dollars en euros, arrondi à 4 décimales.

    Args:
        montant_usd: Montant en dollars (nombre ou ``Decimal``).

    Returns:
        Decimal: Montant en euros.
    """
    montant = Decimal(str(montant_usd)) * Decimal(str(settings.TAUX_USD_EUR))
    return montant.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
