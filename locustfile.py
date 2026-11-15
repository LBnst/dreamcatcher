# tests de charge

import random
import re

from locust import HttpUser, between, task

# Doivent correspondre à la commande creer_donnees_charge.
DOMAINE = "charge.dreamcatcher.test"
MOT_DE_PASSE = "charge-dreamcatcher"
NOMBRE_COMPTES = 20

# Chemins de l'application : vérifie-les dans la barre d'adresse de ton navigateur.
CONNEXION = "/comptes/connexion/"
HISTORIQUE = "/reves/"
TABLEAU_DE_BORD = "/reves/tableau-de-bord/"

LIEN_REVE = re.compile(r'href="(/reves/\d+/)"')
EMOTIONS = ["heureux", "triste", "stressant", "effrayant", "neutre", "colere"]
MOTS_CLES = ["forêt", "mer", "maison", "ville", "examen"]


class Reveur(HttpUser):
    """Utilisateur qui consulte ses rêves, ses filtres et son tableau de bord."""

    wait_time = between(1, 3)

    def on_start(self):
        """Connecte l'utilisateur simulé avec l'un des comptes de test."""
        self.reves = []
        email = f"charge{random.randint(1, NOMBRE_COMPTES)}@{DOMAINE}"
        self.client.get(CONNEXION, name="connexion (page)")
        jeton = self.client.cookies.get("csrftoken", "")
        donnees = {
            "username": email,  # nom du champ dans le formulaire de connexion de Django
            "email": email,
            "password": MOT_DE_PASSE,
            "csrfmiddlewaretoken": jeton,
        }
        with self.client.post(
            CONNEXION, data=donnees, name="connexion (envoi)", catch_response=True
        ) as reponse:
            if CONNEXION in reponse.url:
                reponse.failure("Connexion refusée")

    @task(3)
    def historique(self):
        """Ouvre l'historique et mémorise les liens vers les rêves."""
        reponse = self.client.get(HISTORIQUE, name="historique")
        self.reves = LIEN_REVE.findall(reponse.text) or self.reves

    @task(2)
    def historique_filtre(self):
        """Filtre l'historique par émotion ou par mot-clé."""
        if random.random() < 0.5:
            parametres = {"emotion": random.choice(EMOTIONS)}
        else:
            parametres = {"q": random.choice(MOTS_CLES)}
        self.client.get(HISTORIQUE, params=parametres, name="historique (filtré)")

    @task(2)
    def tableau_de_bord(self):
        """Ouvre le tableau de bord (agrégations en base)."""
        self.client.get(TABLEAU_DE_BORD, name="tableau de bord")

    @task(1)
    def detail(self):
        """Ouvre le détail d'un rêve déjà repéré dans l'historique."""
        if self.reves:
            self.client.get(random.choice(self.reves), name="détail d'un rêve")
