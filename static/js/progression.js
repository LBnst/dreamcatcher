// Suit l'avancement du traitement d'un rêve. Quand l'analyse est finie, l'utilisateur est
// envoyé vers la page de vérification ; sinon, la page est rechargée quand l'étape change
// ou quand le traitement se termine. Le bloc de progression lui-même est rendu par Django.
(() => {
  const bloc = document.getElementById("progression");
  if (!bloc) return;

  const INTERVALLE_MS = 3000;

  async function verifier() {
    try {
      const reponse = await fetch(bloc.dataset.url, { headers: { Accept: "application/json" } });
      if (reponse.ok) {
        const donnees = await reponse.json();
        if (donnees.statut === "a_valider") {
          window.location.href = bloc.dataset.urlValidation;
          return;
        }
        if (donnees.statut !== "en_cours" || donnees.etape !== bloc.dataset.etape) {
          window.location.reload();
          return;
        }
      }
    } catch {
      // Réseau coupé ou session expirée : on réessaie au prochain tour.
    }
    setTimeout(verifier, INTERVALLE_MS);
  }

  setTimeout(verifier, INTERVALLE_MS);
})();
