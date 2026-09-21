# Blog Bird Hunter 65 — mode d'emploi

Comment ajouter un article au blog `birdhunter65.fr/blog/`, sans rien casser.
Aucune connaissance technique avancée nécessaire : on duplique, on remplace, on publie.

---

## 1. Comment le blog est construit

```
blog/
  index.html                                    Liste des articles
  chasse-petit-gibier-tournay-comprendre-le-terrain/
    index.html                                  Article n°1 (modèle à dupliquer)
assets/
  blog.css                                      Styles du blog uniquement
rss.xml                                         Flux d'abonnement
llms.txt                                        Fiche d'identité pour les IA (ChatGPT, Claude…)
sitemap.xml                                     Liste des pages pour Google
robots.txt                                      Autorisations des robots
```

Chaque article vit dans **son propre dossier**, avec un fichier `index.html` dedans.
Le nom du dossier devient l'adresse de l'article :

```
blog/mon-nouveau-sujet/index.html
  →  https://birdhunter65.fr/blog/mon-nouveau-sujet/
```

Le blog réutilise `assets/style.css` (le style du site) + `assets/blog.css`.
**Ne touchez pas à `style.css`** : tout ce qui concerne le blog est dans `blog.css`.

---

## 2. Publier un nouvel article — la marche à suivre

### Étape 1 — Choisir l'adresse (le « slug »)

Uniquement des minuscules, des tirets, pas d'accents, pas d'espaces.
Mettez-y le sujet **et** le lieu quand c'est pertinent.

✅ `entrainement-chien-chasse-avant-ouverture`
❌ `Article n°2 (juillet)`

### Étape 2 — Dupliquer l'article existant

Copiez le dossier `blog/chasse-petit-gibier-tournay-comprendre-le-terrain/`
et renommez la copie avec votre nouveau slug.

### Étape 3 — Dans le nouveau `index.html`, remplacer

| À remplacer | Où |
|---|---|
| L'ancien slug `chasse-petit-gibier-tournay-comprendre-le-terrain` | **partout** (canonical, OG, JSON-LD) — faites un rechercher/remplacer global |
| Le `<title>` | en haut du fichier |
| La `meta description` | **155 caractères maximum**, sinon Google la coupe |
| Les titres `og:title` / `twitter:title` | dans les blocs Open Graph et Twitter |
| Les descriptions `og:description` / `twitter:description` | idem |
| L'image `og:image` / `twitter:image` | une image de `imagesbirdhunter/` |
| Les dates `2026-08-15` | **partout** : `article:published_time`, `datePublished`, `dateModified`, `<time datetime>` |
| Le `<h1>`, le chapô, le corps de l'article | dans `<main>` |
| Les 5 questions de la FAQ | **deux endroits** : le bloc JSON-LD `FAQPage` en haut **et** le bloc `.faq-bloc` en bas — les deux doivent dire exactement la même chose |
| Le fil d'Ariane (3ᵉ niveau) | bloc `BreadcrumbList` en haut **et** `<nav class="fil-ariane">` en bas |

> ⚠️ **Règle d'or** : ce qui est écrit dans le JSON-LD doit être **visible sur la page**.
> Une FAQ déclarée à Google mais absente du texte est une faute pénalisée.

### Étape 4 — Ajouter la carte dans `blog/index.html`

Dupliquez le bloc `<article class="blog-carte">…</article>` et remplacez lien, image, date, titre et résumé.
Le plus récent se place **en premier**.

Ajoutez aussi l'article dans le bloc JSON-LD `"blogPost"` en haut de `blog/index.html`.

### Étape 5 — Mettre à jour les 3 fichiers de référencement

**`sitemap.xml`** — ajoutez un bloc, et mettez `<lastmod>` de `/blog/` à la date du jour :

```xml
<url>
  <loc>https://birdhunter65.fr/blog/mon-nouveau-sujet/</loc>
  <lastmod>2026-09-12</lastmod>
  <changefreq>monthly</changefreq>
  <priority>0.7</priority>
</url>
```

**`rss.xml`** — ajoutez un `<item>` **en haut** de la liste et mettez à jour `<lastBuildDate>`.
Format de date obligatoire : `Sat, 12 Sep 2026 08:00:00 +0200`.

**`llms.txt`** — ajoutez une ligne sous « ## Articles », avec le titre, la date et une phrase de résumé.
C'est ce fichier que lisent ChatGPT, Claude et Perplexity pour parler du domaine.

### Étape 6 — Publier

```bash
git add .
git commit -m "Blog : nouvel article — mon nouveau sujet"
git push
```

GitHub Pages met le site à jour en 1 à 2 minutes.

### Étape 7 — Prévenir Google

Dans la Search Console : **Inspection de l'URL** → collez l'adresse du nouvel article →
**Demander une indexation**. Cela fait gagner plusieurs jours.

---

## 3. Les règles de contenu (à ne jamais contourner)

1. **N'inventez jamais** un tarif, un chiffre, une date, un nom de client, un texte de loi.
   Si vous n'êtes pas sûr d'un chiffre, écrivez la phrase sans le chiffre.
2. **Longueur** : 1 200 à 1 500 mots. En dessous, l'article ne pèse rien pour Google.
3. **Structure** : un seul `<h1>`, puis des `<h2>` pour les grandes parties et des `<h3>` à l'intérieur.
4. **Ancrage local** : Tournay, Hautes-Pyrénées, 65, Tarbes, Occitanie doivent apparaître
   naturellement dans le texte — pas empilés en fin de page.
5. **FAQ** : exactement 5 questions, formulées comme un chasseur les poserait à voix haute.
6. **Les tarifs restent sur la page d'accueil.** Dans un article, renvoyez vers `/#offres`
   plutôt que de recopier un prix : le jour où il change, il n'y a qu'un seul endroit à corriger.
7. **Images** : utilisez celles de `imagesbirdhunter/`. Toujours un attribut `alt` décrivant
   réellement la photo, et `loading="lazy"` sauf pour l'image principale de l'article.

---

## 4. Les informations officielles du domaine (NAP)

À écrire **exactement** de la même façon partout — site, Google Business Profile, annuaires,
Facebook. La moindre variation dilue le référencement local.

```
Bird Hunter 65
Chemin de la Lande
65190 Tournay
06 09 27 62 88   (+33 6 09 27 62 88)
birdhunterdu65@gmail.com
https://birdhunter65.fr/
```

---

## 5. Sujets d'articles prêts à écrire

Classés dans un ordre qui suit la saison. Chacun est ancré local + métier.

> Ce tableau s'allonge tout seul : quand il reste moins de 8 sujets non traités,
> le robot en génère 40 de plus avant de rédiger. Vous pouvez bien sûr en ajouter
> à la main — gardez simplement le format exact des lignes ci-dessous.

| # | Sujet | Slug proposé | Bonne période |
|---|---|---|---|
| 1 | Remettre son chien au gibier avant l'ouverture : le rôle du parc d'entraînement | `entrainement-chien-chasse-avant-ouverture` | juin – août |
| 2 | Chasser à 15 minutes de Tarbes : ce que change la proximité d'un domaine privé | `domaine-chasse-prive-proche-tarbes` | toute l'année |
| 3 | Faisan ou perdreau : deux gibiers, deux façons de chasser | `faisan-perdreau-differences-chasse` | septembre – octobre |
| 4 | Organiser une journée de chasse entre amis dans les Hautes-Pyrénées | `organiser-journee-chasse-entre-amis-65` | septembre – décembre |
| 5 | Sécurité en action de chasse : les règles qui tiennent une ligne de 8 fusils | `securite-action-de-chasse-ligne-fusils` | ouverture |
| 6 | Bien s'équiper pour une journée au piémont pyrénéen : humidité, dénivelé, météo | `equipement-journee-chasse-piemont-pyreneen` | octobre – novembre |
| 7 | Le week-end de chasse avec hébergement : à quoi ressemble vraiment le rythme | `week-end-chasse-hebergement-bergerie` | octobre – février |
| 8 | Chasse au migrateur dans les Hautes-Pyrénées : palombe et bécasse, deux attentes différentes | `chasse-migrateur-palombe-becasse-65` | décembre – février |
| 9 | Débuter la chasse au petit gibier : ce qu'on aurait aimé savoir la première fois | `debuter-chasse-petit-gibier-conseils` | toute l'année |
| 10 | Chasse à l'approche du chevreuil et du sanglier : le silence comme méthode | `chasse-approche-chevreuil-sanglier-65` | juin – octobre |
| 11 | Chasser quand on est à mobilité réduite : ce que permet un domaine aménagé | `chasse-accessible-mobilite-reduite-domaine` | toute l'année |
| 12 | Un domaine de 120 hectares au fil des saisons : ce que la nature change au terrain | `domaine-120-hectares-au-fil-des-saisons` | fin de saison |
| 13 | Comment préparer votre chien pour une chasse au faisan à Tournay | `comment-preparer-chien-chasse-faisan-tournay` | août - septembre |
| 14 | Les meilleures périodes pour chasser le perdreau autour de Lannemezan | `meilleures-periodes-chasser-perdreau-autour-lannemezan` | septembre - novembre |
| 15 | Guide pour choisir le bon fusil pour la chasse au petit gibier en Occitanie | `guide-choisir-bon-fusil-chasse-petit-gibier` | toute l'année |
| 16 | Découvrir les spécificités de la chasse en domaine privé dans les Hautes-Pyrénées | `decouvrir-specificites-chasse-domaine-prive-hautes-pyrenees` | toute l'année |
| 17 | Planifier une journée de chasse en famille dans le piémont pyrénéen | `planifier-journee-chasse-famille-piemont-pyreneen` | octobre - novembre |
| 18 | Comparatif des munitions pour la chasse au faisan dans le Sud-Ouest | `comparatif-munitions-chasse-faisan-sud-ouest` | toute l'année |
| 19 | Les avantages d'une chasse privée près de Pau : confort et exclusivité | `avantages-chasse-privee-pres-pau-confort-exclusivite` | toute l'année |
| 20 | Pourquoi choisir un domaine de chasse à Tournay pour des journées sportives | `pourquoi-choisir-domaine-chasse-tournay-journees-sportives` | avril - juin |
| 21 | Les erreurs à éviter lors de votre première chasse au petit gibier à Bagnères-de-Bigorre | `erreurs-eviter-lors-premiere-chasse-petit-gibier` | septembre - octobre |
| 22 | Consignes pour une chasse sécurisée dans les Hautes-Pyrénées | `consignes-chasse-securisee-hautes-pyrenees` | toute l'année |
| 23 | Comment la météo influence-t-elle la chasse au petit gibier à Tarbes ? | `comment-meteo-influence-t-chasse-petit-gibier` | toute l'année |
| 24 | Coulisses d'une journée de chasse organisée dans un domaine privé à Tournay | `coulisses-journee-chasse-organisee-domaine-prive-tournay` | toute l'année |
| 25 | Les bienfaits de la chasse pour le bien-être : focus sur le domaine de chasse de 65 | `bienfaits-chasse-etre-focus-domaine-chasse-65` | toute l'année |
| 26 | Les meilleures pratiques pour préserver l'environnement lors d'une chasse en Occitanie | `meilleures-pratiques-preserver-environnement-lors-chasse-occitanie` | toute l'année |
| 27 | Comment optimiser votre équipement pour la chasse en terrain vallonné à Auch | `comment-optimiser-equipement-chasse-terrain-vallonne-auch` | septembre - novembre |
| 28 | Découverte de la chasse aux faisans : une aventure unique dans le piémont pyrénéen | `decouverte-chasse-faisans-aventure-unique-piemont-pyreneen` | octobre - novembre |
| 29 | Les spécificités de la chasse au perdreau dans les Hautes-Pyrénées | `specificites-chasse-perdreau-hautes-pyrenees` | septembre - novembre |
| 30 | Conseils pour une chasse réussie en domaine privé près de Pau | `conseils-chasse-reussie-domaine-prive-pres-pau` | toute l'année |
| 31 | Choisir le bon chien pour la chasse au petit gibier à Tournay | `choisir-bon-chien-chasse-petit-gibier-tournay` | toute l'année |
| 32 | Préparation physique pour une journée de chasse dans les collines de Lannemezan | `preparation-physique-journee-chasse-collines-lannemezan` | juin - août |
| 33 | Les critères pour sélectionner un domaine de chasse dans le Sud-Ouest | `criteres-selectionner-domaine-chasse-sud-ouest` | toute l'année |
| 34 | Chasse et traditions locales : immersion dans les pratiques pyrénéennes | `chasse-traditions-locales-immersion-pratiques-pyreneennes` | toute l'année |
| 35 | Les équipements indispensables pour une chasse au petit gibier à Tarbes | `equipements-indispensables-chasse-petit-gibier-tarbes` | octobre - décembre |
| 36 | Pourquoi les Hautes-Pyrénées sont idéales pour la chasse au petit gibier ? | `pourquoi-hautes-pyrenees-sont-ideales-chasse-petit` | toute l'année |
| 37 | Organiser un événement de chasse professionnel dans le domaine de Bird Hunter 65 | `organiser-evenement-chasse-professionnel-domaine-bird-hunter` | toute l'année |
| 38 | Les défis de la chasse en altitude : conseils pour les chasseurs à Bagnères-de-Bigorre | `defis-chasse-altitude-conseils-chasseurs-bagneres-bigorre` | octobre - novembre |
| 39 | Comment le changement de saison affecte-t-il la chasse au faisan à Tournay ? | `comment-changement-saison-affecte-t-chasse-faisan` | toute l'année |
| 40 | Les avantages d'une chasse en petit comité dans le piémont pyrénéen | `avantages-chasse-petit-comite-piemont-pyreneen` | toute l'année |
| 41 | Visite guidée des installations de chasse à Bird Hunter 65 | `visite-guidee-installations-chasse-bird-hunter-65` | toute l'année |
| 42 | L'impact des conditions météorologiques sur la chasse au petit gibier à Pau | `impact-conditions-meteorologiques-chasse-petit-gibier-pau` | toute l'année |
| 43 | Que faire après une journée de chasse réussie à Tournay ? | `faire-apres-journee-chasse-reussie-tournay` | toute l'année |
| 44 | Les meilleures astuces pour repérer le petit gibier dans les Hautes-Pyrénées | `meilleures-astuces-reperer-petit-gibier-hautes-pyrenees` | octobre - décembre |
| 45 | Pourquoi choisir les Hautes-Pyrénées pour une chasse au faisan inoubliable ? | `pourquoi-choisir-hautes-pyrenees-chasse-faisan-inoubliable` | toute l'année |
| 46 | Les bénéfices d'une chasse écoresponsable dans le domaine de Bird Hunter 65 | `benefices-chasse-ecoresponsable-domaine-bird-hunter-65` | toute l'année |
| 47 | Comment bien gérer un groupe de chasseurs en domaine privé à Tournay | `comment-gerer-groupe-chasseurs-domaine-prive-tournay` | toute l'année |
| 48 | Les différents types de gibier à découvrir dans le domaine de Bird Hunter 65 | `differents-types-gibier-decouvrir-domaine-bird-hunter` | toute l'année |
| 49 | Les techniques traditionnelles de chasse au perdreau dans le Sud-Ouest | `techniques-traditionnelles-chasse-perdreau-sud-ouest` | septembre - novembre |
| 50 | Pourquoi la chasse en Occitanie est une expérience unique pour les passionnés | `pourquoi-chasse-occitanie-experience-unique-passionnes` | toute l'année |
| 51 | Les clés pour une chasse réussie au faisan dans les collines pyrénéennes | `cles-chasse-reussie-faisan-collines-pyreneennes` | septembre - novembre |
| 52 | Le rôle de l'écosystème local dans la préservation du petit gibier à Tournay | `role-ecosysteme-local-preservation-petit-gibier-tournay` | toute l'année |

**Rythme conseillé :** un article par mois. Mieux vaut 12 bons articles par an
que 30 articles bâclés — Google mesure la qualité, pas le volume.

---

## 6. Vérifications avant de publier

- [ ] La `meta description` fait moins de 155 caractères
- [ ] L'ancien slug n'apparaît plus nulle part dans le nouveau fichier
- [ ] Toutes les dates ont été changées (elles apparaissent 5 fois)
- [ ] Les 5 questions de la FAQ sont identiques dans le JSON-LD et dans le texte visible
- [ ] Chaque image a un `alt` qui décrit la photo
- [ ] La carte est ajoutée dans `blog/index.html`
- [ ] `sitemap.xml`, `rss.xml` et `llms.txt` sont à jour
- [ ] Test des données structurées : https://search.google.com/test/rich-results
- [ ] Test de l'affichage mobile : réduisez la fenêtre du navigateur, tout doit rester lisible
