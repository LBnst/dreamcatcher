"""Vues des rêves : création, vérification, consultation et suivi du traitement."""

from django.contrib import messages
from django.core.paginator import Paginator
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from accounts.decorators import consentement_requis

from .forms import CorrectionForm, FiltresForm, ReveForm
from .models import Reve
from .services.pipeline import demarrer_traitement
from .services.quotas import MESSAGE_BUDGET, budget_atteint, message_quota
from .services.statistiques import statistiques
from .services.video import suivre_video

TAILLE_PAGE_HISTORIQUE = 10


def historique(request):
    """Liste les rêves de l'utilisateur, filtrables, du plus récent au plus ancien.

    Accessible même sans consentement : chacun doit pouvoir consulter ses
    propres données (droit d'accès RGPD).

    Args:
        request: Requête HTTP reçue.

    Returns:
        HttpResponse: La page de l'historique.
    """
    filtres = FiltresForm(request.GET or None)
    reves = filtres.filtrer(Reve.objects.filter(utilisateur=request.user))
    page = Paginator(reves, TAILLE_PAGE_HISTORIQUE).get_page(request.GET.get("page"))

    parametres = request.GET.copy()
    parametres.pop("page", None)
    contexte = {"page": page, "filtres": filtres, "parametres": parametres.urlencode()}
    return render(request, "dreams/historique.html", contexte)


@consentement_requis
def nouveau_reve(request):
    """Affiche l'enregistreur, crée le rêve et lance son traitement.

    Le rêve est refusé, avec un message clair, si le budget mensuel ou le quota
    quotidien de l'utilisateur est atteint.

    Args:
        request: Requête HTTP reçue.

    Returns:
        HttpResponse: Le formulaire, ou une redirection vers le rêve créé.
    """
    form = ReveForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        refus = _motif_de_refus(request.user, form.cleaned_data["type_media"])
        if refus is None:
            reve = form.save(commit=False)
            reve.utilisateur = request.user
            reve.save()
            demarrer_traitement(reve)
            messages.success(request, "Votre rêve a bien été enregistré : son analyse commence.")
            return redirect("detail_reve", pk=reve.pk)
        form.add_error(None, refus)
    return render(request, "dreams/nouveau.html", {"form": form})


def _motif_de_refus(utilisateur, type_media):
    """Renvoie la raison d'un refus (budget ou quota atteint), ou ``None``.

    Args:
        utilisateur: Utilisateur qui envoie le rêve.
        type_media: Rendu demandé.

    Returns:
        str | None: Le message de refus, ou ``None`` si le rêve peut être créé.
    """
    if budget_atteint():
        return MESSAGE_BUDGET
    return message_quota(utilisateur, type_media)


def detail_reve(request, pk):
    """Affiche un rêve, uniquement à son propriétaire.

    Args:
        request: Requête HTTP reçue.
        pk: Identifiant du rêve.

    Returns:
        HttpResponse: La fiche du rêve (erreur 404 si le rêve appartient à un autre utilisateur).
    """
    reve = get_object_or_404(Reve, pk=pk, utilisateur=request.user)
    return render(request, "dreams/detail.html", {"reve": reve})


def media_reve(request, pk):
    """Envoie l'image ou la vidéo d'un rêve, uniquement à son propriétaire.

    Les fichiers ne sont jamais servis directement par leur adresse : chaque accès
    passe par ce contrôle (exigence « accès uniquement à mes propres données »).

    Args:
        request: Requête HTTP reçue.
        pk: Identifiant du rêve.

    Returns:
        FileResponse: Le fichier (erreur 404 s'il n'existe pas ou appartient à un autre).
    """
    reve = get_object_or_404(Reve, pk=pk, utilisateur=request.user)
    if not reve.media:
        raise Http404("Aucun média pour ce rêve.")
    reponse = FileResponse(reve.media.open("rb"))
    reponse["Cache-Control"] = "private, max-age=3600"
    return reponse


@require_GET
def statut_reve(request, pk):
    """Renvoie le statut du traitement, interrogé toutes les 5 s par la page du rêve.

    Pour une vidéo en cours de génération, c'est aussi l'occasion de demander
    son avancement à Google.

    Args:
        request: Requête HTTP reçue.
        pk: Identifiant du rêve.

    Returns:
        JsonResponse: ``{"statut": "en_cours" | "a_valider" | "termine" | "erreur"}``.
    """
    reve = get_object_or_404(Reve, pk=pk, utilisateur=request.user)
    if reve.statut == Reve.Statut.EN_COURS and reve.id_tache_externe:
        reve = suivre_video(reve.pk)
    return JsonResponse({"statut": reve.statut})


@require_POST
@consentement_requis
def reessayer_reve(request, pk):
    """Relance le traitement d'un rêve en erreur, si son audio est encore disponible.

    Args:
        request: Requête HTTP reçue.
        pk: Identifiant du rêve.

    Returns:
        HttpResponse: Redirection vers le rêve, ou vers un nouvel enregistrement.
    """
    reve = get_object_or_404(Reve, pk=pk, utilisateur=request.user)
    if reve.statut != Reve.Statut.ERREUR:
        return redirect("detail_reve", pk=reve.pk)
    if not reve.audio and not reve.transcription:
        messages.error(
            request, "L'enregistrement n'est plus disponible : racontez à nouveau votre rêve."
        )
        return redirect("nouveau_reve")

    reve.statut = Reve.Statut.EN_COURS
    reve.message_erreur = ""
    reve.save(update_fields=["statut", "message_erreur"])
    demarrer_traitement(reve)
    return redirect("detail_reve", pk=reve.pk)


@require_POST
def supprimer_reve(request, pk):
    """Supprime définitivement un rêve, uniquement pour son propriétaire.

    Le signal ``effacer_fichiers_du_reve`` efface l'audio, l'image ou la vidéo ;
    les traces de coût sont conservées, détachées du rêve, pour le suivi du budget.
    Aucun consentement n'est exigé : on peut toujours effacer ses données.

    Args:
        request: Requête HTTP reçue.
        pk: Identifiant du rêve.

    Returns:
        HttpResponse: Redirection vers l'historique.
    """
    reve = get_object_or_404(Reve, pk=pk, utilisateur=request.user)
    reve.delete()
    messages.success(request, "Le rêve a été supprimé.")
    return redirect("historique")


def tableau_de_bord(request):
    """Affiche les statistiques des rêves de l'utilisateur.

    Args:
        request: Requête HTTP reçue.

    Returns:
        HttpResponse: Le tableau de bord.
    """
    return render(request, "dreams/tableau_de_bord.html", {"stats": statistiques(request.user)})


def valider_reve(request, pk):
    """Fait vérifier la transcription et l'émotion, puis lance la génération du visuel.

    La génération (payante) n'a lieu qu'après cette vérification. La mise à jour
    n'est faite que si le rêve est encore « à valider » : un double clic ne lance
    pas deux générations, ni deux dépenses.

    Args:
        request: Requête HTTP reçue.
        pk: Identifiant du rêve.

    Returns:
        HttpResponse: Le formulaire de vérification, ou une redirection vers le rêve.
    """
    reve = get_object_or_404(Reve, pk=pk, utilisateur=request.user)
    if reve.statut != Reve.Statut.A_VALIDER:
        return redirect("detail_reve", pk=reve.pk)

    emotion_initiale = reve.emotion
    donnees = request.POST if request.method == "POST" else None
    formulaire = CorrectionForm(donnees, instance=reve)
    if formulaire.is_valid():
        lance = Reve.objects.filter(pk=reve.pk, statut=Reve.Statut.A_VALIDER).update(
            transcription=formulaire.cleaned_data["transcription"],
            emotion=formulaire.cleaned_data["emotion"],
            emotion_corrigee=formulaire.cleaned_data["emotion"] != emotion_initiale,
            valide=True,
            statut=Reve.Statut.EN_COURS,
        )
        if lance:
            demarrer_traitement(reve)
            messages.success(request, "C'est parti : votre visuel est en cours de création.")
        return redirect("detail_reve", pk=reve.pk)

    return render(request, "dreams/valider.html", {"reve": reve, "formulaire": formulaire})


def corriger_reve(request, pk):
    """Permet à l'utilisateur de corriger la transcription et l'émotion d'un rêve.

    Accessible même sans consentement : c'est le droit de rectification (RGPD).
    L'illustration déjà générée n'est pas recréée, pour ne pas engager de coût.

    Args:
        request: Requête HTTP reçue.
        pk: Identifiant du rêve.

    Returns:
        HttpResponse: Le formulaire, ou une redirection vers le détail du rêve.
    """
    reve = get_object_or_404(Reve, pk=pk, utilisateur=request.user)
    if reve.statut == Reve.Statut.A_VALIDER:
        # Avant la génération, la correction passe par la page de vérification.
        return redirect("valider_reve", pk=reve.pk)
    if reve.statut == Reve.Statut.EN_COURS:
        messages.warning(request, "Ce rêve est encore en cours de traitement.")
        return redirect("detail_reve", pk=reve.pk)

    emotion_initiale = reve.emotion
    donnees = request.POST if request.method == "POST" else None
    formulaire = CorrectionForm(donnees, instance=reve)
    if formulaire.is_valid():
        reve = formulaire.save(commit=False)
        if reve.emotion != emotion_initiale:
            reve.emotion_corrigee = True
        reve.save()
        messages.success(request, "Vos corrections ont été enregistrées.")
        return redirect("detail_reve", pk=reve.pk)

    contexte = {"reve": reve, "formulaire": formulaire}
    return render(request, "dreams/corriger.html", contexte)


def progression_reve(request, pk):
    """Renvoie l'avancement du traitement d'un rêve, en JSON, sans rien modifier.

    Args:
        request: Requête HTTP reçue.
        pk: Identifiant du rêve.

    Returns:
        JsonResponse: Le statut, l'étape en cours et le pourcentage d'avancement.
    """
    reve = get_object_or_404(Reve, pk=pk, utilisateur=request.user)
    return JsonResponse(
        {
            "statut": reve.statut,
            "etape": reve.etape_courante or "",
            "pourcentage": reve.pourcentage_progression,
        }
    )
