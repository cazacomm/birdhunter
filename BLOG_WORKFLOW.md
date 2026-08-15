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

## 5. Douze sujets d'articles prêts à écrire

Classés dans un ordre qui suit la saison. Chacun est ancré local + métier.

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
