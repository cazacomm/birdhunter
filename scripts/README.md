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

## 1. Installer la clé API (à faire une seule fois)

1. Créez une clé sur <https://platform.openai.com/api-keys>
2. Dans le dépôt GitHub : **Settings → Secrets and variables → Actions → New repository secret**
3. Nom exact : `OPENAI_API_KEY` — valeur : la clé (elle commence par `sk-`)

Vérifiez aussi, dans **Settings → Actions → General → Workflow permissions**,
que l'option **Read and write permissions** est cochée : sans elle, le robot ne
peut pas pousser l'article.

> La clé n'apparaît jamais dans le dépôt ni dans les journaux d'exécution.
> Pour la remplacer, modifiez le secret : aucun fichier n'est à toucher.

---

## 2. Lancer une génération à la main

Onglet **Actions → Blog — article automatique → Run workflow**. Deux options :

- **Test à blanc** : le script rédige l'article et affiche le résultat dans le
  journal, mais n'écrit et ne publie rien. À utiliser pour vérifier la qualité.
- **Forcer un sujet** : entrez un numéro du tableau (1 à 12) pour publier ce
  sujet plutôt que le suivant dans l'ordre.

### En local

```bash
pip install openai
export OPENAI_API_KEY="sk-..."

python3 scripts/generate-article.py --dry-run   # aperçu, rien n'est écrit
python3 scripts/generate-article.py             # génère et écrit les fichiers
python3 scripts/generate-article.py --topic 4   # force le sujet n°4
```

Sans clé API, pour vérifier uniquement la mécanique (gabarit, JSON-LD, sitemap,
RSS) avec du texte factice :

```bash
python3 scripts/generate-article.py --dry-run --mock
```

---

## 3. Ce que le script écrit

| Fichier | Modification |
|---|---|
| `blog/<slug>/index.html` | L'article, créé |
| `blog/index.html` | Une carte ajoutée en tête de grille + entrée JSON-LD |
| `sitemap.xml` | Une URL ajoutée, `lastmod` de `/blog/` rafraîchi |
| `rss.xml` | Un `<item>` en tête de flux |
| `llms.txt` | Une ligne sous « ## Articles » |

**Aucun article existant, aucune page du site n'est modifié.**

---

## 4. Codes de sortie

| Code | Signification | Effet sur le workflow |
|---|---|---|
| `0` | Article généré | Commit + push |
| `78` | Aucun sujet restant | Succès, rien n'est publié |
| `1` | Erreur (API indisponible, contenu invalide, dossier existant…) | Job en échec, **aucun fichier modifié** |

Le script valide tout **avant** d'écrire : JSON-LD parsable, meta description
sous 155 caractères, FAQ du JSON-LD identique à la FAQ visible, marqueur
d'idempotence présent, longueur de l'article suffisante. Si une seule
vérification échoue, rien n'est écrit et le job s'arrête en erreur.

---

## 5. Idempotence

Chaque article généré porte un marqueur invisible juste après `<body>` :

```html
<!-- birdhunter65-topic: 4 -->
```

Au démarrage, le script scanne `blog/*/index.html`, relève ces marqueurs et les
noms de dossiers, puis choisit le premier sujet **non traité**. Rejouer le
workflow ne peut donc jamais réécrire ni écraser un article existant : au pire,
il sort en `78`.

---

## 6. Coût estimé

Modèle `gpt-4o-mini`, un article par semaine.

| | |
|---|---|
| Jetons par article | ~1 000 en entrée, ~2 500 en sortie |
| Coût par article | **environ 0,002 $** (moins d'un quart de centime) |
| Coût sur 12 articles | **environ 0,03 $** |
| Coût annuel (52 articles) | **environ 0,10 $** |

Les minutes GitHub Actions sont gratuites sur un dépôt public ; l'exécution
dure moins d'une minute.

> Tarifs OpenAI à la date de mise en place. Vérifiez
> <https://openai.com/api/pricing/> si le budget compte : l'ordre de grandeur
> restera négligeable, mais les prix évoluent.

---

## 7. Quand les 12 sujets sont épuisés

Le workflow sortira en `78` chaque lundi, sans rien publier ni casser.
Pour relancer la production, ajoutez des lignes au tableau de la section
**« Douze sujets d'articles prêts à écrire »** de `BLOG_WORKFLOW.md`, en gardant
exactement le même format :

```
| 13 | Titre du nouveau sujet | `slug-du-nouveau-sujet` | période |
```

---

## 8. Modifier le gabarit des articles

Le gabarit **n'est pas dans le script**. Il est relu à chaque exécution depuis
l'article désigné par `template_article` dans `blog-config.json` — aujourd'hui
`blog/chasse-petit-gibier-tournay-comprendre-le-terrain/index.html`.

Pour changer la mise en page de tous les futurs articles, modifiez cet
article de référence : les suivants suivront. Le script s'appuie sur des
repères précis de ce fichier (`<div class="article-corps">`, `faq-bloc`,
`article-chapo`, les trois blocs JSON-LD…). Si vous en supprimez un, le script
s'arrête avec un message explicite plutôt que de produire une page cassée.
Après toute modification du gabarit, lancez un `--dry-run --mock` pour vérifier.
