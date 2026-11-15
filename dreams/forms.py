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


class FiltresForm(forms.Form):
    """Filtres de l'historique : période, émotion et mot-clé, tous facultatifs."""

    debut = forms.DateField(
        label="Du",
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}, format="%Y-%m-%d"),
    )
    fin = forms.DateField(
        label="Au",
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}, format="%Y-%m-%d"),
    )
    emotion = forms.ChoiceField(
        label="Émotion",
        required=False,
        choices=[("", "Toutes"), *Reve.Emotion.choices],
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    q = forms.CharField(
        label="Mot-clé",
        required=False,
        max_length=100,
        widget=forms.TextInput(
            attrs={"type": "search", "class": "form-control", "placeholder": "forêt, mer…"}
        ),
    )

    def clean(self):
        """Vérifie que la période est dans le bon ordre.

        Returns:
            dict: Les données nettoyées.

        Raises:
            forms.ValidationError: Si la date de début est après la date de fin.
        """
        donnees = super().clean()
        debut, fin = donnees.get("debut"), donnees.get("fin")
        if debut and fin and debut > fin:
            raise forms.ValidationError("La date de début doit précéder la date de fin.")
        return donnees

    @property
    def actif(self):
        """bool: Vrai si au moins un filtre valide est renseigné."""
        return self.is_valid() and any(self.cleaned_data.values())

    def filtrer(self, reves):
        """Applique les filtres valides à un ensemble de rêves.

        Args:
            reves: QuerySet des rêves de l'utilisateur.

        Returns:
            QuerySet: Les rêves filtrés (inchangés si les filtres sont invalides).
        """
        if not self.is_valid():
            return reves
        donnees = self.cleaned_data
        if donnees["debut"]:
            reves = reves.filter(date_reve__gte=donnees["debut"])
        if donnees["fin"]:
            reves = reves.filter(date_reve__lte=donnees["fin"])
        if donnees["emotion"]:
            reves = reves.filter(emotion=donnees["emotion"])
        if donnees["q"].strip():
            reves = reves.filter(transcription__icontains=donnees["q"].strip())
        return reves


class CorrectionForm(forms.ModelForm):
    """Correction par l'utilisateur de la transcription et de l'émotion détectée."""

    class Meta:
        model = Reve
        fields = ["transcription", "emotion"]
        labels = {"transcription": "Transcription", "emotion": "Émotion"}
        widgets = {
            "transcription": forms.Textarea(attrs={"class": "form-control", "rows": 8}),
            "emotion": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        """Rend les deux champs obligatoires : un rêve corrigé ne peut pas être vide."""
        super().__init__(*args, **kwargs)
        self.fields["transcription"].required = True
        self.fields["emotion"].required = True
