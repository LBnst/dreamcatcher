(() => {
  const source = document.getElementById("donnees-tableau-de-bord");
  if (!source || !window.Chart) return;

  const donnees = JSON.parse(source.textContent);
  let graphiques = [];

  function variable(nom) {
    return getComputedStyle(document.documentElement).getPropertyValue(nom).trim();
  }

  function dessiner() {
    graphiques.forEach((graphique) => graphique.destroy());

    const texte = variable("--bs-body-color");
    const grille = variable("--bs-border-color-translucent");
    const surface = variable("--bs-body-bg");
    const couleur = (emotion) => variable(`--emotion-${emotion}`);
    Chart.defaults.color = variable("--bs-secondary-color");
    Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;

    const evolution = new Chart(document.getElementById("graphique-evolution"), {
      type: "bar",
      data: {
        labels: donnees.evolution.mois,
        datasets: donnees.evolution.series.map((serie) => ({
          label: serie.libelle,
          data: serie.valeurs,
          backgroundColor: couleur(serie.emotion),
          borderColor: surface, // fin liseré de la couleur du fond entre les segments
          borderWidth: 2,
          borderRadius: 4,
          maxBarThickness: 48,
        })),
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { position: "top", labels: { color: texte, usePointStyle: true } },
        },
        scales: {
          x: { stacked: true, grid: { display: false } },
          y: {
            stacked: true,
            beginAtZero: true,
            ticks: { precision: 0 },
            grid: { color: grille },
            title: { display: true, text: "Nombre de rêves" },
          },
        },
      },
    });

    const repartition = new Chart(document.getElementById("graphique-repartition"), {
      type: "bar",
      data: {
        labels: donnees.repartition.map((ligne) => ligne.libelle),
        datasets: [
          {
            label: "Rêves",
            data: donnees.repartition.map((ligne) => ligne.nombre),
            backgroundColor: donnees.repartition.map((ligne) => couleur(ligne.emotion)),
            borderRadius: 4,
            maxBarThickness: 28,
          },
        ],
      },
      options: {
        indexAxis: "y",
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          x: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: grille } },
          y: { grid: { display: false }, ticks: { color: texte } },
        },
      },
    });

    graphiques = [evolution, repartition];
  }

  dessiner();
})();