# Dreamcatcher


Dreamcatcher réimagine les rêves de l’utilisateur sous forme d’image ou de vidéo.

Dreamcatcher demande à l’utilisateur de raconter son rêve à voix haute, identifie son émotion et renvoie une image ou courte vidéo représentant son récit. L’utilisateur aura également accès à ses précédents « rêves » dans un tableau de bord et suivre l’évolution de ses émotions à travers ces derniers.


## Fonctionnalités

- Comptes utilisateurs + consentement RGPD
- Enregistrement au micro/import d'un fichier audio
- Transcription et détection de l'émotion
- Illustration par image ou vidéo a partir d'une description anonymisée
- Historique des rêves, option de suppression du compte avec toutes ses données
- Quotas et budget mensuel des API parametrables

## Prérequis

- Python >=3.12
- Docker Desktop (https://www.docker.com/products/docker-desktop/) /!\ doit être lancé au préalable
- Clés API :
    - Mistral (https://console.mistral.ai)
    - Black Forest Labs (https://bfl.ai)
    - Google AI Studio (https://aistudio.google.com)

## Installation et déploiement

Dans un terminal: 

```bash
git clone https://github.com/LBnst/dreamcatcher.git
cd dreamcatcher
python installer.py
```

Appuyez sur Entrée pour choisir le mode "production" (mis par défaut). 

Le script :

1. crée le fichier ".env.prod" avec clé secrete + mot de passe de base générés puis vous demande vos clés d'API
2. construit l'image et lance l'application avec Docker Compose : serveur gunicorn, DEBUG=False, base de données
 et médias conservés dans des volumes,
3. affiche la commande pour créer le compte administrateur

L'application est ensuite disponible sur **http://localhost:8000**

Le panel administration est sur **http://localhost:8000/admin**

Au premier rêve, le modèle d'émotion est téléchargé une seule fois (environ 560 Mo)

Ce premier traitement prend 1/2 min (normal!)

## Utilisation

Toutes les commandes s'appliquent à la production :

- Créer un administrateur : `docker compose -f docker-compose.prod.yml --env-file .env.prod exec web python manage.py createsuperuser` 
- Suivre les journaux : `docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f web` 
- Arrêter : `docker compose -f docker-compose.prod.yml --env-file .env.prod down` 
- Relancer ou mettre à jour : `docker compose -f docker-compose.prod.yml --env-file .env.prod up -d --build` 

Arrêter l'application conserve les données. 

/!\ Ne pas ajouter l'option `-v` à `down` (efface les données)

## Configuration

Tout se règle dans `.env.prod` (production) ou `.env` (développement), sans modifier le code.

Relancer l'application après une modification

Variables a modifier :

- `SECRET_KEY` : Clé secrète Django (générée par le script)
- `POSTGRES_PASSWORD` : Mot de passe de la base (généré par le script)
- `MISTRAL_API_KEY`, `BFL_API_KEY`, `GEMINI_API_KEY` : Clés API des IA
- `BUDGET_MENSUEL_EUR` : Plafond reglable
- `QUOTA_REVES_PAR_JOUR`, `QUOTA_VIDEOS_PAR_JOUR` : Quotas reglables

## Développement

Le script propose aussi deux modes de développement : avec Docker (serveur de
développement, rechargement automatique du code), ou dans un environnement virtuel
Python. 

Lancez `python installer.py` et choisissez `d` ou `v`.

Tests et qualité, depuis l'environnement virtuel :

```bash
docker compose up -d db     #base de test postgresql
pytest --cov    #tests de couverture
ruff check .    #test de compatibilité avec les styles pep8 + docstrings google 
```

/!\ Les call API sont simulés lors des tests

## Intégration et livraison continues

À chaque pull request GitHub Actions vérifie le style, les tests, les migrations et la construction de l'image. 

La branche main est protégée, une PR ne peut être fusionnée que si tous ces contrôles sont validés. 

Après chaque fusion l'image est publiée sur `ghcr.io/lbnst/dreamcatcher:latest`

## Crédits

Lucien Benoist