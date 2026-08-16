#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Génération automatique d'un article de blog — Bird Hunter 65
=============================================================

Principe : le gabarit HTML n'est PAS dupliqué dans ce script. Il est relu à
chaque exécution depuis l'article de référence indiqué dans blog-config.json
(`template_article`). Le script ne fait que remplacer des régions identifiées
du gabarit. Si le gabarit évolue, les articles générés suivent automatiquement.

Sortie :
  code 0   article généré (ou dry-run réussi)
  code 1   erreur (API, gabarit illisible, contenu invalide) — rien n'est écrit
  code 78  aucun nouveau sujet à traiter — rien n'est écrit

Usage :
  python3 scripts/generate-article.py
  python3 scripts/generate-article.py --dry-run
  python3 scripts/generate-article.py --dry-run --mock   (sans clé API)
  python3 scripts/generate-article.py --topic 4          (force un sujet)
"""

import argparse
import datetime as dt
import html
import json
import os
import re
import sys
import unicodedata

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_NO_TOPIC = 78

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MOIS_FR = ["janvier", "février", "mars", "avril", "mai", "juin",
           "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
JOURS_EN = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MOIS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
           "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


# ══════════════════════════════════════════════════════════════════════
#  Journalisation
# ══════════════════════════════════════════════════════════════════════

def log(msg):
    print(f"[blog] {msg}", flush=True)


def warn(msg):
    print(f"[blog][ATTENTION] {msg}", flush=True)


def fail(msg):
    """Erreur fatale : on sort en 1 sans avoir rien écrit sur le disque."""
    print(f"[blog][ERREUR] {msg}", file=sys.stderr, flush=True)
    sys.exit(EXIT_ERROR)


# ══════════════════════════════════════════════════════════════════════
#  Utilitaires
# ══════════════════════════════════════════════════════════════════════

def rel(path):
    return os.path.join(ROOT, path)


def read(path):
    with open(rel(path), encoding="utf-8") as fh:
        return fh.read()


def esc(text):
    """Échappement pour un nœud texte."""
    return html.escape(str(text), quote=False)


def esc_attr(text):
    """Échappement pour une valeur d'attribut."""
    return html.escape(str(text), quote=True)


def slugify(value):
    """Minuscules, sans accent, tirets — même convention que les slugs existants."""
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c))
    value = value.lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return re.sub(r"-{2,}", "-", value).strip("-")


def date_fr(d):
    return f"{d.day} {MOIS_FR[d.month - 1]} {d.year}"


def date_rfc822(d):
    return (f"{JOURS_EN[d.weekday()]}, {d.day:02d} {MOIS_EN[d.month - 1]} "
            f"{d.year} 08:00:00 +0200")


def replace_once(text, pattern, replacement, label, flags=re.S):
    """Remplace une région unique du gabarit. Échoue si 0 ou >1 correspondance."""
    matches = list(re.finditer(pattern, text, flags))
    if len(matches) != 1:
        fail(f"gabarit : {len(matches)} correspondance(s) pour « {label} » "
             f"(1 attendue). Le gabarit a probablement changé de structure.")
    m = matches[0]
    value = replacement(m) if callable(replacement) else replacement
    return text[:m.start()] + value + text[m.end():]


def insert_before_first(text, marker, payload, label):
    """Insère `payload` avant la PREMIÈRE occurrence de `marker`.

    À utiliser quand le point d'ancrage se répète (un flux RSS contient autant
    de <item> que d'articles) : replace_once refuserait de choisir.
    """
    pos = text.find(marker)
    if pos == -1:
        fail(f"point d'insertion « {label} » introuvable.")
    return text[:pos] + payload + text[pos:]


def json_ld_blocks(text):
    return list(re.finditer(
        r'(<script type="application/ld\+json">\s*)(.*?)(\s*</script>)', text, re.S))


def dump_json_ld(obj):
    """Sérialise un bloc JSON-LD avec l'indentation du gabarit (2 espaces + 2)."""
    raw = json.dumps(obj, ensure_ascii=False, indent=2)
    return "\n".join("  " + line if line else line for line in raw.split("\n"))


# ══════════════════════════════════════════════════════════════════════
#  1. Configuration
# ══════════════════════════════════════════════════════════════════════

def load_config():
    try:
        cfg = json.loads(read("blog-config.json"))
    except FileNotFoundError:
        fail("blog-config.json introuvable à la racine du dépôt.")
    except json.JSONDecodeError as e:
        fail(f"blog-config.json illisible : {e}")
    for key in ("site_slug", "site_name", "site_url", "template_article",
                "blog_dir", "blog_index", "workflow_doc"):
        if not cfg.get(key):
            fail(f"blog-config.json : clé « {key} » manquante.")
    cfg["site_url"] = cfg["site_url"].rstrip("/")
    return cfg


# ══════════════════════════════════════════════════════════════════════
#  2. Sujets : lecture du tableau de BLOG_WORKFLOW.md
# ══════════════════════════════════════════════════════════════════════

def load_topics(cfg):
    """Extrait les sujets du tableau « | n | titre | `slug` | période | »."""
    try:
        doc = read(cfg["workflow_doc"])
    except FileNotFoundError:
        fail(f"{cfg['workflow_doc']} introuvable : impossible de lire les sujets.")

    topics = []
    row = re.compile(r"^\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*`([a-z0-9-]+)`\s*\|\s*(.*?)\s*\|\s*$")
    for line in doc.splitlines():
        m = row.match(line.strip())
        if m:
            topics.append({
                "n": int(m.group(1)),
                "title": m.group(2).strip(),
                "slug": m.group(3).strip(),
                "period": m.group(4).strip(),
            })

    if not topics:
        fail(f"aucun sujet trouvé dans {cfg['workflow_doc']}. "
             "Le tableau doit rester au format « | n | sujet | `slug` | période | ».")

    topics.sort(key=lambda t: t["n"])
    log(f"{len(topics)} sujets lus dans {cfg['workflow_doc']}")
    return topics


# ══════════════════════════════════════════════════════════════════════
#  3. Articles déjà publiés (slugs + marqueurs d'idempotence)
# ══════════════════════════════════════════════════════════════════════

def scan_published(cfg):
    blog_dir = rel(cfg["blog_dir"])
    slugs, markers = set(), set()
    marker_re = re.compile(
        r"<!--\s*" + re.escape(cfg["site_slug"]) + r"-topic:\s*(\d+)\s*-->")

    if not os.path.isdir(blog_dir):
        fail(f"dossier {cfg['blog_dir']}/ introuvable.")

    for name in sorted(os.listdir(blog_dir)):
        path = os.path.join(blog_dir, name, "index.html")
        if not os.path.isfile(path):
            continue
        slugs.add(name)
        with open(path, encoding="utf-8") as fh:
            m = marker_re.search(fh.read())
        if m:
            markers.add(int(m.group(1)))

    log(f"{len(slugs)} article(s) déjà publié(s) : {', '.join(sorted(slugs)) or '—'}")
    if markers:
        log(f"sujets déjà traités automatiquement : {sorted(markers)}")
    return slugs, markers


def pick_topic(topics, slugs, markers, forced=None):
    """Premier sujet non traité, dans l'ordre du tableau."""
    if forced is not None:
        for t in topics:
            if t["n"] == forced:
                if t["n"] in markers or t["slug"] in slugs:
                    fail(f"sujet {forced} déjà publié (slug « {t['slug']} »). "
                         "Rien n'est écrit — le script est idempotent.")
                return t
        fail(f"sujet {forced} absent du tableau de BLOG_WORKFLOW.md.")

    for t in topics:
        if t["n"] in markers:
            continue
        if t["slug"] in slugs:
            log(f"sujet {t['n']} ignoré : le dossier blog/{t['slug']}/ existe déjà")
            continue
        return t
    return None


# ══════════════════════════════════════════════════════════════════════
#  4. Appel OpenAI
# ══════════════════════════════════════════════════════════════════════

SCHEMA_HINT = """Réponds UNIQUEMENT avec un objet JSON valide, sans commentaire,
respectant exactement cette forme :

{
  "title_seo": "titre de la balise <title>, 60 caractères max, sans le nom du site",
  "h1": "titre visible de l'article",
  "meta_description": "150 caractères MAXIMUM, phrase complète",
  "og_title": "titre pour les réseaux sociaux, 70 caractères max",
  "category": "catégorie courte, ex : Chasse au petit gibier",
  "keywords": "6 à 10 mots-clés séparés par des virgules",
  "image_alt": "description factuelle de la photo d'illustration",
  "image_caption": "légende courte de la photo",
  "chapo": "chapô d'accroche de 2 à 3 phrases",
  "sections": [
    {
      "h2": "titre de section",
      "paragraphs": ["paragraphe", "paragraphe"],
      "subsections": [
        { "h3": "sous-titre", "paragraphs": ["paragraphe"] }
      ]
    }
  ],
  "summary_points": ["point de synthèse", "point de synthèse"],
  "faq": [
    { "question": "question telle qu'un client la poserait", "answer": "réponse de 2 à 4 phrases" }
  ],
  "card_excerpt": "résumé de 2 phrases pour la carte du blog et le flux RSS"
}"""


def build_prompt(cfg, topic):
    facts = "\n".join(f"- {f}" for f in cfg.get("facts_allowed", []))
    geo = ", ".join(cfg.get("geo_keywords", []))
    return f"""Tu rédiges un article de blog pour {cfg['site_name']}, {cfg['sector']}
situé à {cfg['location']}.

SUJET IMPOSÉ : {topic['title']}

TON : {cfg['tone']}. Tu écris comme un professionnel du métier qui explique son
terrain à un client, à la première personne du pluriel quand tu parles du domaine.

RÈGLES ABSOLUES — toute violation rend l'article inutilisable :
1. N'INVENTE JAMAIS de prix, de tarif, de chiffre précis, de pourcentage, de
   statistique, de date de fondation, de nom de client, de témoignage, de récompense,
   ni de référence à un article de loi ou à une réglementation datée.
2. Les SEULS faits chiffrés ou concrets que tu peux citer sur le domaine sont
   ceux de cette liste, et rien d'autre :
{facts}
3. Si tu as besoin d'un chiffre qui n'est pas dans cette liste, reformule la phrase
   SANS le chiffre. Une phrase vague et vraie vaut mieux qu'une phrase précise et fausse.
4. Ne cite jamais de tarif : renvoie le lecteur vers la page des offres du site.
5. Pour la réglementation, reste général : « permis de chasser en cours de validité
   et assurance responsabilité civile chasse obligatoires » est la seule formulation
   autorisée. Ne cite aucun texte, aucune date, aucun quota légal.

ANCRAGE LOCAL : intègre naturellement dans le corps du texte plusieurs de ces
repères géographiques : {geo}. Ils doivent apparaître dans des phrases utiles,
jamais empilés en liste.

STRUCTURE ATTENDUE :
- environ {cfg.get('target_word_count', 1300)} mots au total dans les paragraphes
  (viser entre 1200 et 1500 mots)
- 5 à 7 sections de niveau h2
- au moins 2 sections comportant des sous-sections h3
- 4 à 6 points de synthèse dans summary_points
- exactement {cfg.get('faq_questions_count', 5)} questions dans faq
- meta_description de 150 caractères MAXIMUM (contrainte stricte)
- pas de section « En résumé » ni de conclusion dans sections : la synthèse est
  générée séparément à partir de summary_points
- pas de balise HTML dans les textes, du texte brut uniquement

{SCHEMA_HINT}"""


def call_openai(cfg, topic):
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        fail("OPENAI_API_KEY absent de l'environnement. "
             "Utilisez --mock pour tester le script hors ligne.")
    try:
        from openai import OpenAI
    except ImportError:
        fail("bibliothèque « openai » non installée (pip install openai).")

    model = cfg.get("openai_model", "gpt-4o-mini")
    log(f"appel OpenAI · modèle {model} · sujet {topic['n']} — {topic['title']}")

    try:
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=model,
            temperature=cfg.get("openai_temperature", 0.7),
            response_format={"type": "json_object"},
            messages=[
                {"role": "system",
                 "content": "Tu es un rédacteur web spécialisé en SEO local francophone. "
                            "Tu ne produis que du JSON valide. Tu n'inventes jamais de fait."},
                {"role": "user", "content": build_prompt(cfg, topic)},
            ],
        )
    except Exception as e:                                   # noqa: BLE001
        fail(f"appel OpenAI échoué : {type(e).__name__} — {e}")

    try:
        data = json.loads(resp.choices[0].message.content)
    except (json.JSONDecodeError, AttributeError, IndexError) as e:
        fail(f"réponse OpenAI illisible (JSON attendu) : {e}")

    usage = getattr(resp, "usage", None)
    if usage:
        log(f"jetons : {usage.prompt_tokens} entrée + "
            f"{usage.completion_tokens} sortie = {usage.total_tokens}")
    return data


def mock_content(cfg, topic):
    """Contenu factice pour tester la chaîne complète sans clé API."""
    log("mode --mock : contenu factice, aucun appel à OpenAI")
    para = (("Cette phrase de démonstration remplace le texte qui serait rédigé par "
             "le modèle. Elle sert uniquement à vérifier que le gabarit, les données "
             "structurées et les fichiers de référencement sont correctement "
             "assemblés, sans consommer un seul jeton d'API. ") * 2).strip()
    return {
        "title_seo": f"{topic['title']} | {cfg['location'].split(',')[0]}",
        "h1": topic["title"],
        "meta_description": (f"{topic['title']} : repères de terrain et conseils "
                             f"pratiques à {cfg['location'].split(',')[0]}.")[:150],
        "og_title": topic["title"],
        "category": "Chasse au petit gibier",
        "keywords": "chasse petit gibier, Tournay, Hautes-Pyrénées, faisan, perdreau",
        "image_alt": "Photo d'illustration du domaine de chasse Bird Hunter à Tournay",
        "image_caption": "Le domaine, à Tournay (65), à quinze minutes de Tarbes.",
        "chapo": "Chapô de démonstration généré en mode hors ligne. " + para,
        "sections": [
            {"h2": f"Partie de démonstration n°{i + 1}",
             "paragraphs": [para, para, para],
             "subsections": ([{"h3": "Un point de détail", "paragraphs": [para, para]}]
                             if i % 2 == 0 else [])}
            for i in range(4)
        ],
        "summary_points": [f"Point de synthèse n°{i + 1}." for i in range(4)],
        "faq": [{"question": f"Question de démonstration n°{i + 1} ?",
                 "answer": para} for i in range(cfg.get("faq_questions_count", 5))],
        "card_excerpt": "Résumé de démonstration pour la carte du blog et le flux RSS.",
    }


# ══════════════════════════════════════════════════════════════════════
#  5. Validation du contenu reçu
# ══════════════════════════════════════════════════════════════════════

def validate(cfg, data):
    required = ["title_seo", "h1", "meta_description", "chapo",
                "sections", "summary_points", "faq", "card_excerpt"]
    for key in required:
        if not data.get(key):
            fail(f"contenu généré incomplet : champ « {key} » absent ou vide.")

    if not isinstance(data["sections"], list) or len(data["sections"]) < 3:
        fail("contenu généré : au moins 3 sections h2 attendues.")

    expected_faq = cfg.get("faq_questions_count", 5)
    faq = data["faq"]
    if not isinstance(faq, list) or len(faq) < expected_faq:
        fail(f"contenu généré : {expected_faq} questions de FAQ attendues, "
             f"{len(faq) if isinstance(faq, list) else 0} reçue(s).")
    data["faq"] = faq[:expected_faq]
    for q in data["faq"]:
        if not q.get("question") or not q.get("answer"):
            fail("contenu généré : une question de FAQ est incomplète.")

    # Contrainte stricte : la meta description doit rester sous 155 caractères.
    desc = " ".join(data["meta_description"].split())
    if len(desc) > 154:
        cut = desc[:154].rsplit(" ", 1)[0].rstrip(" ,;:–-")
        warn(f"meta description de {len(desc)} caractères → tronquée à {len(cut)}")
        desc = cut
    data["meta_description"] = desc

    words = sum(len(p.split())
                for s in data["sections"]
                for p in s.get("paragraphs", []))
    words += sum(len(p.split())
                 for s in data["sections"]
                 for sub in s.get("subsections", []) or []
                 for p in sub.get("paragraphs", []))
    words += len(data["chapo"].split())
    log(f"corps de l'article : ~{words} mots")
    if words < 900:
        fail(f"article trop court ({words} mots) : publication annulée.")
    if words > 1900:
        warn(f"article long ({words} mots) — publié tel quel.")
    return data


# ══════════════════════════════════════════════════════════════════════
#  6. Fabrication du HTML à partir du gabarit
# ══════════════════════════════════════════════════════════════════════

def build_body(data):
    """Contenu de <div class="article-corps">, indenté comme le gabarit."""
    out = []
    for sec in data["sections"]:
        out.append(f'        <h2>{esc(sec["h2"])}</h2>\n')
        for p in sec.get("paragraphs", []):
            out.append(f"        <p>{esc(p)}</p>\n")
        for sub in sec.get("subsections") or []:
            out.append(f'        <h3>{esc(sub["h3"])}</h3>\n')
            for p in sub.get("paragraphs", []):
                out.append(f"        <p>{esc(p)}</p>\n")

    out.append("        <h2>En résumé</h2>\n")
    out.append('        <ul class="liste">\n')
    for point in data["summary_points"]:
        out.append(f"          <li>{esc(point)}</li>\n")
    out.append("        </ul>\n")
    return "\n".join(chunk.rstrip("\n") for chunk in out)


def build_faq_items(data):
    parts = []
    for q in data["faq"]:
        parts.append(
            '        <div class="faq-item">\n'
            f'          <h3>{esc(q["question"])}</h3>\n'
            f'          <p>{esc(q["answer"])}</p>\n'
            "        </div>"
        )
    return "\n\n".join(parts)


def render_article(cfg, template, topic, data, today):
    """Remplace, région par région, le contenu du gabarit."""
    base = cfg["site_url"]
    slug = topic["slug"]
    url = f"{base}/blog/{slug}/"
    iso = today.isoformat()
    image = cfg["image_pool"][(topic["n"] - 1) % len(cfg["image_pool"])]
    image_url = f"{base}/{image}"
    site = cfg["site_name"]
    doc = template

    # ---- Marqueur d'idempotence -------------------------------------
    marker = f"<!-- {cfg['site_slug']}-topic: {topic['n']} -->"
    doc = replace_once(doc, r"<body>\n", f"<body>\n{marker}\n", "<body>")

    # ---- <title> et meta description --------------------------------
    # Le modèle ajoute parfois le nom du site de lui-même : on évite le doublon.
    title = " ".join(data["title_seo"].split())
    if site.lower() not in title.lower():
        title = f"{title} | {site}"
    if len(title) > 75:
        warn(f"balise <title> de {len(title)} caractères — Google la tronquera.")
    doc = replace_once(doc, r"<title>.*?</title>",
                       f"<title>{esc(title)}</title>", "<title>")
    doc = replace_once(
        doc,
        r'<meta name="description"\s*\n\s*content=".*?" />',
        '<meta name="description"\n'
        f'        content="{esc_attr(data["meta_description"])}" />',
        "meta description")

    # ---- URLs canoniques --------------------------------------------
    doc = replace_once(doc, r'<link rel="canonical" href=".*?" />',
                       f'<link rel="canonical" href="{esc_attr(url)}" />', "canonical")
    doc = replace_once(doc, r'<meta property="og:url" content=".*?" />',
                       f'<meta property="og:url" content="{esc_attr(url)}" />', "og:url")

    # ---- Open Graph / Twitter ---------------------------------------
    og_title = data.get("og_title") or data["h1"]
    for prop, value in [("og:title", og_title),
                        ("og:description", data["meta_description"]),
                        ("og:image", image_url),
                        ("og:image:alt", data["image_alt"]),
                        ("article:published_time", iso),
                        ("article:modified_time", iso),
                        ("article:section", data["category"])]:
        doc = replace_once(
            doc, rf'<meta property="{re.escape(prop)}" content=".*?" />',
            f'<meta property="{prop}" content="{esc_attr(value)}" />', prop)

    for name, value in [("twitter:title", og_title),
                        ("twitter:description", data["meta_description"]),
                        ("twitter:image", image_url),
                        ("twitter:image:alt", data["image_alt"])]:
        doc = replace_once(
            doc, rf'<meta name="{re.escape(name)}" content=".*?" />',
            f'<meta name="{name}" content="{esc_attr(value)}" />', name)

    # ---- JSON-LD : Article, BreadcrumbList, FAQPage ------------------
    doc = update_json_ld(doc, cfg, data, url, image_url, iso)

    # ---- Fil d'Ariane visible ---------------------------------------
    doc = replace_once(
        doc, r'<li aria-current="page">.*?</li>',
        f'<li aria-current="page">{esc(topic["title"])}</li>', "fil d'Ariane")

    # ---- En-tête de l'article ---------------------------------------
    doc = replace_once(doc, r"<h1>.*?</h1>", f'<h1>{esc(data["h1"])}</h1>', "<h1>")
    doc = replace_once(
        doc, r'<time datetime=".*?">.*?</time>',
        f'<time datetime="{iso}">{date_fr(today)}</time>', "date visible")
    doc = replace_once(
        doc,
        r'(<time datetime="[^"]*">[^<]*</time>\s*\n\s*<span class="sep">•</span>\s*\n\s*<span>).*?(</span>)',
        lambda m: m.group(1) + esc(data["category"]) + m.group(2),
        "catégorie visible")

    # ---- Image d'illustration ---------------------------------------
    doc = replace_once(
        doc, r'<figure class="article-image">.*?</figure>',
        '<figure class="article-image">\n'
        f'        <img src="/{esc_attr(image)}"\n'
        f'             alt="{esc_attr(data["image_alt"])}"\n'
        '             width="1200" height="800" />\n'
        f'        <figcaption>{esc(data["image_caption"])}</figcaption>\n'
        "      </figure>", "figure")

    # ---- Chapô, corps, FAQ ------------------------------------------
    doc = replace_once(doc, r'<p class="article-chapo">.*?</p>',
                       f'<p class="article-chapo">{esc(data["chapo"])}</p>', "chapô")
    doc = replace_once(
        doc, r'(<div class="article-corps">\n).*?(\n\n      </div>)',
        lambda m: m.group(1) + build_body(data) + m.group(2), "corps de l'article")
    doc = replace_once(
        doc, r'(<h2 id="faq-titre">[^<]*</h2>\n\n).*?(\n      </section>)',
        lambda m: m.group(1) + build_faq_items(data) + m.group(2), "FAQ visible")

    return doc, image


def update_json_ld(doc, cfg, data, url, image_url, iso):
    base = cfg["site_url"]
    blocks = json_ld_blocks(doc)
    if len(blocks) != 3:
        fail(f"gabarit : {len(blocks)} blocs JSON-LD trouvés, 3 attendus "
             "(Article, BreadcrumbList, FAQPage).")

    rebuilt = []
    for m in blocks:
        try:
            obj = json.loads(m.group(2))
        except json.JSONDecodeError as e:
            fail(f"gabarit : bloc JSON-LD invalide — {e}")
        kind = obj.get("@type")

        if kind == "Article":
            obj["@id"] = url + "#article"
            obj["headline"] = data["h1"]
            obj["description"] = data["meta_description"]
            obj["datePublished"] = iso
            obj["dateModified"] = iso
            obj["image"] = image_url
            obj["articleSection"] = data["category"]
            obj["keywords"] = data["keywords"]
            obj["mainEntityOfPage"] = {"@type": "WebPage", "@id": url}

        elif kind == "BreadcrumbList":
            items = obj.get("itemListElement", [])
            if items:
                items[-1]["name"] = data["h1"]
                items[-1]["item"] = url

        elif kind == "FAQPage":
            obj["mainEntity"] = [
                {"@type": "Question", "name": q["question"],
                 "acceptedAnswer": {"@type": "Answer", "text": q["answer"]}}
                for q in data["faq"]
            ]
        else:
            fail(f"gabarit : bloc JSON-LD de type inattendu « {kind} ».")

        rebuilt.append(dump_json_ld(obj))

    # Reconstruction de droite à gauche pour ne pas décaler les positions.
    for m, payload in zip(reversed(blocks), reversed(rebuilt)):
        doc = doc[:m.start(2)] + payload.strip() + doc[m.end(2):]
    assert base  # base est déjà intégré dans les URLs passées en argument
    return doc


# ══════════════════════════════════════════════════════════════════════
#  7. Mises à jour des fichiers annexes
# ══════════════════════════════════════════════════════════════════════

def update_blog_index(cfg, topic, data, image, today):
    doc = read(cfg["blog_index"])
    url_path = f"/blog/{topic['slug']}/"
    iso = today.isoformat()

    if url_path in doc:
        warn("la carte de cet article existe déjà dans blog/index.html — inchangée")
        return doc

    card = (
        '      <article class="blog-carte">\n'
        '        <div class="blog-carte-image">\n'
        f'          <a href="{url_path}" tabindex="-1" aria-hidden="true">\n'
        f'            <img src="/{esc_attr(image)}"\n'
        f'                 alt="{esc_attr(data["image_alt"])}"\n'
        '                 width="1200" height="800" loading="lazy" />\n'
        "          </a>\n"
        "        </div>\n"
        '        <div class="blog-carte-corps">\n'
        f'          <div class="blog-carte-meta"><time datetime="{iso}">'
        f'{date_fr(today)}</time> · {esc(data["category"])}</div>\n'
        f'          <h2><a href="{url_path}">{esc(data["h1"])}</a></h2>\n'
        f'          <p>{esc(data["card_excerpt"])}</p>\n'
        f'          <a href="{url_path}" class="btn btn-principal">Lire l\'article</a>\n'
        "        </div>\n"
        "      </article>\n"
    )

    # La carte la plus récente se place en tête de grille.
    doc = replace_once(doc, r'(<div class="blog-grille">\n\n)',
                       lambda m: m.group(1) + card + "\n", "grille du blog")

    # Bloc JSON-LD Blog : ajout en tête de blogPost.
    blocks = json_ld_blocks(doc)
    for m in blocks:
        obj = json.loads(m.group(2))
        if obj.get("@type") != "Blog":
            continue
        entry = {
            "@type": "BlogPosting",
            "headline": data["h1"],
            "url": f"{cfg['site_url']}{url_path}",
            "datePublished": iso,
            "image": f"{cfg['site_url']}/{image}",
        }
        obj["blogPost"] = [entry] + obj.get("blogPost", [])
        doc = doc[:m.start(2)] + dump_json_ld(obj).strip() + doc[m.end(2):]
        break
    return doc


def update_sitemap(cfg, topic, image, data, today):
    doc = read(cfg["sitemap"])
    loc = f"{cfg['site_url']}/blog/{topic['slug']}/"
    iso = today.isoformat()

    if loc in doc:
        warn("l'article figure déjà dans sitemap.xml — inchangé")
        return doc

    entry = (
        "  <url>\n"
        f"    <loc>{loc}</loc>\n"
        f"    <lastmod>{iso}</lastmod>\n"
        "    <changefreq>monthly</changefreq>\n"
        "    <priority>0.7</priority>\n"
        "    <image:image>\n"
        f"      <image:loc>{cfg['site_url']}/{image}</image:loc>\n"
        f"      <image:title>{esc(data['image_alt'])}</image:title>\n"
        "    </image:image>\n"
        "  </url>\n"
    )

    blog_loc = f"{cfg['site_url']}/blog/"
    doc = replace_once(
        doc,
        rf"(  <url>\n    <loc>{re.escape(blog_loc)}</loc>\n    <lastmod>)[\d-]+(</lastmod>)",
        lambda m: m.group(1) + iso + m.group(2), "lastmod de /blog/")
    doc = replace_once(doc, r"(\n)(  <url>\n    <loc>[^<]*mentions-legales)",
                       lambda m: m.group(1) + entry + m.group(2), "insertion sitemap")
    return doc


def update_rss(cfg, topic, data, today):
    doc = read(cfg["rss"])
    link = f"{cfg['site_url']}/blog/{topic['slug']}/"

    if link in doc:
        warn("l'article figure déjà dans rss.xml — inchangé")
        return doc

    item = (
        "    <item>\n"
        f"      <title>{esc(data['h1'])}</title>\n"
        f"      <link>{link}</link>\n"
        f'      <guid isPermaLink="true">{link}</guid>\n'
        f"      <pubDate>{date_rfc822(today)}</pubDate>\n"
        f"      <category>{esc(data['category'])}</category>\n"
        f"      <description>{esc(data['card_excerpt'])}</description>\n"
        "    </item>\n"
    )
    doc = replace_once(doc, r"<lastBuildDate>.*?</lastBuildDate>",
                       f"<lastBuildDate>{date_rfc822(today)}</lastBuildDate>",
                       "lastBuildDate")
    # Le flux contient autant de <item> que d'articles : on vise le premier,
    # les nouveautés se placent en tête de flux.
    doc = insert_before_first(doc, "    <item>", item + "\n", "premier <item> du flux")
    return doc


def update_llms(cfg, topic, data, today):
    """Étape 5 de BLOG_WORKFLOW.md : référencer l'article dans llms.txt."""
    path = cfg.get("llms")
    if not path or not os.path.isfile(rel(path)):
        return None
    doc = read(path)
    url = f"{cfg['site_url']}/blog/{topic['slug']}/"
    if url in doc:
        warn("l'article figure déjà dans llms.txt — inchangé")
        return doc
    line = (f"- [{data['h1']}]({url}) — {date_fr(today)}. "
            f"{data['card_excerpt']}\n")
    return replace_once(doc, r"(## Articles\n\n)",
                        lambda m: m.group(1) + line, "section Articles de llms.txt")


# ══════════════════════════════════════════════════════════════════════
#  8. Vérifications finales avant écriture
# ══════════════════════════════════════════════════════════════════════

def verify(cfg, article_html, data):
    for i, m in enumerate(json_ld_blocks(article_html)):
        try:
            json.loads(m.group(2))
        except json.JSONDecodeError as e:
            fail(f"article généré : bloc JSON-LD n°{i} invalide — {e}")

    desc = re.search(r'<meta name="description"\s*\n\s*content="(.*?)" />',
                     article_html, re.S)
    length = len(html.unescape(desc.group(1)).strip()) if desc else 0
    if length == 0 or length > 154:
        fail(f"article généré : meta description de {length} caractères "
             "(155 maximum).")
    log(f"meta description : {length} caractères")

    ld_faq = [q["name"] for m in json_ld_blocks(article_html)
              for q in json.loads(m.group(2)).get("mainEntity", [])
              if json.loads(m.group(2)).get("@type") == "FAQPage"]
    visible = [html.unescape(re.sub(r"<[^>]+>", "", x)).strip()
               for x in re.findall(r'<div class="faq-item">\s*<h3>(.*?)</h3>',
                                   article_html, re.S)]
    if ld_faq != visible or len(visible) != cfg.get("faq_questions_count", 5):
        fail("article généré : la FAQ du JSON-LD ne correspond pas à la FAQ visible.")
    log(f"FAQ : {len(visible)} questions, JSON-LD et texte visible identiques")

    marker = f"{cfg['site_slug']}-topic:"
    if marker not in article_html:
        fail("article généré : marqueur d'idempotence absent.")

    if "[" in data["h1"] and "]" in data["h1"]:
        warn("le titre contient des crochets — vérifiez qu'il ne reste pas de gabarit.")


# ══════════════════════════════════════════════════════════════════════
#  9. Programme principal
# ══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Génère et publie un article de blog.")
    parser.add_argument("--dry-run", action="store_true",
                        help="n'écrit aucun fichier, affiche un aperçu")
    parser.add_argument("--mock", action="store_true",
                        help="contenu factice, sans appel à OpenAI (test hors ligne)")
    parser.add_argument("--topic", type=int, default=None,
                        help="force le numéro de sujet à traiter")
    args = parser.parse_args()

    log(f"racine du dépôt : {ROOT}")
    cfg = load_config()
    log(f"site : {cfg['site_name']} — {cfg['site_url']}")

    topics = load_topics(cfg)
    slugs, markers = scan_published(cfg)
    topic = pick_topic(topics, slugs, markers, args.topic)

    if topic is None:
        log("tous les sujets de BLOG_WORKFLOW.md ont été publiés.")
        log("Ajoutez de nouvelles lignes au tableau pour relancer la production.")
        sys.exit(EXIT_NO_TOPIC)

    log(f"sujet retenu : n°{topic['n']} — {topic['title']}")
    log(f"slug : {topic['slug']}")

    target_dir = os.path.join(rel(cfg["blog_dir"]), topic["slug"])
    target = os.path.join(target_dir, "index.html")
    if os.path.exists(target):
        fail(f"blog/{topic['slug']}/index.html existe déjà — publication annulée.")

    try:
        template = read(cfg["template_article"])
    except FileNotFoundError:
        fail(f"gabarit introuvable : {cfg['template_article']}")
    log(f"gabarit relu depuis {cfg['template_article']} ({len(template)} caractères)")

    data = mock_content(cfg, topic) if args.mock else call_openai(cfg, topic)
    data = validate(cfg, data)

    today = dt.date.today()
    article_html, image = render_article(cfg, template, topic, data, today)
    log(f"image d'illustration : {image}")
    verify(cfg, article_html, data)

    blog_index = update_blog_index(cfg, topic, data, image, today)
    sitemap = update_sitemap(cfg, topic, image, data, today)
    rss = update_rss(cfg, topic, data, today)
    llms = update_llms(cfg, topic, data, today)

    if args.dry_run:
        log("--- MODE DRY-RUN : aucun fichier écrit ---")
        print()
        print("=" * 70)
        print(f"TITRE      : {data['h1']}")
        print(f"SLUG       : blog/{topic['slug']}/")
        print(f"DESCRIPTION: {data['meta_description']}")
        print(f"CATÉGORIE  : {data['category']}")
        print("=" * 70)
        print()
        text = re.sub(r"<[^>]+>", " ", build_body(data))
        text = " ".join(html.unescape(text).split())
        print("CHAPÔ :", data["chapo"])
        print()
        print("CORPS (200 premiers mots) :")
        print(" ".join(text.split()[:200]), "…")
        print()
        print("FAQ :")
        for q in data["faq"]:
            print(f"  · {q['question']}")
        print()
        log(f"fichiers qui auraient été écrits : blog/{topic['slug']}/index.html, "
            f"{cfg['blog_index']}, {cfg['sitemap']}, {cfg['rss']}"
            + (f", {cfg['llms']}" if llms else ""))
        sys.exit(EXIT_OK)

    # ---- Écriture : tout est prêt et validé, on écrit d'un bloc ------
    os.makedirs(target_dir, exist_ok=True)
    with open(target, "w", encoding="utf-8") as fh:
        fh.write(article_html)
    log(f"écrit : blog/{topic['slug']}/index.html")

    for path, content in [(cfg["blog_index"], blog_index),
                          (cfg["sitemap"], sitemap),
                          (cfg["rss"], rss),
                          (cfg["llms"], llms)]:
        if content is None:
            continue
        with open(rel(path), "w", encoding="utf-8") as fh:
            fh.write(content)
        log(f"mis à jour : {path}")

    log(f"terminé — sujet {topic['n']} publié.")
    sys.exit(EXIT_OK)


if __name__ == "__main__":
    main()
