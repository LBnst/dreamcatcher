"""Crée ou supprime des comptes et des rêves fictifs pour les tests de charge."""

import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from dreams.models import Reve

DOMAINE = "charge.dreamcatcher.test"
MOT_DE_PASSE = "charge-dreamcatcher"
RECITS = [
    "Je marchais dans une forêt immense et les arbres me parlaient.",
    "Je nageais dans une mer chaude au milieu de poissons lumineux.",
    "J'étais en retard à un examen et je ne trouvais pas la salle.",
    "Une maison inconnue dont les couloirs ne finissaient jamais.",
    "Je volais au-dessus de ma ville au coucher du soleil.",
    "Quelqu'un me poursuivait dans un parking souterrain.",
]


class Command(BaseCommand):
    """Prépare (ou nettoie) le jeu de données du test de charge, sans appel d'API."""

    help = "Crée des comptes charge<N>@charge.dreamcatcher.test avec des rêves fictifs."

    def add_arguments(self, parser):
        """Déclare les options de la commande.

        Args:
            parser: Analyseur d'arguments de la commande.
        """
        parser.add_argument("--comptes", type=int, default=20)
        parser.add_argument("--reves", type=int, default=30, help="Rêves par compte.")
        parser.add_argument("--supprimer", action="store_true", help="Supprime ces comptes.")

    def handle(self, *args, **options):
        """Crée les comptes manquants et leurs rêves, ou les supprime.

        Args:
            *args: Arguments positionnels (inutilisés).
            **options: Options de la ligne de commande.
        """
        utilisateurs = get_user_model().objects
        if options["supprimer"]:
            nombre, _ = utilisateurs.filter(email__endswith=f"@{DOMAINE}").delete()
            self.stdout.write(f"{nombre} objets supprimés.")
            return

        aleatoire = random.Random(42)  # données identiques d'un lancement à l'autre
        aujourdhui = timezone.localdate()
        emotions = [valeur for valeur, _ in Reve.Emotion.choices]
        crees = 0
        for numero in range(1, options["comptes"] + 1):
            email = f"charge{numero}@{DOMAINE}"
            if utilisateurs.filter(email=email).exists():
                continue
            utilisateur = utilisateurs.create_user(email=email, password=MOT_DE_PASSE)
            Reve.objects.bulk_create(
                Reve(
                    utilisateur=utilisateur,
                    date_reve=aujourdhui - timedelta(days=aleatoire.randint(0, 180)),
                    transcription=aleatoire.choice(RECITS),
                    emotion=aleatoire.choice(emotions),
                    score_emotion=round(aleatoire.uniform(0.4, 0.95), 2),
                    statut=Reve.Statut.TERMINE,
                )
                for _ in range(options["reves"])
            )
            crees += 1
        self.stdout.write(f"{crees} comptes créés (mot de passe : {MOT_DE_PASSE}).")
