"""Modèles des rêves et du suivi des appels aux API externes."""

from django.conf import settings
from django.db import models
from django.utils import timezone


class Reve(models.Model):
    """Rêve raconté par un utilisateur et résultat de son traitement.

    Attributes:
        utilisateur: Propriétaire du rêve ; ses rêves sont supprimés avec son compte.
        date_reve: Nuit du rêve, utilisée pour les filtres par date.
        audio: Récit enregistré, supprimé dès la fin du traitement (RGPD).
        transcription: Texte renvoyé par l'API de transcription, corrigeable.
        emotion: Émotion dominante détectée (filtre par humeur).
        score_emotion: Confiance du modèle de classification, entre 0 et 1.
        type_media: Rendu choisi par l'utilisateur (image ou vidéo).
        media: Fichier de l'image ou de la vidéo générée.
        id_tache_externe: Identifiant de la génération vidéo chez le fournisseur.
        generation_lancee_le: Lancement de la génération vidéo, pour le délai maximal.
        statut: Avancement du traitement.
        message_erreur: Explication affichée à l'utilisateur si le traitement échoue.
        date_creation: Horodatage de création.
        emotion_corrigee: Vrai si l'utilisateur a changé l'émotion détectée.
        valide: Vrai une fois la transcription et l'émotion vérifiées par l'utilisateur ;
            la génération du visuel (payante) n'a lieu qu'après.
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
        A_VALIDER = "a_valider", "À valider"

    ETAPES_TRAITEMENT = ("transcription", "emotion", "validation", "generation")

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
    generation_lancee_le = models.DateTimeField(null=True, blank=True)
    statut = models.CharField(max_length=20, choices=Statut.choices, default=Statut.EN_COURS)
    message_erreur = models.CharField(max_length=255, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    emotion_corrigee = models.BooleanField("émotion corrigée par l'utilisateur", default=False)
    valide = models.BooleanField("validé par l'utilisateur avant génération", default=False)

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

    @property
    def etape_courante(self):
        """Str | None: Étape en cours, ou None si le traitement est terminé ou en erreur."""
        if self.statut == self.Statut.A_VALIDER:
            return "validation"
        if self.statut != self.Statut.EN_COURS:
            return None
        if not self.transcription:
            return "transcription"
        if not self.valide:
            return "emotion"
        return "generation"

    @property
    def etapes(self):
        """list[dict]: Chaque étape avec son libellé et son état (fait, en_cours, a_venir)."""
        courante = self.etape_courante
        index_courant = (
            self.ETAPES_TRAITEMENT.index(courante) if courante else len(self.ETAPES_TRAITEMENT)
        )
        media = "la vidéo" if self.type_media == self.TypeMedia.VIDEO else "l'image"
        libelles = {
            "transcription": "Transcription de votre récit",
            "emotion": "Analyse de l'émotion",
            "validation": "Votre vérification",
            "generation": f"Création de {media}",
        }
        etapes = []
        for index, code in enumerate(self.ETAPES_TRAITEMENT):
            if index < index_courant:
                etat = "fait"
            elif index == index_courant:
                etat = "en_cours"
            else:
                etat = "a_venir"
            etapes.append({"code": code, "libelle": libelles[code], "etat": etat})
        return etapes

    @property
    def pourcentage_progression(self):
        """int: Avancement estimé, l'étape en cours comptant pour moitié."""
        courante = self.etape_courante
        if courante is None:
            return 100
        index, nombre = self.ETAPES_TRAITEMENT.index(courante), len(self.ETAPES_TRAITEMENT)
        return (2 * index + 1) * 100 // (2 * nombre)


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
        PROMPT = "prompt", "Réécriture du prompt"

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
