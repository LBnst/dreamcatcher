"""Script d'installation de Dreamcatcher.

Trois modes au choix :
- production : déploiement local (gunicorn, DEBUG=False, volumes persistants) ;
- développement avec Docker : serveur de développement et base PostgreSQL ;
- développement en environnement virtuel Python.

Le script prépare le fichier de configuration (.env ou .env.prod) avec des secrets
générés et les clés d'API saisies, puis installe et lance le projet.
N'utilise que la bibliothèque standard : rien à installer avant de le lancer.

Usage :
    python installer.py
"""

import secrets
import shutil
import subprocess
import sys
import venv
from getpass import getpass
from pathlib import Path

RACINE = Path(__file__).resolve().parent
COMPOSE_PROD = ["docker", "compose", "-f", "docker-compose.prod.yml", "--env-file", ".env.prod"]
CLES_API = {
    "MISTRAL_API_KEY": "Clé Mistral (transcription)",
    "BFL_API_KEY": "Clé Black Forest Labs (image)",
    "GEMINI_API_KEY": "Clé Google Gemini (vidéo)",
}


def preparer_configuration(fichier, modele, valeurs):
    """Crée un fichier de configuration à partir de son modèle, sans jamais l'écraser.

    Args:
        fichier: Fichier à créer (``.env`` ou ``.env.prod``).
        modele: Fichier d'exemple qui sert de base.
        valeurs: Valeurs générées à placer dans le fichier (secrets...).
    """
    if fichier.exists():
        print(f"Le fichier {fichier.name} existe déjà : il est conservé tel quel.")
        return

    print("Saisissez vos clés d'API (saisie masquée ; laissez vide pour plus tard).")
    for nom, description in CLES_API.items():
        valeurs[nom] = getpass(f"  {description} : ").strip()

    lignes = []
    for ligne in modele.read_text(encoding="utf-8").splitlines():
        nom = ligne.split("=", 1)[0].strip()
        if valeurs.get(nom):
            ligne = f"{nom}={valeurs.pop(nom)}"
        lignes.append(ligne)
    # Valeurs absentes du modèle : ajoutées à la fin.
    lignes += [f"{nom}={valeur}" for nom, valeur in valeurs.items() if valeur]

    fichier.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    print(f"Fichier {fichier.name} créé.")


def secret(longueur=50):
    """Génère un secret aléatoire, sans caractère spécial gênant dans un fichier .env.

    Args:
        longueur: Nombre d'octets aléatoires.

    Returns:
        str: Le secret (lettres, chiffres, - et _).
    """
    return secrets.token_urlsafe(longueur)


def verifier_docker():
    """Arrête le script si Docker n'est pas installé."""
    if shutil.which("docker") is None:
        sys.exit("Docker est introuvable : installez Docker Desktop, puis relancez ce script.")


def installer_production():
    """Prépare .env.prod et lance le déploiement local de production."""
    verifier_docker()
    preparer_configuration(
        RACINE / ".env.prod",
        RACINE / ".env.prod.example",
        {"SECRET_KEY": secret(), "POSTGRES_PASSWORD": secret(24)},
    )
    executer([*COMPOSE_PROD, "up", "-d", "--build"])
    print(
        "\nProduction lancée. Créez votre compte administrateur :\n"
        f"  {' '.join(COMPOSE_PROD)} exec web python manage.py createsuperuser\n"
        "Puis ouvrez http://localhost:8000"
    )


def installer_docker():
    """Prépare .env et lance l'environnement de développement avec Docker Compose."""
    verifier_docker()
    preparer_configuration(
        RACINE / ".env", RACINE / ".env.example", {"SECRET_KEY": secret(), "DEBUG": "True"}
    )
    executer(["docker", "compose", "up", "-d", "--build"])
    print(
        "\nEnvironnement de développement lancé. Créez votre compte administrateur :\n"
        "  docker compose exec web python manage.py createsuperuser\n"
        "Puis ouvrez http://localhost:8000"
    )


def installer_venv():
    """Prépare .env, crée l'environnement virtuel .venv et y installe les dépendances."""
    if sys.version_info < (3, 12):
        sys.exit("Python 3.12 ou plus récent est nécessaire.")
    preparer_configuration(
        RACINE / ".env", RACINE / ".env.example", {"SECRET_KEY": secret(), "DEBUG": "True"}
    )
    dossier = RACINE / ".venv"
    if not dossier.exists():
        print("Création de l'environnement virtuel .venv...")
        venv.create(dossier, with_pip=True)
    sous_dossier = "Scripts" if sys.platform == "win32" else "bin"
    executer(
        [
            str(dossier / sous_dossier / "python"),
            "-m",
            "pip",
            "install",
            "-r",
            "requirements-dev.txt",
        ]
    )

    activation = (
        r".venv\Scripts\Activate.ps1" if sys.platform == "win32" else "source .venv/bin/activate"
    )
    print(
        "\nInstallation terminée. Pour lancer l'application :\n"
        f"  {activation}\n"
        "  docker compose up -d db          (base PostgreSQL)\n"
        "  python manage.py migrate\n"
        "  python manage.py createsuperuser\n"
        "  python manage.py runserver\n"
        "Puis ouvrez http://localhost:8000"
    )


def executer(commande):
    """Lance une commande dans le dossier du projet, et s'arrête proprement si elle échoue.

    Args:
        commande: Commande et arguments, sous forme de liste.
    """
    try:
        subprocess.run(commande, check=True, cwd=RACINE)
    except subprocess.CalledProcessError:
        sys.exit(f"La commande a échoué : {' '.join(commande)}")


MODES = {
    "p": ("Production locale (recommandé pour utiliser l'application)", installer_production),
    "d": ("Développement avec Docker", installer_docker),
    "v": ("Développement en environnement virtuel Python", installer_venv),
}


def main():
    """Demande le mode d'installation, puis l'exécute."""
    print("=== Installation de Dreamcatcher ===\n")
    for touche, (description, _) in MODES.items():
        print(f"  [{touche}] {description}")
    choix = input("\nVotre choix [p/d/v] : ").strip().lower()[:1] or "p"
    if choix not in MODES:
        sys.exit("Choix inconnu : relancez le script et tapez p, d ou v.")
    MODES[choix][1]()


if __name__ == "__main__":
    main()
