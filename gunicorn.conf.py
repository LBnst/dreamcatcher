"""Configuration de gunicorn, le serveur web de production.

Un seul processus (worker) pour ne charger qu'une seule fois le modèle d'émotion
(environ 1 Go de mémoire), et plusieurs threads pour servir plusieurs
utilisateurs en parallèle.
"""

bind = "0.0.0.0:8000"
workers = 1
threads = 8
worker_class = "gthread"

# timeout pour les requetes de suivi video google
timeout = 120

# journaux console
accesslog = "-"
errorlog = "-"
