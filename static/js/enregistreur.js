// Enregistreur audio : capte le micro avec MediaRecorder, puis place le fichier
// obtenu dans le champ "audio" du formulaire, exactement comme un import classique.
(() => {
  const champAudio = document.getElementById("id_audio");
  const statut = document.getElementById("enr-statut");
  const chrono = document.getElementById("enr-chrono");
  const boutonDemarrer = document.getElementById("enr-demarrer");
  const boutonArreter = document.getElementById("enr-arreter");
  const apercu = document.getElementById("enr-apercu");
  const lecteur = document.getElementById("enr-lecteur");
  const boutonRecommencer = document.getElementById("enr-recommencer");
  const MESSAGE_INITIAL = statut.textContent;

  // Navigateur trop ancien, ou page non sécurisée (le micro exige HTTPS ou localhost).
  if (!navigator.mediaDevices || !window.MediaRecorder) {
    statut.textContent = "Enregistrement impossible sur ce navigateur : importez un fichier audio.";
    boutonDemarrer.disabled = true;
    return;
  }

  let enregistreur;
  let morceaux = [];
  let debut;
  let minuterie;

  function afficherChrono() {
    const secondes = Math.floor((Date.now() - debut) / 1000);
    const mm = String(Math.floor(secondes / 60)).padStart(2, "0");
    const ss = String(secondes % 60).padStart(2, "0");
    chrono.textContent = `${mm}:${ss}`;
  }

  boutonDemarrer.addEventListener("click", async () => {
    let flux;
    try {
      flux = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      statut.textContent = "Accès au micro refusé : autorisez-le dans votre navigateur ou importez un fichier.";
      return;
    }

    morceaux = [];
    enregistreur = new MediaRecorder(flux);
    enregistreur.addEventListener("dataavailable", (evenement) => {
      if (evenement.data.size > 0) morceaux.push(evenement.data);
    });
    enregistreur.addEventListener("stop", () => {
      flux.getTracks().forEach((piste) => piste.stop()); // libère le micro
      clearInterval(minuterie);

      // Chrome et Firefox produisent du webm, Safari du mp4 (extension .m4a).
      const type = enregistreur.mimeType || "audio/webm";
      const extension = type.includes("mp4") ? "m4a" : type.includes("ogg") ? "ogg" : "webm";
      const blob = new Blob(morceaux, { type });
      const fichier = new File([blob], `enregistrement.${extension}`, { type });

      const transfert = new DataTransfer();
      transfert.items.add(fichier);
      champAudio.files = transfert.files;

      lecteur.src = URL.createObjectURL(blob);
      apercu.classList.remove("d-none");
      boutonArreter.classList.add("d-none");
      statut.textContent = "Réécoutez votre récit, puis envoyez-le ou recommencez.";
    });

    enregistreur.start();
    debut = Date.now();
    afficherChrono();
    minuterie = setInterval(afficherChrono, 1000);
    boutonDemarrer.classList.add("d-none");
    boutonArreter.classList.remove("d-none");
    apercu.classList.add("d-none");
    statut.textContent = "Enregistrement en cours…";
  });

  boutonArreter.addEventListener("click", () => enregistreur.stop());

  boutonRecommencer.addEventListener("click", () => {
    champAudio.value = "";
    URL.revokeObjectURL(lecteur.src);
    lecteur.removeAttribute("src");
    apercu.classList.add("d-none");
    boutonDemarrer.classList.remove("d-none");
    chrono.textContent = "00:00";
    statut.textContent = MESSAGE_INITIAL;
  });
})();