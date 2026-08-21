#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Génération automatique d'un article de blog — Bird Hunter 65.

Le script :
  1. lit blog-config.json ;
  2. extrait de BLOG_WORKFLOW.md le tableau des sujets et les règles de contenu ;
  3. scanne /blog/*/index.html pour savoir quels sujets sont déjà traités ;
  4. choisit le prochain sujet non traité (ordre séquentiel du tableau) ;
  5. relit l'article de référence pour s'en servir de gabarit HTML ;
  6. demande à l'API OpenAI le seul CONTENU éditorial, en JSON structuré
     (titre, chapô, sections h2/h3, paragraphes, listes, FAQ) ;
  7. valide ce contenu, puis ASSEMBLE lui-même la page : head, meta, canonical,
     Open Graph, Twitter Card, les trois blocs JSON-LD, le fil d'Ariane, le
     marqueur d'idempotence, l'en-tête et le pied de page viennent du gabarit et
     du script — jamais du modèle ;
  8. écrit /blog/<slug>/index.html, puis met à jour blog/index.html,
     sitemap.xml, rss.xml et llms.txt.

Le modèle n'écrit donc pas une ligne de HTML. Auparavant il régénérait toute la
page : les deux tiers de ses tokens de sortie partaient en balisage, ce qui
plafonnait le corps rédigé bien en dessous de la cible.

Codes de sortie :
   0  succès
   1  erreur (rien n'a été écrit)
  78  aucun nouveau sujet à traiter (arrêt propre)

Options :
  --dry-run       n'écrit aucun fichier, affiche le résultat
  --mock          n'appelle pas l'API (contenu de démonstration)
  --rewrite SLUG  régénère un article existant et écrase son fichier
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "blog-config.json"
WORKFLOW_PATH = ROOT / "BLOG_WORKFLOW.md"
BLOG_DIR = ROOT / "blog"
BLOG_INDEX = BLOG_DIR / "index.html"
SITEMAP = ROOT / "sitemap.xml"
RSS = ROOT / "rss.xml"
LLMS = ROOT / "llms.txt"

EXIT_OK, EXIT_ERROR, EXIT_NOTHING_TODO = 0, 1, 78

# Volume du corps rédigé, FAQ exclue, compté sur le contenu et non sur le HTML.
#  · PROMPT_MIN/MAX_WORDS : la cible, annoncée au modèle et seuil de rattrapage.
#  · MIN/MAX_WORDS        : bornes de validation, plus larges (tolérance ±30 %).
MIN_WORDS, MAX_WORDS = 900, 1900
PROMPT_MIN_WORDS, PROMPT_MAX_WORDS = 1200, 1500

# Nombre maximal d'appels OpenAI pour un article, rattrapages compris.
MAX_CALLS = 3

# Les 19 clés que blog-config.json doit obligatoirement fournir.
REQUIRED_KEYS = (
    "site_name", "site_url", "sector", "location", "geo_keywords", "tone",
    "author", "target_word_count", "faq_questions_count", "language", "model",
    "temperature", "topic_marker_prefix", "og_image", "logo_path",
    "default_article_section", "internal_link_targets",
    "reference_article_slug", "facts",
)

MONTHS_FR = ["janvier", "février", "mars", "avril", "mai", "juin",
             "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
DAYS_EN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MONTHS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
             "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

STOPWORDS = {
    "le", "la", "les", "un", "une", "des", "du", "de", "d", "l", "et", "ou", "a", "au",
    "aux", "en", "dans", "sur", "pour", "par", "avec", "sans", "que", "qui", "quoi",
    "ce", "cet", "cette", "ces", "se", "sa", "son", "ses", "nos", "notre", "votre",
    "vos", "est", "ne", "pas", "plus", "tout", "tous", "toute", "toutes", "y", "il",
    "elle", "on", "vraiment", "bien",
}


# ─────────────────────────────────────────────────────────────
# Utilitaires
# ─────────────────────────────────────────────────────────────

def log(msg: str) -> None:
    print(f"[blog] {msg}", flush=True)


def fail(msg: str) -> None:
    print(f"[blog][ERREUR] {msg}", file=sys.stderr, flush=True)


def strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", text)
                   if unicodedata.category(c) != "Mn")


def slugify(title: str, max_words: int = 7) -> str:
    """Slug déterministe : même titre => même slug (garantit l'idempotence).
    Sert de repli quand le tableau de BLOG_WORKFLOW.md ne déclare pas de slug."""
    text = strip_accents(title.lower())
    text = text.replace("'", " ").replace("’", " ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    words = [w for w in text.split() if w and w not in STOPWORDS]
    if not words:
        words = [w for w in text.split() if w]
    return "-".join(words[:max_words])


def esc(text: str) -> str:
    """Échappement HTML. Tout le contenu du modèle passe par là : il fournit du
    texte brut, jamais du markup, ce qui rend une injection HTML impossible."""
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def inline(text: str) -> str:
    """Rend le balisage inline autorisé dans le texte du modèle, après
    échappement : **gras** et [libellé](/chemin-interne).

    Les liens sont restreints aux chemins commençant par « / » : le maillage
    interne reste possible, un lien externe devient structurellement impossible."""
    out = esc(text)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"\[([^\]]+)\]\((/[^)\s]*)\)", r'<a href="\2">\1</a>', out)
    return out


def plain(text: str) -> str:
    """Texte débarrassé du balisage inline — pour les JSON-LD et les meta."""
    out = re.sub(r"\*\*(.+?)\*\*", r"\1", str(text))
    return re.sub(r"\[([^\]]+)\]\((/[^)\s]*)\)", r"\1", out)


def content_word_count(data: dict) -> int:
    """Volume rédactionnel du corps, FAQ exclue — compté sur le contenu lui-même
    et non sur du HTML : plus de balises ni de boilerplate dans le total."""
    words = len(plain(data.get("lede", "")).split())
    for section in data.get("sections", []):
        words += len(plain(section.get("h2", "")).split())
        for block in section.get("content", []):
            words += len(plain(block.get("text", "")).split())
            for item in block.get("items", []) or []:
                words += len(plain(item).split())
    return words


def fr_date(d: dt.date) -> str:
    return f"{d.day} {MONTHS_FR[d.month - 1]} {d.year}"


def rfc822(d: dt.date, hour: str = "08:00:00") -> str:
    return (f"{DAYS_EN[d.weekday()]}, {d.day:02d} {MONTHS_EN[d.month - 1]} "
            f"{d.year} {hour} +0200")


# ─────────────────────────────────────────────────────────────
# Lecture de la configuration et du workflow
# ─────────────────────────────────────────────────────────────

def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Configuration introuvable : {CONFIG_PATH}")
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    missing = [k for k in REQUIRED_KEYS if not cfg.get(k)]
    if missing:
        raise ValueError("Clé(s) manquante(s) ou vide(s) dans blog-config.json : "
                         + ", ".join(missing))
    cfg["site_url"] = cfg["site_url"].rstrip("/")
    return cfg


def parse_topics(workflow: str) -> list[dict]:
    """Extrait les sujets du tableau de BLOG_WORKFLOW.md.

    Convention propre à ce site — le tableau markdown de la section
    « Douze sujets d'articles prêts à écrire » :

        | 1 | Titre du sujet | `slug-du-sujet` | juin – août |

    Le slug déclaré entre accents graves fait autorité : c'est lui qui sera
    utilisé pour le dossier de l'article, afin de respecter la convention de
    nommage déjà en place sur le site."""
    rows = re.compile(
        r"^\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*`([a-z0-9-]+)`\s*\|\s*(.*?)\s*\|\s*$")
    topics: list[dict] = []
    for line in workflow.splitlines():
        m = rows.match(line.strip())
        if not m:
            continue
        title = re.sub(r"[`*]", "", m.group(2)).strip()
        topics.append({
            "num": int(m.group(1)),
            "title": title,
            "brief": f"Angle saisonnier : {m.group(4).strip()}." if m.group(4) else "",
            "declared_slug": m.group(3).strip(),
        })
    if not topics:
        raise ValueError(
            "Aucun sujet exploitable dans BLOG_WORKFLOW.md. Le tableau doit rester "
            "au format « | n | sujet | `slug` | période | ».")
    topics.sort(key=lambda t: t["num"])
    return topics


def parse_editorial_rules(workflow: str) -> str:
    """Récupère la section des règles de contenu pour l'injecter dans le prompt.
    Le titre exact diffère d'un site à l'autre : on accepte les deux libellés."""
    m = re.search(
        r"^##\s+\d+\.\s+.*(?:règles de contenu|règles éditoriales).*?$(.*?)^##\s",
        workflow, flags=re.M | re.S | re.I)
    return m.group(1).strip() if m else ""


# ─────────────────────────────────────────────────────────────
# État du blog
# ─────────────────────────────────────────────────────────────

def scan_blog(marker_prefix: str) -> tuple[set[int], set[str]]:
    """Retourne (numéros de sujets déjà traités, slugs existants)."""
    done_nums: set[int] = set()
    slugs: set[str] = set()
    if not BLOG_DIR.exists():
        return done_nums, slugs
    for path in sorted(BLOG_DIR.glob("*/index.html")):
        slugs.add(path.parent.name)
        html = path.read_text(encoding="utf-8", errors="replace")
        m = re.search(rf"<!--\s*{re.escape(marker_prefix)}:\s*(\d+)\s*-->", html)
        if m:
            done_nums.add(int(m.group(1)))
    return done_nums, slugs


def pick_topic(topics: list[dict], done_nums: set[int], slugs: set[str]) -> dict | None:
    """Premier sujet non traité, dans l'ordre du tableau."""
    for topic in topics:
        if topic["num"] in done_nums:
            continue
        slug = topic["declared_slug"] or slugify(topic["title"])
        if slug in slugs:
            # Le dossier existe déjà : sujet considéré traité (idempotence).
            continue
        topic["slug"] = slug
        return topic
    return None


def load_reference_article(cfg: dict, slugs: set[str]) -> tuple[str, str]:
    """Relit un article existant : il sert de gabarit (jamais de template en dur)."""
    preferred = cfg.get("reference_article_slug")
    candidates = [preferred] if preferred in slugs else []
    candidates += sorted(s for s in slugs if s != preferred)
    for slug in candidates:
        path = BLOG_DIR / slug / "index.html"
        if path.exists():
            return slug, path.read_text(encoding="utf-8")
    raise FileNotFoundError(
        "Aucun article de référence dans /blog/ : impossible de déduire le gabarit.")


def pick_image(cfg: dict, topic: dict) -> str:
    """Illustration de l'article : rotation déterministe sur le pool configuré,
    indexée par le numéro de sujet. Repli sur l'image Open Graph du site."""
    pool = cfg.get("image_pool") or []
    if not pool:
        return cfg["og_image"]
    return pool[(topic["num"] - 1) % len(pool)]


# ─────────────────────────────────────────────────────────────
# Rédaction : le modèle ne produit QUE du contenu éditorial
# ─────────────────────────────────────────────────────────────

def volume_rank(errors: list[str], wc: int) -> tuple[int, int]:
    """Clé de comparaison entre deux copies : celle qui a le moins d'erreurs
    prime, puis on préfère celle qui approche le mieux la cible."""
    deficit = max(0, PROMPT_MIN_WORDS - wc)
    excess = max(0, wc - MAX_WORDS)
    return (len(errors), deficit + excess)


def build_correction(cfg: dict, errors: list[str], wc: int) -> str:
    """Message de reprise adressé au modèle. Il ne porte pas seulement sur le
    volume : toute erreur de validation que le modèle peut corriger lui-même
    (maillage interne, nombre de questions, longueur du title) y passe, tant
    qu'il reste des appels au budget."""
    demands = []
    if wc < PROMPT_MIN_WORDS:
        demands.append(
            f"Tu as généré {wc} mots pour le corps (FAQ exclue), il en faut au moins "
            f"{PROMPT_MIN_WORDS}. Développe chaque section : ajoute des paragraphes, "
            "des exemples concrets, du contexte local, des nuances. Ne retire aucune "
            "section.")
    elif wc > MAX_WORDS:
        demands.append(
            f"Tu as généré {wc} mots pour le corps (FAQ exclue), c'est trop : il en "
            f"faut au plus {PROMPT_MAX_WORDS}. Resserre chaque section sans en "
            "supprimer aucune.")

    if any("maillage" in e for e in errors):
        targets = "\n".join(f"  {t}" for t in cfg["internal_link_targets"])
        demands.append(
            "Il manque des liens internes, c'est rédhibitoire. Insère dans le corps "
            "au moins DEUX liens markdown vers ces chemins exacts, placés dans deux "
            f"sections différentes :\n{targets}\net au moins UN lien vers /blog/. "
            f"Écris-les sous la forme [libellé descriptif]({cfg['internal_link_targets'][0]}), "
            "en recopiant le chemin tel quel. Ne touche à rien d'autre.")

    others = [e for e in errors if "maillage" not in e and "volume" not in e]
    if others:
        demands.append("Corrige aussi ces points : " + " ; ".join(others) + ".")

    if not demands:
        demands.append("Reprends ton JSON en respectant toutes les consignes.")
    return " ".join(demands) + " Réponds par le seul objet JSON complet."


def build_prompt(cfg: dict, topic: dict, rules: str) -> tuple[str, str]:
    """Prompt court : plus de gabarit HTML à recopier, plus de contraintes de
    balisage. Le modèle écrit, le script fabrique la page."""
    targets = cfg["internal_link_targets"]
    targets_bullets = "\n".join(f"    {t}" for t in targets)

    system = f"""Tu es rédacteur SEO/GEO senior pour une entreprise locale française.
Tu écris du CONTENU, jamais du HTML : la mise en page est faite par ailleurs.

Tu réponds UNIQUEMENT par un objet JSON valide, sans bloc de code markdown,
respectant exactement ce schéma :

{{
  "title": "titre de la page, 55 à 60 caractères, sans le nom du site",
  "h1": "titre affiché en haut de l'article, court et percutant",
  "breadcrumb": "libellé court pour le fil d'Ariane (2 à 4 mots)",
  "meta_description": "résumé de moins de 155 caractères",
  "lede": "chapô d'introduction, 60 à 90 mots, qui plante une situation concrète",
  "image_alt": "description factuelle d'une photo d'illustration du domaine",
  "image_caption": "légende courte de cette photo, une phrase",
  "sections": [
    {{"h2": "titre de section",
      "content": [
        {{"type": "p", "text": "paragraphe"}},
        {{"type": "h3", "text": "sous-titre"}},
        {{"type": "ul", "items": ["élément", "élément"]}},
        {{"type": "ol", "items": ["étape", "étape"]}}
      ]}}
  ],
  "faq": [{{"question": "…", "answer": "…"}}]
}}

RÈGLES DE CONTENU
- Volume : le corps (lede + sections, FAQ exclue) fait entre {PROMPT_MIN_WORDS} et
  {PROMPT_MAX_WORDS} mots. Compte les mots avant de répondre. C'est la contrainte
  la plus importante : en dessous de {PROMPT_MIN_WORDS} mots, la réponse est rejetée.
- Vise 5 à 7 sections « h2 », chacune avec 3 à 5 paragraphes nourris. Un paragraphe
  fait 60 à 110 mots : développe, donne des exemples concrets, du contexte local,
  des nuances. Ne fais jamais de paragraphe d'une seule phrase.
- FAQ : exactement {{faq_count}} questions, avec des réponses de 40 à 70 mots.
  Elles ne comptent pas dans le volume du corps.
- Balisage inline autorisé dans les textes, et lui seul :
  **gras** et [libellé](/chemin). Les liens sont forcément internes.
- Maillage interne — OBLIGATOIRE, la réponse est rejetée sans cela :
  place AU MOINS DEUX liens markdown vers ces chemins exacts, dans deux
  sections différentes du corps :
{targets_bullets}
  et AU MOINS UN lien vers /blog/.
  Forme attendue, à recopier telle quelle : [libellé descriptif]({targets[0]})
  Recopie les chemins sans les modifier, sans domaine et sans rien y ajouter.
- Ancres de liens : les libellés des liens internes doivent être descriptifs et
  se lire naturellement dans la phrase. Interdit : les libellés secs d'un seul
  mot comme « ici », « blog », « offres », « contact ».

GARDE-FOUS — NON NÉGOCIABLES
N'invente AUCUN prix, AUCUN tarif, AUCUN chiffre d'affaires ou de fréquentation,
AUCUN nom de client, AUCUN témoignage, AUCUNE date de fondation, AUCUNE norme,
AUCUNE réglementation datée, AUCUN quota légal, AUCUN label, AUCUN avis client,
AUCUN horaire et AUCUNE adresse autres que ceux fournis ci-dessous.
Si une information te manque, reformule pour t'en passer : une phrase vague et
vraie vaut mieux qu'une phrase précise et fausse.
Ne cite jamais un tarif dans le corps : renvoie le lecteur vers la page des offres.
Sur la réglementation de la chasse, une seule formulation est autorisée :
« permis de chasser en cours de validité et assurance responsabilité civile
chasse obligatoires ». N'ajoute aucun texte de loi, aucune date, aucun quota.

FAITS AUTORISÉS (seule source de faits chiffrés, d'adresses et d'horaires)
{{facts}}
""".replace("{faq_count}", str(cfg["faq_questions_count"])).replace(
        "{facts}", "\n".join(f"- {f}" for f in cfg.get("facts", [])))

    user = f"""Sujet n°{topic['num']} : {topic['title']}
Angle : {topic['brief'] or "à développer librement dans le cadre des règles"}

Entreprise : {cfg['site_name']} — {cfg['sector']}.
Zone : {cfg['location']}.
Ton : {cfg['tone']}. Langue : français.

Mots-clés géographiques à faire vivre naturellement (pas de bourrage) :
{', '.join(cfg['geo_keywords'])}.

RÈGLES ÉDITORIALES DU BLOG
{rules}

Réponds par le seul objet JSON."""

    return system, user


def generate_content(cfg: dict, system: str, user: str,
                     followup: list[dict] | None = None) -> dict:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise RuntimeError(
            "Le paquet 'openai' n'est pas installé (pip install openai).") from exc

    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("Variable d'environnement OPENAI_API_KEY absente.")

    client = OpenAI()
    log(f"Appel OpenAI (modèle {cfg['model']}, temperature {cfg['temperature']})…")
    response = client.chat.completions.create(
        model=cfg["model"],
        temperature=cfg["temperature"],
        max_tokens=9000,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
            *(followup or []),
        ],
    )
    content = (response.choices[0].message.content or "").strip()
    usage = getattr(response, "usage", None)
    if usage:
        log(f"Tokens : {usage.prompt_tokens} entrée + "
            f"{usage.completion_tokens} sortie = {usage.total_tokens}")
    if not content:
        raise ValueError("réponse vide")
    return json.loads(content)


def mock_content(cfg: dict, topic: dict) -> dict:
    """Contenu de démonstration pour --mock : même forme que la sortie du modèle,
    calibré pour dépasser la cible de volume."""
    filler = ("Sur le piémont pyrénéen, la question se pose différemment selon le moment "
              "de la saison et le temps qu'il fait le matin même. Entre Tournay, Tarbes et "
              "Lannemezan, les distances restent courtes, ce qui change beaucoup de choses "
              "dans la manière d'organiser une journée de chasse. Les habitudes des uns et "
              "des autres varient, et c'est précisément pour cela qu'il vaut la peine de "
              "détailler chaque cas de figure plutôt que de donner une réponse unique qui "
              "ne conviendrait qu'à une minorité des situations rencontrées sur le terrain.")
    sections = []
    for i in range(7):          # 7 sections : le mock dépasse la cible de 1200
        content = [{"type": "p", "text": filler}, {"type": "p", "text": filler}]
        if i == 0:
            content.insert(1, {"type": "h3", "text": "Un point de départ concret"})
            content.append({"type": "p",
                            "text": "Le détail des formules figure sur "
                                    "[la page de nos offres](/#offres) et la "
                                    "présentation du terrain sur "
                                    "[la page du domaine](/#domaine)."})
        if i == 1:
            content.append({"type": "ul", "items": ["Premier repère utile",
                                                    "Deuxième repère utile",
                                                    "Troisième repère utile"]})
        if i == 2:
            content.append({"type": "p",
                            "text": "D'autres articles sont réunis dans "
                                    "[le carnet de chasse](/blog/)."})
        sections.append({"h2": f"Section de démonstration n°{i + 1}", "content": content})
    return {
        "title": f"{topic['title'][:50]} | démo",
        "h1": topic["title"],
        "breadcrumb": topic["title"][:28],
        "meta_description": f"{topic['title'][:110]} — contenu de démonstration.",
        "lede": filler,
        "image_alt": "Photo d'illustration du domaine de chasse Bird Hunter à Tournay",
        "image_caption": "Le domaine, à Tournay (65), à quinze minutes de Tarbes.",
        "sections": sections,
        "faq": [{"question": f"Question de démonstration n°{i + 1} ?",
                 "answer": filler[:220]} for i in range(cfg["faq_questions_count"])],
    }


# ─────────────────────────────────────────────────────────────
# Validation du contenu
# ─────────────────────────────────────────────────────────────

CONTENT_TYPES = {"p", "h3", "ul", "ol", "strong"}


def validate_content(data: dict, cfg: dict) -> list[str]:
    """Contrôles bloquants sur le CONTENU. Tout ce que le script fabrique
    lui-même (canonical, OG, JSON-LD, marqueur, fil d'Ariane, structure) ne peut
    plus être erroné et n'est donc plus contrôlé ici."""
    errors: list[str] = []

    if not isinstance(data, dict):
        return ["la réponse n'est pas un objet JSON"]

    for key in ("title", "h1", "breadcrumb", "meta_description", "lede"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            errors.append(f"champ « {key} » absent ou vide")

    title = data.get("title", "")
    if isinstance(title, str) and not 40 <= len(title) <= 70:
        errors.append(f"title hors bornes : {len(title)} caractères (attendu 40–70)")

    desc = data.get("meta_description", "")
    if isinstance(desc, str) and len(desc) >= 155:
        errors.append(f"meta description trop longue ({len(desc)} caractères)")

    sections = data.get("sections")
    if not isinstance(sections, list) or not sections:
        errors.append("aucune section")
    else:
        for i, section in enumerate(sections, 1):
            if not isinstance(section, dict) or not section.get("h2"):
                errors.append(f"section n°{i} sans titre h2")
                continue
            blocks = section.get("content")
            if not isinstance(blocks, list) or not blocks:
                errors.append(f"section n°{i} sans contenu")
                continue
            for block in blocks:
                if not isinstance(block, dict):
                    errors.append(f"section n°{i} : bloc de contenu invalide")
                    continue
                kind = block.get("type")
                if kind not in CONTENT_TYPES:
                    errors.append(f"section n°{i} : type de bloc inconnu ({kind!r})")
                elif kind in ("ul", "ol"):
                    if not (block.get("items") or block.get("text")):
                        errors.append(f"section n°{i} : liste {kind} vide")
                elif not block.get("text"):
                    errors.append(f"section n°{i} : bloc {kind} sans texte")

    faq = data.get("faq")
    if not isinstance(faq, list) or len(faq) != cfg["faq_questions_count"]:
        errors.append(f"{cfg['faq_questions_count']} questions attendues dans la FAQ "
                      f"(trouvé : {len(faq) if isinstance(faq, list) else 0})")
    else:
        for i, item in enumerate(faq, 1):
            if not isinstance(item, dict) or not item.get("question") or not item.get("answer"):
                errors.append(f"question de FAQ n°{i} incomplète")

    # Maillage interne : toujours dépendant du modèle, donc toujours contrôlé.
    body = " ".join(
        [data.get("lede", "")] +
        [b.get("text", "") + " " + " ".join(b.get("items") or [])
         for s in (sections if isinstance(sections, list) else [])
         if isinstance(s, dict)
         for b in (s.get("content") or []) if isinstance(b, dict)])
    links = re.findall(r"\[[^\]]+\]\((/[^)\s]*)\)", body)
    targets = cfg["internal_link_targets"]
    if sum(1 for h in links if h in targets) < 2:
        errors.append("maillage interne : moins de deux liens vers "
                      + " ou ".join(targets))
    if not any(h.startswith("/blog") for h in links):
        errors.append("maillage interne : aucun lien vers /blog/")

    wc = content_word_count(data)
    if not MIN_WORDS <= wc <= MAX_WORDS:
        errors.append(f"volume hors bornes : {wc} mots (attendu {MIN_WORDS}–{MAX_WORDS})")

    return errors


# ─────────────────────────────────────────────────────────────
# Assemblage du HTML à partir du gabarit
# ─────────────────────────────────────────────────────────────

def split_template(reference_html: str) -> dict:
    """Découpe le gabarit relu en morceaux réutilisables.

    ADAPTÉ AUX CONVENTIONS HTML DE CE SITE. Le gabarit de Bird Hunter diffère
    de celui d'autres sites du parc sur plusieurs points, tous pris en compte
    ici sans qu'une seule ligne du gabarit n'ait à être modifiée :

      · les blocs JSON-LD sont introduits par un commentaire décoratif
        (« DONNÉES STRUCTURÉES »), et non par un simple « <!-- Article --> » ;
      · <main> porte des attributs : <main id="contenu" class="page-blog …"> ;
      · le corps de l'article est enveloppé dans
        <div class="container"> puis <article class="article-carte"> ;
      · le fil d'Ariane est un <nav class="fil-ariane"><ol>…</ol></nav>,
        pas un <p class="breadcrumb"> ;
      · le bloc de rappel est un <aside class="article-cta">, pas un <div> ;
      · un lien de retour <p class="article-retour"> ferme le conteneur.
    """
    parts: dict[str, str] = {}

    # ── <head> : on s'arrête au commentaire qui introduit le premier JSON-LD.
    first_ld = reference_html.find('<script type="application/ld+json">')
    head_end = reference_html.find("</head>")
    if first_ld == -1 or head_end == -1:
        raise ValueError("Gabarit : bloc JSON-LD ou </head> introuvable.")
    # Le commentaire décoratif qui précède le script fait partie de l'en-tête à
    # remplacer : on remonte jusqu'à son ouverture si elle est proche.
    comment = reference_html.rfind("<!--", 0, first_ld)
    ld_start = first_ld
    if comment != -1 and reference_html.count("\n", comment, first_ld) <= 4:
        line_start = reference_html.rfind("\n", 0, comment)
        ld_start = line_start + 1 if line_start != -1 else comment
    parts["head_top"] = reference_html[:ld_start]

    # ── Corps : header de site, <main …>, footer.
    main_start = reference_html.find("<main")
    main_end = reference_html.find("</main>")
    if main_start == -1 or main_end == -1:
        raise ValueError("Gabarit : <main> ou </main> introuvable.")
    parts["header"] = reference_html[head_end + len("</head>"):main_start]
    parts["footer"] = reference_html[main_end:]

    # La balise <main> est recopiée telle quelle, attributs compris.
    tag_end = reference_html.find(">", main_start)
    if tag_end == -1:
        raise ValueError("Gabarit : balise <main> mal formée.")
    parts["main_tag"] = reference_html[main_start:tag_end + 1]

    inner = reference_html[main_start:main_end]

    # ── Blocs repris tels quels : rappel contact et lien de retour.
    cta = re.search(r'(<!--[^\n]*-->\n\s*)?<aside class="article-cta">.*?</aside>',
                    inner, re.S)
    parts["cta"] = cta.group().strip() if cta else ""

    retour = re.search(r'<p class="article-retour">.*?</p>', inner, re.S)
    parts["retour"] = retour.group().strip() if retour else ""

    return parts


def build_head(parts: dict, cfg: dict, data: dict, url: str,
               today: dict, image: str) -> str:
    """Reprend le <head> du gabarit et n'y remplace que ce qui est propre à
    l'article. Les valeurs viennent du script, jamais du modèle en HTML."""
    head = parts["head_top"]
    title = f"{plain(data['title'])} | {cfg['site_name']}"
    desc = plain(data["meta_description"])
    img = f"{cfg['site_url']}{image}"
    alt = plain(data.get("image_alt") or cfg["site_name"])

    def swap(pattern: str, replacement: str, text: str) -> str:
        new, n = re.subn(pattern, lambda _: replacement, text, count=1, flags=re.S)
        if n != 1:
            raise ValueError(f"Gabarit : motif introuvable dans le <head> — {pattern}")
        return new

    head = swap(r"<title>.*?</title>", f"<title>{esc(title)}</title>", head)
    # Sur ce site la meta description est écrite sur deux lignes : le motif doit
    # tolérer le retour à la ligne et l'indentation (d'où le flag re.S ci-dessus).
    head = swap(r'<meta name="description"\s*\n?\s*content="[^"]*" />',
                '<meta name="description"\n'
                f'        content="{esc(desc)}" />', head)
    head = swap(r'<link rel="canonical" href="[^"]*" />',
                f'<link rel="canonical" href="{url}" />', head)
    for prop, value in (("og:title", plain(data["title"])),
                        ("og:description", desc),
                        ("og:url", url),
                        ("og:image", img),
                        ("og:image:alt", alt),
                        ("article:published_time", today["iso"]),
                        ("article:modified_time", today["iso"]),
                        ("article:section", cfg["default_article_section"])):
        head = swap(rf'<meta property="{re.escape(prop)}" content="[^"]*" />',
                    f'<meta property="{prop}" content="{esc(value)}" />', head)
    for name, value in (("twitter:title", plain(data["title"])),
                        ("twitter:description", desc),
                        ("twitter:image", img),
                        ("twitter:image:alt", alt)):
        head = swap(rf'<meta name="{re.escape(name)}" content="[^"]*" />',
                    f'<meta name="{name}" content="{esc(value)}" />', head)
    return head


def build_jsonld(cfg: dict, data: dict, url: str, today: dict, image: str) -> str:
    """Les trois blocs JSON-LD, sérialisés par json.dumps : ils sont valides
    par construction, ce que le modèle ne pouvait pas garantir."""
    img = f"{cfg['site_url']}{image}"
    article = {
        "@context": "https://schema.org",
        "@type": "Article",
        "@id": f"{url}#article",
        "headline": plain(data["h1"]),
        "description": plain(data["meta_description"]),
        "inLanguage": "fr-FR",
        "datePublished": today["iso"],
        "dateModified": today["iso"],
        "image": img,
        "mainEntityOfPage": {"@type": "WebPage", "@id": url},
        "author": {"@type": "Organization", "name": cfg["author"],
                   "url": f"{cfg['site_url']}/"},
        "publisher": {
            "@type": "Organization", "name": cfg["site_name"],
            "url": f"{cfg['site_url']}/",
            "logo": {"@type": "ImageObject",
                     "url": f"{cfg['site_url']}{cfg['logo_path']}"}},
        # Rattache l'article à la fiche d'établissement déclarée sur l'accueil.
        "about": {"@id": f"{cfg['site_url']}/{cfg.get('about_id', '#org')}"},
        "isPartOf": {"@id": f"{cfg['site_url']}/blog/#blog"},
        "articleSection": cfg["default_article_section"],
        "keywords": ", ".join(cfg["geo_keywords"][:6]),
    }
    breadcrumb = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Accueil",
             "item": f"{cfg['site_url']}/"},
            {"@type": "ListItem", "position": 2, "name": "Blog",
             "item": f"{cfg['site_url']}/blog/"},
            {"@type": "ListItem", "position": 3, "name": plain(data["title"]),
             "item": url},
        ],
    }
    faqpage = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": plain(q["question"]),
             "acceptedAnswer": {"@type": "Answer", "text": plain(q["answer"])}}
            for q in data["faq"]
        ],
    }
    out = []
    for comment, payload in (("Article", article), ("Fil d'Ariane", breadcrumb),
                             ("FAQ", faqpage)):
        body = json.dumps(payload, ensure_ascii=False, indent=2)
        out.append(f'  <!-- {comment} -->\n  <script type="application/ld+json">\n'
                   f'{body}\n  </script>\n')
    return "\n".join(out)


def render_blocks(blocks: list[dict]) -> str:
    """Contenu d'une section, converti en HTML. Le modèle n'écrit que du texte :
    c'est ici, et seulement ici, que le balisage apparaît.
    Indentation à 8 espaces, comme dans le gabarit du site."""
    out = []
    for block in blocks:
        kind = block.get("type")
        if kind in ("ul", "ol"):
            items = block.get("items")
            if not items:
                items = [s for s in re.split(r"\s*[;\n]\s*", block.get("text", "")) if s]
            lines = "\n".join(f"          <li>{inline(i)}</li>" for i in items)
            cls = ' class="liste"' if kind == "ul" else ""
            out.append(f"        <{kind}{cls}>\n{lines}\n        </{kind}>")
        elif kind == "h3":
            out.append(f"        <h3>{inline(block['text'])}</h3>")
        elif kind == "strong":
            out.append(f"        <p><strong>{inline(block['text'])}</strong></p>")
        else:
            out.append(f"        <p>{inline(block['text'])}</p>")
    return "\n\n".join(out)


def build_main(parts: dict, cfg: dict, data: dict, topic: dict,
               today: dict, image: str) -> str:
    """Le <main> complet, reconstruit aux conventions HTML de ce site :
    conteneur, fil d'Ariane en <nav><ol>, article-carte, en-tête, figure,
    chapô, corps, FAQ en .faq-item, puis CTA et lien de retour du gabarit."""
    body = "\n\n".join(
        f"        <h2>{inline(s['h2'])}</h2>\n\n{render_blocks(s['content'])}"
        for s in data["sections"])

    faq = "\n\n".join(
        '        <div class="faq-item">\n'
        f'          <h3>{inline(q["question"])}</h3>\n'
        f'          <p>{inline(q["answer"])}</p>\n'
        "        </div>"
        for q in data["faq"])

    alt = esc(plain(data.get("image_alt") or cfg["site_name"]))
    caption = inline(data.get("image_caption") or "")
    cta = ("\n\n      " + parts["cta"]) if parts["cta"] else ""
    retour = ("\n    " + parts["retour"] + "\n") if parts["retour"] else ""

    return f"""{parts['main_tag']}
  <div class="container">

    <!-- Fil d'Ariane -->
    <nav class="fil-ariane" aria-label="Fil d'Ariane">
      <ol>
        <li><a href="/">Accueil</a></li>
        <li><a href="/blog/">Blog</a></li>
        <li aria-current="page">{inline(data['breadcrumb'])}</li>
      </ol>
    </nav>

    <article class="article-carte">

      <header class="article-entete">
        <h1>{inline(data['h1'])}</h1>
        <div class="article-meta">
          <time datetime="{today['iso']}">{today['fr']}</time>
          <span class="sep">•</span>
          <span>{esc(cfg['default_article_section'])}</span>
          <span class="sep">•</span>
          <span>{esc(cfg['location'])}</span>
        </div>
      </header>

      <figure class="article-image">
        <img src="{esc(image)}"
             alt="{alt}"
             width="1200" height="800" />
        <figcaption>{caption}</figcaption>
      </figure>

      <p class="article-chapo">{inline(data['lede'])}</p>

      <div class="article-corps">

{body}

      </div>

      <!-- ═══ FAQ ═══ -->
      <section class="faq-bloc" aria-labelledby="faq-titre">
        <h2 id="faq-titre">Questions fréquentes</h2>

{faq}
      </section>{cta}

    </article>
{retour}
  </div>
"""


def assemble(reference_html: str, cfg: dict, topic: dict,
             data: dict, today: dict, image: str) -> str:
    """Fabrique la page complète. Toute la structure vient d'ici : le modèle
    n'a produit que du texte."""
    parts = split_template(reference_html)
    url = f"{cfg['site_url']}/blog/{topic['slug']}/"
    marker = f"<!-- {cfg['topic_marker_prefix']}: {topic['num']} -->"

    head = build_head(parts, cfg, data, url, today, image)
    jsonld = build_jsonld(cfg, data, url, today, image)
    header = parts["header"].replace("<body>", f"<body>\n{marker}", 1)

    return (head + jsonld + "</head>" + header
            + build_main(parts, cfg, data, topic, today, image) + parts["footer"])


def validate_assembled(html: str, cfg: dict, topic: dict) -> list[str]:
    """Filet de sécurité sur l'assemblage : ces contrôles ne portent plus sur le
    modèle mais sur notre propre code. Ils doivent toujours passer."""
    errors = []
    url = f"{cfg['site_url']}/blog/{topic['slug']}/"
    if not html.startswith("<!DOCTYPE html>"):
        errors.append("assemblage : DOCTYPE absent")
    if not html.rstrip().endswith("</html>"):
        errors.append("assemblage : </html> absent")
    if f"{cfg['topic_marker_prefix']}: {topic['num']}" not in html:
        errors.append("assemblage : marqueur d'idempotence absent")
    if html.count("<h1") != 1:
        errors.append(f"assemblage : {html.count('<h1')} balise(s) h1")
    if f'rel="canonical" href="{url}"' not in html:
        errors.append("assemblage : canonical incorrect")
    blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
    if len(blocks) != 3:
        errors.append(f"assemblage : {len(blocks)} blocs JSON-LD au lieu de 3")
    faq_ld = []
    for i, block in enumerate(blocks, 1):
        try:
            payload = json.loads(block)
        except json.JSONDecodeError as exc:
            errors.append(f"assemblage : JSON-LD n°{i} invalide ({exc})")
            continue
        if payload.get("@type") == "FAQPage":
            faq_ld = [q["name"] for q in payload.get("mainEntity", [])]
    if html.count('class="faq-item"') != cfg["faq_questions_count"]:
        errors.append("assemblage : nombre de questions de FAQ incorrect")
    # La FAQ déclarée à Google doit être mot pour mot celle qui est affichée.
    visible = [re.sub(r"<[^>]+>", "", x).strip()
               for x in re.findall(r'<div class="faq-item">\s*<h3>(.*?)</h3>', html, re.S)]
    if faq_ld and [esc(q) for q in faq_ld] != visible:
        errors.append("assemblage : la FAQ du JSON-LD diffère de la FAQ visible")
    # Les feuilles de style du site doivent rester liées.
    for asset in ("/assets/style.css", "/assets/blog.css"):
        if asset not in html:
            errors.append(f"assemblage : feuille de style {asset} absente")
    return errors


def extract(data: dict) -> dict:
    """Métadonnées utilisées par blog/index.html, rss.xml et llms.txt."""
    return {
        "title": plain(data["title"]),
        "description": plain(data["meta_description"]),
        "h1": plain(data["h1"]),
        "headline": plain(data["h1"]),
        "lead": plain(data["lede"]),
        "alt": plain(data.get("image_alt") or ""),
        "words": content_word_count(data),
    }


# ─────────────────────────────────────────────────────────────
# Mises à jour des fichiers annexes
# ─────────────────────────────────────────────────────────────

def update_blog_index(cfg: dict, topic: dict, meta: dict, today: dict,
                      image: str) -> str:
    """Ajoute la carte de l'article en tête de la grille .blog-grille,
    convention de ce site (et non .post-grid)."""
    html = BLOG_INDEX.read_text(encoding="utf-8")
    url = f"/blog/{topic['slug']}/"
    if url in html:
        log("blog/index.html contient déjà cet article : pas de doublon ajouté.")
        return html

    headline = meta["headline"] or topic["title"]
    teaser = meta["lead"] or meta["description"]
    if len(teaser) > 320:
        teaser = teaser[:317].rsplit(" ", 1)[0] + "…"
    alt = esc(meta["alt"] or cfg["site_name"])

    card = f"""
      <article class="blog-carte">
        <div class="blog-carte-image">
          <a href="{url}" tabindex="-1" aria-hidden="true">
            <img src="{esc(image)}"
                 alt="{alt}"
                 width="1200" height="800" loading="lazy" />
          </a>
        </div>
        <div class="blog-carte-corps">
          <div class="blog-carte-meta"><time datetime="{today['iso']}">{today['fr']}</time> · {esc(cfg['default_article_section'])}</div>
          <h2><a href="{url}">{esc(headline)}</a></h2>
          <p>{esc(teaser)}</p>
          <a href="{url}" class="btn btn-principal">Lire l'article</a>
        </div>
      </article>
"""
    anchor = '<div class="blog-grille">'
    if anchor not in html:
        raise ValueError("Point d'insertion .blog-grille introuvable dans blog/index.html")
    html = html.replace(anchor, anchor + card, 1)

    entry = f"""
      {{
        "@type": "BlogPosting",
        "headline": {json.dumps(headline, ensure_ascii=False)},
        "url": "{cfg['site_url']}{url}",
        "datePublished": "{today['iso']}",
        "image": "{cfg['site_url']}{image}"
      }},"""
    ld_anchor = '"blogPost": ['
    if ld_anchor in html:
        html = html.replace(ld_anchor, ld_anchor + entry, 1)
    else:
        log("Avertissement : tableau blogPost introuvable, JSON-LD de l'index inchangé.")
    return html


def update_sitemap(cfg: dict, topic: dict, today: dict, meta: dict,
                   image: str) -> str:
    xml = SITEMAP.read_text(encoding="utf-8")
    loc = f"{cfg['site_url']}/blog/{topic['slug']}/"
    if loc in xml:
        log("sitemap.xml contient déjà cette URL.")
        return xml

    xml = re.sub(
        rf"(<loc>{re.escape(cfg['site_url'])}/blog/</loc>\s*<lastmod>)[^<]*(</lastmod>)",
        rf"\g<1>{today['iso']}\g<2>", xml)

    alt = esc(meta["alt"] or cfg["site_name"])
    entry = f"""  <url>
    <loc>{loc}</loc>
    <lastmod>{today['iso']}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
    <image:image>
      <image:loc>{cfg['site_url']}{image}</image:loc>
      <image:title>{alt}</image:title>
    </image:image>
  </url>
</urlset>"""
    return xml.replace("</urlset>", entry, 1)


def update_rss(cfg: dict, topic: dict, meta: dict, today: dict) -> str:
    xml = RSS.read_text(encoding="utf-8")
    link = f"{cfg['site_url']}/blog/{topic['slug']}/"
    if link in xml:
        log("rss.xml contient déjà cet article.")
        return xml

    def xesc(text: str) -> str:
        return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

    headline = meta["headline"] or topic["title"]
    teaser = meta["lead"] or meta["description"]
    pub = rfc822(today["date"])

    xml = re.sub(r"<lastBuildDate>[^<]*</lastBuildDate>",
                 f"<lastBuildDate>{pub}</lastBuildDate>", xml, count=1)

    item = f"""    <item>
      <title>{xesc(headline)}</title>
      <link>{link}</link>
      <guid isPermaLink="true">{link}</guid>
      <pubDate>{pub}</pubDate>
      <category>{xesc(cfg['default_article_section'])}</category>
      <description>{xesc(teaser)}</description>
    </item>

"""
    # Le flux contient autant de <item> que d'articles : on vise le premier,
    # les nouveautés se placent en tête de flux.
    if "    <item>" in xml:
        idx = xml.index("    <item>")
        return xml[:idx] + item + xml[idx:]
    return xml.replace("  </channel>", item + "  </channel>", 1)


def update_llms(cfg: dict, topic: dict, meta: dict, today: dict) -> str | None:
    """Section « ## Articles » de llms.txt — convention de ce site."""
    if not LLMS.exists():
        return None
    text = LLMS.read_text(encoding="utf-8")
    url = f"{cfg['site_url']}/blog/{topic['slug']}/"
    if url in text:
        log("llms.txt référence déjà cet article.")
        return text
    headline = meta["headline"] or topic["title"]
    summary = (meta["description"] or "").rstrip(".")
    line = f"- [{headline}]({url}) — {today['fr']}. {summary}.\n"
    m = re.search(r"^## Articles\s*$\n\n", text, flags=re.M)
    if not m:
        log("Avertissement : section « ## Articles » introuvable dans llms.txt.")
        return text
    return text[:m.end()] + line + text[m.end():]


# ─────────────────────────────────────────────────────────────
# Point d'entrée
# ─────────────────────────────────────────────────────────────

def refresh_entries(cfg: dict, topic: dict, meta: dict) -> list[str]:
    """Après réécriture d'un article existant, resynchronise le teaser de
    blog/index.html et l'entrée RSS : les updaters sont idempotents par URL et
    laisseraient sinon en place le texte de l'ancienne version."""
    touched = []
    slug = topic["slug"]
    teaser = meta["lead"] or meta["description"]
    if len(teaser) > 320:
        teaser = teaser[:317].rsplit(" ", 1)[0] + "…"

    html = BLOG_INDEX.read_text(encoding="utf-8")
    card = re.search(r'<article class="blog-carte">(?:(?!</article>).)*?/blog/'
                     + re.escape(slug) + r'/(?:(?!</article>).)*?</article>', html, re.S)
    if card:
        new_card = re.sub(r"<p>(?!<)[^<]*</p>",
                          f"<p>{esc(teaser)}</p>", card.group(), count=1)
        new_card = re.sub(r'(<h2><a href="/blog/' + re.escape(slug) + r'/">)[^<]*',
                          lambda m: m.group(1) + esc(meta["headline"]), new_card, count=1)
        if new_card != card.group():
            BLOG_INDEX.write_text(html.replace(card.group(), new_card, 1), encoding="utf-8")
            touched.append("blog/index.html")

    xml = RSS.read_text(encoding="utf-8")
    item = re.search(r"<item>(?:(?!</item>).)*?" + re.escape(slug)
                     + r"(?:(?!</item>).)*?</item>", xml, re.S)
    if item:
        new_item = re.sub(r"<description>.*?</description>",
                          f"<description>{esc(teaser)}</description>",
                          item.group(), count=1, flags=re.S)
        new_item = re.sub(r"<title>.*?</title>",
                          f"<title>{esc(meta['headline'])}</title>",
                          new_item, count=1, flags=re.S)
        if new_item != item.group():
            RSS.write_text(xml.replace(item.group(), new_item, 1), encoding="utf-8")
            touched.append("rss.xml")
    return touched


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Génère un article de blog Bird Hunter 65.")
    parser.add_argument("--dry-run", action="store_true",
                        help="n'écrit aucun fichier, affiche le résultat")
    parser.add_argument("--mock", action="store_true",
                        help="n'appelle pas l'API OpenAI (contenu de démonstration)")
    parser.add_argument("--rewrite", metavar="SLUG",
                        help="réécrit un article existant et écrase son fichier")
    args = parser.parse_args()

    if args.dry_run:
        log("Mode DRY-RUN : aucun fichier ne sera écrit.")

    try:
        cfg = load_config()
        log(f"Site : {cfg['site_name']} — {cfg['site_url']}")

        if not WORKFLOW_PATH.exists():
            fail(f"BLOG_WORKFLOW.md introuvable ({WORKFLOW_PATH}).")
            return EXIT_ERROR
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

        topics = parse_topics(workflow)
        rules = parse_editorial_rules(workflow)
        log(f"{len(topics)} sujets listés dans BLOG_WORKFLOW.md.")
        if not rules:
            log("Avertissement : règles éditoriales non trouvées, prompt allégé.")

        done, slugs = scan_blog(cfg["topic_marker_prefix"])
        log(f"Articles déjà en ligne : {len(slugs)} — sujets marqués traités : "
            f"{sorted(done) if done else 'aucun'}")

        if args.rewrite:
            target_file = BLOG_DIR / args.rewrite / "index.html"
            if not target_file.exists():
                fail(f"Article introuvable : {target_file.relative_to(ROOT)}")
                return EXIT_ERROR
            existing = target_file.read_text(encoding="utf-8")
            m = re.search(rf"<!--\s*{re.escape(cfg['topic_marker_prefix'])}:\s*(\d+)\s*-->",
                          existing)
            if not m:
                fail(f"Aucun marqueur de sujet dans {target_file.relative_to(ROOT)} : "
                     "impossible de savoir quel sujet réécrire.")
                return EXIT_ERROR
            num = int(m.group(1))
            topic = next((t for t in topics if t["num"] == num), None)
            if topic is None:
                fail(f"Le sujet n°{num} n'existe plus dans BLOG_WORKFLOW.md.")
                return EXIT_ERROR
            topic["slug"] = args.rewrite
            log(f"Mode RÉÉCRITURE : sujet n°{num} — {topic['title']}")
        else:
            topic = pick_topic(topics, done, slugs)
            if topic is None:
                log("Aucun sujet restant à traiter. Ajoutez des lignes au tableau "
                    "de BLOG_WORKFLOW.md pour relancer la production.")
                return EXIT_NOTHING_TODO
            log(f"Sujet retenu : n°{topic['num']} — {topic['title']}")
            target_file = BLOG_DIR / topic["slug"] / "index.html"
            if target_file.exists():
                fail(f"Le fichier existe déjà : {target_file.relative_to(ROOT)} — "
                     "rien n'est écrasé (--rewrite pour le régénérer).")
                return EXIT_NOTHING_TODO

        log(f"Slug : {topic['slug']}")

        ref_slug, reference_html = load_reference_article(cfg, slugs)
        log(f"Gabarit relu depuis /blog/{ref_slug}/index.html "
            f"({len(reference_html)} caractères).")

        image = pick_image(cfg, topic)
        log(f"Illustration : {image}")

        today_date = dt.date.today()
        today = {"date": today_date, "iso": today_date.isoformat(),
                 "fr": fr_date(today_date)}

        system = user = None
        if args.mock:
            log("Mode MOCK : contenu de démonstration, aucun appel API.")
            data = mock_content(cfg, topic)
        else:
            system, user = build_prompt(cfg, topic, rules)
            log(f"Prompt construit ({len(system)} car. système + "
                f"{len(user)} car. utilisateur).")
            data = generate_content(cfg, system, user)

        errors = validate_content(data, cfg)
        wc = content_word_count(data)

        # Rattrapage : on relance tant qu'il reste une erreur que le modèle peut
        # corriger — volume hors cible, maillage absent, etc. —, dans la limite
        # de MAX_CALLS appels au total. Chaque reprise repart de la MEILLEURE
        # copie obtenue jusque-là, pas de la dernière.
        calls = 1
        while (not args.mock and calls < MAX_CALLS
               and (errors or not PROMPT_MIN_WORDS <= wc <= MAX_WORDS)):
            correction = build_correction(cfg, errors, wc)
            calls += 1
            reason = (f"{wc} mots, cible {PROMPT_MIN_WORDS}"
                      if not PROMPT_MIN_WORDS <= wc <= MAX_WORDS
                      else f"{len(errors)} erreur(s) de validation")
            log(f"Copie à reprendre ({reason}) — tentative {calls}/{MAX_CALLS}.")
            try:
                retry = generate_content(cfg, system, user, followup=[
                    {"role": "assistant", "content": json.dumps(data, ensure_ascii=False)},
                    {"role": "user", "content": correction},
                ])
            except (ValueError, json.JSONDecodeError) as exc:
                fail(f"Tentative {calls} inexploitable : {exc}")
                break
            retry_errors = validate_content(retry, cfg)
            retry_wc = content_word_count(retry)
            log(f"Tentative {calls} : {retry_wc} mots, {len(retry_errors)} erreur(s).")
            if volume_rank(retry_errors, retry_wc) < volume_rank(errors, wc):
                data, errors, wc = retry, retry_errors, retry_wc
                log(f"Copie retenue : la n°{calls}.")
            else:
                log("Copie retenue : la précédente (la nouvelle n'est pas meilleure).")
        if calls > 1:
            log(f"{calls} appels OpenAI au total pour cet article.")

        if errors:
            fail("Contenu rejeté par la validation — aucun fichier écrit :")
            for err in errors:
                fail(f"  · {err}")
            return EXIT_ERROR

        html = assemble(reference_html, cfg, topic, data, today, image)
        build_errors = validate_assembled(html, cfg, topic)
        if build_errors:
            fail("Assemblage HTML incorrect — aucun fichier écrit :")
            for err in build_errors:
                fail(f"  · {err}")
            return EXIT_ERROR

        meta = extract(data)
        log("Validation OK.")
        log(f"  Titre       : {meta['title']}")
        log(f"  Description : {meta['description']} ({len(meta['description'])} car.)")
        log(f"  Volume      : {meta['words']} mots (corps hors FAQ)")
        log(f"  Page        : {len(html)} caractères, "
            f"{len(data['sections'])} sections")

        if args.dry_run:
            print("\n" + "=" * 70)
            print("APERÇU (aucun fichier écrit)")
            print("=" * 70)
            print(f"Sujet       : n°{topic['num']} — {topic['title']}")
            print(f"Slug        : {topic['slug']}")
            print(f"URL         : {cfg['site_url']}/blog/{topic['slug']}/")
            print(f"Titre       : {meta['title']}")
            print(f"H1          : {meta['h1']}")
            print(f"Description : {meta['description']}")
            print(f"Mots        : {meta['words']}")
            print("-" * 70)
            for section in data["sections"]:
                print(f"  H2 · {plain(section['h2'])}")
            print("=" * 70)
            log("DRY-RUN terminé, rien n'a été modifié.")
            return EXIT_OK

        # ── Écriture (au plus tard possible, une fois tout validé) ──
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(html, encoding="utf-8")
        log(f"Écrit : {target_file.relative_to(ROOT)}")

        if args.rewrite:
            for name in refresh_entries(cfg, topic, meta):
                log(f"Resynchronisé : {name}")
            log(f"Terminé — article n°{topic['num']} réécrit : "
                f"{cfg['site_url']}/blog/{topic['slug']}/")
            return EXIT_OK

        blog_index_html = update_blog_index(cfg, topic, meta, today, image)
        sitemap_xml = update_sitemap(cfg, topic, today, meta, image)
        rss_xml = update_rss(cfg, topic, meta, today)
        llms_txt = update_llms(cfg, topic, meta, today)

        BLOG_INDEX.write_text(blog_index_html, encoding="utf-8")
        log("Mis à jour : blog/index.html")
        SITEMAP.write_text(sitemap_xml, encoding="utf-8")
        log("Mis à jour : sitemap.xml")
        RSS.write_text(rss_xml, encoding="utf-8")
        log("Mis à jour : rss.xml")
        if llms_txt is not None:
            LLMS.write_text(llms_txt, encoding="utf-8")
            log("Mis à jour : llms.txt")

        log(f"Terminé — article n°{topic['num']} publié : "
            f"{cfg['site_url']}/blog/{topic['slug']}/")
        return EXIT_OK

    except Exception as exc:                      # noqa: BLE001
        fail(f"{type(exc).__name__} : {exc}")
        return EXIT_ERROR


if __name__ == "__main__":
    sys.exit(main())
