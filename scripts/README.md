# Génération automatique d'articles

Un article de blog est rédigé et publié **chaque lundi à 9 h UTC** (11 h en France
l'été, 10 h l'hiver), sans intervention. Le sujet est pris dans le tableau des
12 sujets de [`BLOG_WORKFLOW.md`](../BLOG_WORKFLOW.md), dans l'ordre.

| Fichier | Rôle |
|---|---|
| `blog-config.json` | Identité du site, ton, faits autorisés, modèle OpenAI |
| `scripts/generate-article.py` | Le script de génération |
| `.github/workflows/blog-auto.yml` | La planification hebdomadaire |

---

## 1. Comment ça marche

Le modèle **n'écrit pas de HTML**. Il ne rend qu'un objet JSON éditorial : titre,
chapô, sections, paragraphes, listes, FAQ. C'est le script qui fabrique la page —
`<head>`, canonical, Open Graph, Twitter Card, les trois blocs JSON-LD, le fil
d'Ariane, le marqueur d'idempotence, l'en-tête et le pied de page.

Deux conséquences directes :

- **Le volume rédigé monte.** Auparavant les deux tiers des tokens de sortie
  partaient en balisage, ce qui plafonnait le corps bien en dessous de la cible.
  Le budget de sortie va désormais entièrement au texte.
- **Les données structurées sont valides par construction.** Elles sont
  sérialisées par `json.dumps`, plus rédigées à la main par le modèle.

Le gabarit HTML n'est pas dans le script : il est relu à chaque exécution depuis
l'article désigné par `reference_article_slug`, puis découpé par
`split_template()`. Voir la section 8.

---

## 2. Installer la clé API (à faire une seule fois)

1. Créez une clé sur <https://platform.openai.com/api-keys>
2. Dans le dépôt GitHub : **Settings → Secrets and variables → Actions → New repository secret**
3. Nom exact : `OPENAI_API_KEY` — valeur : la clé (elle commence par `sk-`)

Vérifiez aussi, dans **Settings → Actions → General → Workflow permissions**,
que l'option **Read and write permissions** est cochée : sans elle, le robot ne
peut pas pousser l'article.

> La clé n'apparaît jamais dans le dépôt ni dans les journaux d'exécution.

---

## 3. Lancer une génération à la main

Onglet **Actions → Blog — article automatique → Run workflow**. Deux options :

- **Test à blanc** : le script rédige l'article et affiche le résultat dans le
  journal, mais n'écrit et ne publie rien. À utiliser pour juger la qualité.
- **Réécrire un article existant** : saisissez le slug d'un article déjà publié
  (par exemple `entrainement-chien-chasse-avant-ouverture`). Le script retrouve
  le sujet grâce au marqueur du fichier, régénère l'article, écrase la page et
  resynchronise le teaser dans `blog/index.html` et dans `rss.xml`.

### En local

```bash
pip install openai
export OPENAI_API_KEY="sk-..."

python3 scripts/generate-article.py --dry-run    # aperçu, rien n'est écrit
python3 scripts/generate-article.py              # génère et écrit les fichiers
python3 scripts/generate-article.py --rewrite mon-slug   # régénère un article
```

Sans clé API, pour vérifier uniquement la mécanique (gabarit, JSON-LD, sitemap,
RSS) avec du texte factice :

```bash
python3 scripts/generate-article.py --dry-run --mock
```

---

## 4. Volume et rattrapage

| Réglage | Valeur |
|---|---|
| Cible annoncée au modèle | **1200 à 1500 mots** (corps, FAQ exclue) |
| Bornes de rejet | 900 à 1900 mots |
| Appels OpenAI maximum par article | **3** |

Le compte de mots porte sur le **contenu**, pas sur le HTML : ni balises ni
en-tête de page ne gonflent le total.

Si la copie rendue est hors cible — ou porte n'importe quelle autre erreur que
le modèle peut corriger lui-même (maillage interne absent, nombre de questions
faux, `title` trop long) — le script relance en joignant un message de reprise
ciblé, dans la limite de 3 appels. Chaque reprise repart de la **meilleure**
copie obtenue jusque-là, pas de la dernière : le modèle développe alors un texte
déjà long au lieu de repartir d'un plus court.

Si des erreurs subsistent au bout des 3 appels, **rien n'est écrit** et le job
échoue.

---

## 5. Ce que le script écrit

| Fichier | Modification |
|---|---|
| `blog/<slug>/index.html` | L'article, créé |
| `blog/index.html` | Une carte en tête de `.blog-grille` + entrée JSON-LD |
| `sitemap.xml` | Une URL ajoutée, `lastmod` de `/blog/` rafraîchi |
| `rss.xml` | Un `<item>` en tête de flux |
| `llms.txt` | Une ligne sous « ## Articles » |

**Aucun article existant, aucune page du site n'est modifié** — sauf en mode
`--rewrite`, qui ne touche que l'article visé et ses deux entrées.

---

## 6. Codes de sortie

| Code | Signification | Effet sur le workflow |
|---|---|---|
| `0` | Article généré | Commit + push |
| `78` | Aucun sujet restant | Succès, rien n'est publié |
| `1` | Erreur (API indisponible, contenu invalide, dossier existant…) | Job en échec, **aucun fichier modifié** |

Le script valide en deux temps, **avant** toute écriture :

- `validate_content()` sur le JSON du modèle : champs présents, longueur du
  `title`, meta description sous 155 caractères, nombre de questions, maillage
  interne, volume.
- `validate_assembled()` sur la page fabriquée : DOCTYPE, `</html>`, un seul
  `<h1>`, canonical correct, 3 blocs JSON-LD parsables, FAQ du JSON-LD identique
  à la FAQ visible, feuilles de style liées, marqueur présent.

---

## 7. Idempotence

Chaque article généré porte un marqueur invisible juste après `<body>` :

```html
<!-- birdhunter65-topic: 4 -->
```

Au démarrage, le script scanne `blog/*/index.html`, relève ces marqueurs et les
noms de dossiers, puis choisit le premier sujet **non traité**. Rejouer le
workflow ne peut donc jamais réécrire ni écraser un article existant : au pire,
il sort en `78`. Seul `--rewrite` écrase, et uniquement le slug demandé.

Le slug vient du tableau de `BLOG_WORKFLOW.md`, colonne entre accents graves :
il est stable dans le temps, quelle que soit la reformulation du titre par
le modèle.

---

## 8. Le gabarit : `split_template()`

Le gabarit **n'est pas dans le script**. Il est relu à chaque exécution depuis
l'article désigné par `reference_article_slug` dans `blog-config.json` —
aujourd'hui `blog/chasse-petit-gibier-tournay-comprendre-le-terrain/index.html`.

`split_template()` est **adapté aux conventions HTML de ce site** :

| Élément | Convention ici |
|---|---|
| Blocs JSON-LD | introduits par un commentaire décoratif « DONNÉES STRUCTURÉES » |
| `<main>` | porte des attributs : `<main id="contenu" class="page-blog article-page">` |
| Conteneur | `<div class="container">` puis `<article class="article-carte">` |
| Fil d'Ariane | `<nav class="fil-ariane"><ol>…</ol></nav>` |
| Corps | `<div class="article-corps">`, indentation à 8 espaces |
| FAQ | `<div class="faq-item"><h3>Q</h3><p>R</p></div>` |
| Rappel contact | `<aside class="article-cta">` |
| Retour | `<p class="article-retour">` |
| Carte du blog | `.blog-grille` / `.blog-carte` |
| `llms.txt` | section `## Articles` |

Pour changer la mise en page de tous les futurs articles, modifiez l'article de
référence : les suivants suivront. Si un repère disparaît du gabarit, le script
s'arrête avec un message explicite plutôt que de produire une page cassée.
Après toute modification du gabarit, lancez un `--dry-run --mock`.

---

## 9. Coût estimé

Modèle `gpt-4o`, un article par semaine, 1 à 3 appels selon le rattrapage.

| | |
|---|---|
| Jetons par appel | ~2 000 en entrée, ~4 000 en sortie |
| Coût par appel | environ 0,045 $ |
| Coût par article (2 appels en moyenne) | **environ 0,09 $** |
| Coût annuel (52 articles) | **environ 5 $** |

Les minutes GitHub Actions sont gratuites sur un dépôt public.

> Tarifs OpenAI à la date de mise en place. Vérifiez
> <https://openai.com/api/pricing/> : l'ordre de grandeur reste faible, mais les
> prix évoluent.

---

## 10. Quand les 12 sujets sont épuisés

Le workflow sortira en `78` chaque lundi, sans rien publier ni casser.
Pour relancer la production, ajoutez des lignes au tableau de la section
**« Douze sujets d'articles prêts à écrire »** de `BLOG_WORKFLOW.md`, en gardant
exactement le même format :

```
| 13 | Titre du nouveau sujet | `slug-du-nouveau-sujet` | période |
```
