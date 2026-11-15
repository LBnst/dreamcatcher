"""Commande ``evaluer_emotions`` : mesure la fiabilité du modèle sur des rêves annotés."""

from django.core.management.base import BaseCommand

from dreams.services.emotion import classer_emotion

# exemples de rêves en outil de comparaison
REVES_ANNOTES = [
    ("Je retrouvais mes amis sur une plage ensoleillée, on riait et on dansait.", "heureux"),
    ("Je gagnais un concours et toute ma famille me félicitait.", "heureux"),
    ("Mon grand-père, disparu l'an dernier, me disait adieu sur un quai de gare.", "triste"),
    ("Je cherchais mon chien partout, mais il était parti pour toujours.", "triste"),
    ("J'arrivais en retard à mon examen et je n'avais rien révisé.", "stressant"),
    (
        "Mon patron exigeait le dossier immédiatement et mon téléphone sonnait sans arrêt.",
        "stressant",
    ),
    ("Un homme sans visage me poursuivait dans un couloir sombre.", "effrayant"),
    ("Des araignées géantes sortaient des murs de ma chambre.", "effrayant"),
    ("Je faisais mes courses au supermarché, puis je rentrais chez moi.", "neutre"),
    ("Je prenais le bus pour aller au travail, comme tous les matins.", "neutre"),
    ("Mon frère avait cassé ma voiture et je lui hurlais dessus.", "colere"),
    ("Mon voisin faisait du bruit toute la nuit et je tapais du poing sur sa porte.", "colere"),
]


class Command(BaseCommand):
    """Compare l'émotion prédite à l'émotion attendue sur un petit jeu de rêves."""

    help = "Évalue la classification émotionnelle sur un jeu de rêves annotés."

    def handle(self, *args, **options):
        """Affiche chaque prédiction, puis le taux de bonnes réponses."""
        corrects = 0
        for texte, attendue in REVES_ANNOTES:
            predite, score = classer_emotion(texte)
            juste = str(predite) == attendue
            corrects += juste
            self.stdout.write(
                f"{'OK' if juste else 'KO'}  attendu={attendue:<10} "
                f"prédit={str(predite):<10} ({score:.2f})  {texte[:45]}"
            )
        total = len(REVES_ANNOTES)
        self.stdout.write(f"\nPrécision : {corrects}/{total} ({corrects / total:.0%})")
