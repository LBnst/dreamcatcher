"""Formulaire de création d'un rêve."""

from pathlib import Path

from django import forms
from django.utils import timezone

from .models import Reve

EXTENSIONS_AUDIO = [".wav", ".mp3", ".m4a", ".ogg", ".webm", ".mp4"]
TAILLE_MAX_AUDIO = 20 * 1024 * 1024  # 20 Mo, largement assez pour quelques minutes de récit


class ReveForm(forms.ModelForm):
    """Récit audio (enregistré ou importé), date du rêve et rendu souhaité."""

    class Meta:
        model = Reve
        fields = ["audio", "date_reve", "type_media"]
        labels = {
            "audio": "… ou importez un fichier audio",
            "date_reve": "Nuit du rêve",
            "type_media": "Rendu souhaité",
        }
        widgets = {
            "audio": forms.FileInput(
                attrs={"accept": ",".join(EXTENSIONS_AUDIO), "class": "form-control"}
            ),
            "date_reve": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}, format="%Y-%m-%d"
            ),
            "type_media": forms.RadioSelect(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        """Rend le récit audio obligatoire.

        Args:
            *args: Arguments positionnels du formulaire Django.
            **kwargs: Arguments nommés du formulaire Django.
        """
        super().__init__(*args, **kwargs)
        self.fields["audio"].required = True

    def clean_audio(self):
        """Vérifie le format et la taille du fichier audio.

        Returns:
            UploadedFile: Le fichier audio validé.

        Raises:
            forms.ValidationError: Si le format n'est pas accepté ou si le fichier est trop lourd.
        """
        audio = self.cleaned_data["audio"]
        if Path(audio.name).suffix.lower() not in EXTENSIONS_AUDIO:
            raise forms.ValidationError(
                "Format non pris en charge : utilisez un fichier wav, mp3, m4a, ogg ou webm."
            )
        if audio.size > TAILLE_MAX_AUDIO:
            raise forms.ValidationError("Le fichier dépasse la taille maximale de 20 Mo.")
        return audio

    def clean_date_reve(self):
        """Refuse une date de rêve dans le futur.

        Returns:
            date: La date validée.

        Raises:
            forms.ValidationError: Si la date est postérieure à aujourd'hui.
        """
        date_reve = self.cleaned_data["date_reve"]
        if date_reve > timezone.localdate():
            raise forms.ValidationError("La date du rêve ne peut pas être dans le futur.")
        return date_reve
