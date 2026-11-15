"""Modèles des rêves et du suivi des appels aux API externes."""

from django.conf import settings
from django.db import models
from django.utils import timezone


class Reve(models.Model):
    """Rêve raconté par un utilisateur et résultat de son traitement.

    Attributes:
        utilisateur: Propriétaire du rêve ; ses rêves sont supprimés avec son compte.
        date_reve: Nuit du rêve, utilisée pour les filtres par date.
        audio: Récit enregistré, supprimé dès la fin du traitement (RGPD)
        transcription: Texte renvoyé par l'API de transcription.
        emotion: Émotion dominante détectée (filtre par humeur).
        score_emotion: Confiance du modèle de classification, entre 0 et 1.
        type_media: Rendu choisi par l'utilisateur (image ou vidéo).
        media: Fichier de l'image ou de la vidéo générée.
        id_tache_externe: Identifiant de la génération vidéo chez le fournisseur.
        statut: Avancement du traitement.
        date_creation: Horodatage de création.
    """

    class Emotion(models.TextChoices):
        HEUREUX = "heureux", "Heureux"
        TRISTE = "triste", "Triste"
        STRESSANT = "stressant", "Stressant"
        EFFRAYANT = "effrayant", "Effrayant"
        NEUTRE = "neutre", "Neutre"
        COLERE = "colere", "Colère"

    class TypeMedia(models.TextChoices):
        IMAGE = "image", "Image"
        VIDEO = "video", "Vidéo"

    class Statut(models.TextChoices):
        EN_COURS = "en_cours", "En cours"
        TERMINE = "termine", "Terminé"
        ERREUR = "erreur", "Erreur"

    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reves"
    )
    date_reve = models.DateField("nuit du rêve", default=timezone.localdate)
    audio = models.FileField(upload_to="audio/%Y/%m/", blank=True)
    transcription = models.TextField(blank=True)
    emotion = models.CharField(max_length=20, choices=Emotion.choices, blank=True)
    score_emotion = models.FloatField(null=True, blank=True)
    type_media = models.CharField(max_length=10, choices=TypeMedia.choices, default=TypeMedia.IMAGE)
    media = models.FileField(upload_to="reves/%Y/%m/", blank=True)
    id_tache_externe = models.CharField(max_length=255, blank=True)
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.EN_COURS)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "rêve"
        verbose_name_plural = "rêves"
        ordering = ["-date_reve", "-date_creation"]
        # Accélèrent l'historique et le tableau de bord (filtres date et humeur).
        indexes = [
            models.Index(fields=["utilisateur", "date_reve"]),
            models.Index(fields=["utilisateur", "emotion"]),
        ]

    def __str__(self):
        return f"Rêve du {self.date_reve:%d/%m/%Y} ({self.utilisateur})"


class AppelApi(models.Model):
    """Trace d'un appel à une API externe, pour le suivi du budget et le monitoring.

    Ne contient aucune donnée personnelle : ni récit, ni e-mail.

    Attributes:
        reve: Rêve concerné ; vidé (et non supprimé) si le rêve est effacé,
            pour que le coût reste comptabilisé dans le budget du mois.
        service: API appelée.
        latence_ms: Temps de réponse mesuré, en millisecondes.
        cout_eur: Coût estimé de l'appel, en euros.
        statut: Résultat de l'appel.
        message_erreur: Détail technique de l'erreur éventuelle.
        date_appel: Horodatage de l'appel.
    """

    class Service(models.TextChoices):
        TRANSCRIPTION = "transcription", "Transcription"
        IMAGE = "image", "Image"
        VIDEO = "video", "Vidéo"

    class Statut(models.TextChoices):
        SUCCES = "succes", "Succès"
        TIMEOUT = "timeout", "Timeout"
        QUOTA = "quota", "Quota dépassé"
        ERREUR = "erreur", "Erreur"

    reve = models.ForeignKey(
        Reve, on_delete=models.SET_NULL, null=True, blank=True, related_name="appels_api"
    )
    service = models.CharField(max_length=20, choices=Service.choices)
    latence_ms = models.PositiveIntegerField(null=True, blank=True)
    cout_eur = models.DecimalField(max_digits=8, decimal_places=4, default=0)
    statut = models.CharField(max_length=20, choices=Statut.choices)
    message_erreur = models.CharField(max_length=255, blank=True)
    date_appel = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "appel API"
        verbose_name_plural = "appels API"
        ordering = ["-date_appel"]

    def __str__(self):
        return f"{self.get_service_display()} – {self.get_statut_display()}"
