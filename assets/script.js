/* ==========================================================================
   BIRD HUNTER 65 — Scripts du site
   Aucune bibliothèque externe : tout est en JavaScript natif.

   1. Menu mobile
   2. Lien de navigation actif au défilement
   3. Apparition des blocs au défilement
   4. Année automatique dans le pied de page
   5. Pré-remplissage de la formule depuis les cartes d'offres
   6. Envoi du formulaire (Web3Forms)
   ========================================================================== */

(function () {
  'use strict';

  /* ======================================================================
     1. MENU MOBILE
     ====================================================================== */
  var burger = document.querySelector('.burger');
  var nav = document.querySelector('.nav-principale');

  function fermerMenu() {
    if (!nav || !burger) return;
    nav.classList.remove('ouvert');
    burger.setAttribute('aria-expanded', 'false');
    document.body.style.overflow = '';
  }

  if (burger && nav) {
    burger.addEventListener('click', function () {
      var ouvert = nav.classList.toggle('ouvert');
      burger.setAttribute('aria-expanded', ouvert ? 'true' : 'false');
      // On bloque le défilement de la page quand le menu est ouvert
      document.body.style.overflow = ouvert ? 'hidden' : '';
    });

    // Un clic sur un lien du menu le referme
    nav.addEventListener('click', function (e) {
      if (e.target.closest('a')) fermerMenu();
    });

    // La touche Échap referme le menu
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') fermerMenu();
    });

    // Si on repasse en affichage bureau, on remet tout à zéro
    window.addEventListener('resize', function () {
      if (window.innerWidth > 960) fermerMenu();
    });
  }


  /* ======================================================================
     2. LIEN DE NAVIGATION ACTIF AU DÉFILEMENT
     Surligne dans le menu la section actuellement à l'écran.
     ====================================================================== */
  var liensNav = Array.prototype.slice.call(
    document.querySelectorAll('.nav-liste a[href^="#"]')
  );
  var sections = liensNav
    .map(function (a) { return document.querySelector(a.getAttribute('href')); })
    .filter(Boolean);

  if (sections.length && 'IntersectionObserver' in window) {
    var observateurNav = new IntersectionObserver(function (entrees) {
      entrees.forEach(function (entree) {
        if (!entree.isIntersecting) return;
        liensNav.forEach(function (a) {
          a.classList.toggle('actif', a.getAttribute('href') === '#' + entree.target.id);
        });
      });
    }, { rootMargin: '-45% 0px -50% 0px', threshold: 0 });

    sections.forEach(function (s) { observateurNav.observe(s); });
  }


  /* ======================================================================
     2 bis. EN-TÊTE QUI SE RESSERRE AU DÉFILEMENT
     ====================================================================== */
  var entete = document.querySelector('.entete');

  if (entete) {
    var dernierEtat = null;
    var majEntete = function () {
      var reduit = window.scrollY > 60;
      if (reduit !== dernierEtat) {
        entete.classList.toggle('reduit', reduit);
        dernierEtat = reduit;
      }
    };
    majEntete();
    window.addEventListener('scroll', function () {
      window.requestAnimationFrame(majEntete);
    }, { passive: true });
  }


  /* ======================================================================
     3. APPARITION DES BLOCS AU DÉFILEMENT

     Les éléments d'une même rangée arrivent en cascade : on pose sur chacun
     un petit délai (--retard) lu par la feuille de style.
     ====================================================================== */
  ['.offres-grille', '.avis-grille', '.horaires', '.reperes-grille'].forEach(function (sel) {
    var groupe = document.querySelector(sel);
    if (!groupe) return;
    Array.prototype.forEach.call(groupe.children, function (enfant, i) {
      enfant.style.setProperty('--retard', (i % 3) * 0.09 + 's');
    });
  });

  var aAnimer = document.querySelectorAll('.apparition');

  if (!('IntersectionObserver' in window)) {
    // Navigateur ancien : on affiche tout immédiatement
    Array.prototype.forEach.call(aAnimer, function (el) { el.classList.add('visible'); });
  } else {
    var observateurApparition = new IntersectionObserver(function (entrees, obs) {
      entrees.forEach(function (entree) {
        if (!entree.isIntersecting) return;
        entree.target.classList.add('visible');
        obs.unobserve(entree.target);
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });

    Array.prototype.forEach.call(aAnimer, function (el) { observateurApparition.observe(el); });
  }


  /* ======================================================================
     4. ANNÉE AUTOMATIQUE
     ====================================================================== */
  Array.prototype.forEach.call(document.querySelectorAll('[data-annee]'), function (el) {
    el.textContent = new Date().getFullYear();
  });

  Array.prototype.forEach.call(document.querySelectorAll('[data-maj]'), function (el) {
    el.textContent = new Date().toLocaleDateString('fr-FR');
  });


  /* ======================================================================
     5. PRÉ-REMPLISSAGE DE LA FORMULE
     Quand on clique sur « Demander cette formule » dans une carte d'offre,
     la liste déroulante du formulaire se positionne sur la bonne offre.
     ====================================================================== */
  var champFormule = document.getElementById('formule');

  Array.prototype.forEach.call(document.querySelectorAll('[data-formule]'), function (lien) {
    lien.addEventListener('click', function () {
      if (!champFormule) return;
      var valeur = lien.getAttribute('data-formule');
      var trouve = Array.prototype.some.call(champFormule.options, function (opt) {
        return opt.value === valeur;
      });
      if (trouve) champFormule.value = valeur;
    });
  });


  /* ======================================================================
     6. ENVOI DU FORMULAIRE (Web3Forms)

     ⚠️ POUR ACTIVER LE FORMULAIRE :
        1. Créez votre formulaire sur https://web3forms.com (gratuit).
        2. Copiez la clé d'accès (Access Key) reçue par e-mail.
        3. Collez-la dans index.html, dans le champ caché :
              <input type="hidden" name="access_key" value="VOTRE-CLE-ICI">

     Tant que la clé n'est pas renseignée, le formulaire n'envoie rien et
     invite poliment le visiteur à téléphoner ou à écrire directement.
     ====================================================================== */
  var CLE_NON_RENSEIGNEE = 'REMPLACER-PAR-VOTRE-CLE-WEB3FORMS';

  var formulaire = document.getElementById('formulaire-contact');

  if (formulaire) {
    var zoneMessage = document.getElementById('form-message');
    var bouton = formulaire.querySelector('button[type="submit"]');
    var libelleBouton = bouton ? bouton.innerHTML : '';

    function afficherMessage(texte, type) {
      if (!zoneMessage) return;
      zoneMessage.innerHTML = texte;
      zoneMessage.className = 'form-message visible ' + type;
      zoneMessage.setAttribute('role', 'status');
      zoneMessage.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    var SECOURS =
      'Vous pouvez nous joindre directement au ' +
      '<a href="tel:+33609276288">06 09 27 62 88</a> ou par e-mail à ' +
      '<a href="mailto:birdhunterdu65@gmail.com">birdhunterdu65@gmail.com</a>.';

    formulaire.addEventListener('submit', function (e) {
      e.preventDefault();

      var cle = formulaire.querySelector('[name="access_key"]');
      var valeurCle = cle ? cle.value.trim() : '';

      // Garde-fou : la clé Web3Forms n'a pas encore été installée
      if (!valeurCle || valeurCle === CLE_NON_RENSEIGNEE) {
        afficherMessage(
          '<strong>Le formulaire n’est pas encore activé.</strong><br>' + SECOURS,
          'erreur'
        );
        return;
      }

      if (bouton) {
        bouton.disabled = true;
        bouton.innerHTML = 'Envoi en cours…';
      }

      fetch('https://api.web3forms.com/submit', {
        method: 'POST',
        headers: { 'Accept': 'application/json' },
        body: new FormData(formulaire)
      })
        .then(function (reponse) { return reponse.json(); })
        .then(function (data) {
          if (data && data.success) {
            afficherMessage(
              '<strong>Merci, votre message est bien parti !</strong><br>' +
              'Nous vous répondons dans les meilleurs délais. Pour une demande urgente, ' +
              'appelez-nous au <a href="tel:+33609276288">06 09 27 62 88</a>.',
              'succes'
            );
            formulaire.reset();
          } else {
            afficherMessage(
              '<strong>L’envoi n’a pas abouti.</strong><br>' + SECOURS,
              'erreur'
            );
          }
        })
        .catch(function () {
          afficherMessage(
            '<strong>L’envoi n’a pas abouti (problème de connexion).</strong><br>' + SECOURS,
            'erreur'
          );
        })
        .then(function () {
          if (bouton) {
            bouton.disabled = false;
            bouton.innerHTML = libelleBouton;
          }
        });
    });
  }

})();
