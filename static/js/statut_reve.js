// Tant que le rêve est en cours de traitement, interroge le serveur toutes les 5 s,
// puis recharge la page dès que le résultat (ou une erreur) est disponible.
(() => {
  const bloc = document.getElementById("traitement-en-cours");
  if (!bloc) return;

  const minuterie = setInterval(async () => {
    try {
      const reponse = await fetch(bloc.dataset.urlStatut, { headers: { Accept: "application/json" } });
      if (!reponse.ok) return;
      const { statut } = await reponse.json();
      if (statut !== "en_cours") {
        clearInterval(minuterie);
        window.location.reload();
      }
    } catch {
      // Réseau momentanément coupé : on réessaie au prochain tour.
    }
  }, 5000);
})();