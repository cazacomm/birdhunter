# Bird Hunter 65 — birdhunter65.fr

Site vitrine du domaine de chasse privée **Bird Hunter**, à Tournay (Hautes-Pyrénées).
Site statique, hébergé sur **GitHub Pages** (domaine personnalisé via le fichier `CNAME`).

## Structure des fichiers

```
index.html              Page d'accueil (tout le contenu du site)
mentions-legales.html   Mentions légales
assets/style.css        Toute la mise en forme
assets/script.js        Menu mobile, animations, envoi du formulaire
imagesbirdhunter/       Photos, logo, icône Facebook
CNAME                   Domaine personnalisé (birdhunter65.fr)
sitemap.xml, robots.txt Référencement
404.html                Page affichée sur un lien mort
favicon*, *.png, *.svg  Icônes du site (onglet navigateur, mobile)
site.webmanifest        Configuration application mobile
```

## Modifier le site

| Ce que vous voulez changer | Où |
|---|---|
| Un tarif, un texte, une offre | `index.html` |
| Ajouter / modifier un avis client | `index.html`, section `AVIS` — dupliquez un bloc `<article class="avis">` |
| Les couleurs | `assets/style.css`, tout en haut (section `VARIABLES`) |
| Une photo | remplacez le fichier dans `imagesbirdhunter/` en gardant le même nom |
| Le numéro de téléphone | `index.html` — chercher `0609276288` (plusieurs occurrences) |

## Formulaire de contact

Le formulaire utilise **Web3Forms** (gratuit, aucun serveur nécessaire). **Il est actif.**
Les messages arrivent sur l'adresse configurée dans le compte Web3Forms.

Pour changer de destinataire, créer un nouveau formulaire sur https://web3forms.com
et remplacer la clé dans `index.html` :

```html
<input type="hidden" name="access_key" value="..." />
```

Champs transmis : nom, e-mail, téléphone, formule souhaitée, message.
Un piège anti-robots (`botcheck`) est en place.

## Mettre en ligne

```bash
git add .
git commit -m "Mise à jour du site"
git push
```

GitHub Pages publie automatiquement en 1 à 2 minutes.

## Crédits photos

Photographies d'illustration issues d'**Unsplash** (licence libre, usage commercial autorisé).
Voir `CREDITS-PHOTOS.md` pour le détail.
