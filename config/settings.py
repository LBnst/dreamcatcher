"""Configuration Django du projet Dreamcatcher.

Toutes les valeurs sensibles ou dépendantes de l'environnement
(clé secrète, base de données, clés d'API, quotas...) sont lues depuis
les variables d'environnement ou le fichier ``.env``.
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "dreams",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Sert les fichiers statiques en production (DEBUG=False), sans serveur dédié.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # Toutes les pages exigent une connexion, sauf celles marquées @login_not_required.
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# bdd par defaut : sqlite -> postgresql des que l'url de la bdd est définie
DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
}

# connexion par email
AUTH_USER_MODEL = "accounts.Utilisateur"
LOGIN_URL = "connexion"
LOGIN_REDIRECT_URL = "accueil"
LOGOUT_REDIRECT_URL = "connexion"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "fr-fr"
TIME_ZONE = "Europe/Paris"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    # CSS et JavaScript compressés, servis par WhiteNoise.
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# journaux (monitoring) : console, lisible dans Docker, sans donnée personnelle
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {"format": "{asctime} {levelname} {name} : {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "simple"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}

# traitement des rêves en arrière-plan (désactivé dans les tests)
TRAITEMENT_EN_ARRIERE_PLAN = env.bool("TRAITEMENT_EN_ARRIERE_PLAN", default=True)

# quotas
QUOTA_REVES_PAR_JOUR = env.int("QUOTA_REVES_PAR_JOUR", default=10)
QUOTA_VIDEOS_PAR_JOUR = env.int("QUOTA_VIDEOS_PAR_JOUR", default=2)
BUDGET_MENSUEL_EUR = env.float("BUDGET_MENSUEL_EUR", default=15.0)


# modeles
MISTRAL_API_KEY = env("MISTRAL_API_KEY", default="")
MISTRAL_MODELE_TRANSCRIPTION = env(
    "MISTRAL_MODELE_TRANSCRIPTION", default="voxtral-mini-transcribe-3-0"
)

MISTRAL_MODELE_PROMPT = env("MISTRAL_MODELE_PROMPT", default="mistral-small-2603")
PRIX_PROMPT_USD_MILLION_ENTREE = env.float("PRIX_PROMPT_USD_MILLION_ENTREE", default=0.15)
PRIX_PROMPT_USD_MILLION_SORTIE = env.float("PRIX_PROMPT_USD_MILLION_SORTIE", default=0.60)

BFL_API_KEY = env("BFL_API_KEY", default="")
BFL_MODELE_IMAGE = env("BFL_MODELE_IMAGE", default="flux-3-image-klein")
PRIX_IMAGE_USD = env.float("PRIX_IMAGE_USD", default=0.009)

GEMINI_API_KEY = env("GEMINI_API_KEY", default="")
GEMINI_MODELE_VIDEO = env("GEMINI_MODELE_VIDEO", default="gemini-omni-1.2-flash")
RESOLUTION_VIDEO = env("RESOLUTION_VIDEO", default="360p")
DUREE_VIDEO_SECONDES = env.int("DUREE_VIDEO_SECONDES", default=8)
PRIX_VIDEO_USD_SECONDE = env.float("PRIX_VIDEO_USD_SECONDE", default=0.023)
DUREE_MAX_VIDEO = env.int("DUREE_MAX_VIDEO", default=180)  # secondes


PRIX_TRANSCRIPTION_USD_MINUTE = env.float("PRIX_TRANSCRIPTION_USD_MINUTE", default=0.0035)
TAUX_USD_EUR = env.float("TAUX_USD_EUR", default=1.0)


# sécurité
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"

# cookies
SESSION_COOKIE_SECURE = env.bool("COOKIES_SECURISES", default=False)
CSRF_COOKIE_SECURE = SESSION_COOKIE_SECURE
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
