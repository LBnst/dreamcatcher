(() => {
  const bloc = document.getElementById("progression");
  if (!bloc) return;

  const INTERVALLE_MS = 3000;

  async function verifier() {
    try {
      const reponse = await fetch(bloc.dataset.url, { headers: { Accept: "application/json" } });
      if (reponse.ok) {
        const donnees = await reponse.json();
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