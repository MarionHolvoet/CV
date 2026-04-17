"""
tex_watch.py  —  Watch CV_Marion_Holvoet.tex and regenerate index.html on every save.

Usage:
    python tex_watch.py            # watch and regenerate on change
    python tex_watch.py --once     # regenerate once and exit
    python tex_watch.py --translate        # auto-translate missing FR entries, then regenerate
    python tex_watch.py --translate-force  # retranslate everything, then regenerate

Requires: watchdog
    pip install watchdog
For translation (free, no API key required):
    pip install deep-translator
"""

import re
import sys
import time
import textwrap
from pathlib import Path

TEX_FILE  = Path(__file__).parent / "CV_Marion_Holvoet.tex"
HTML_FILE = Path(__file__).parent / "index.html"

# ─── TeX → plain-text helpers ────────────────────────────────────────────────

def tex_to_html_inline(s: str) -> str:
    """Convert inline TeX markup to HTML."""
    # Strip TeX line comments (% ... end-of-line), but not escaped \%
    s = re.sub(r"(?<!\\)%[^\n]*", "", s)
    s = s.replace("\\&", "\x00AMP\x00")   # protect TeX \& with a placeholder
    s = s.replace("&", "&amp;")            # escape any bare &
    s = s.replace("\x00AMP\x00", "&amp;")  # restore placeholder as &amp;
    s = s.replace("\\textregistered{}", "®")
    s = s.replace("\\textregistered",   "®")
    s = s.replace("\\textsuperscript{2}", "<sup>2</sup>")
    s = re.sub(r"\\textsuperscript\{([^}]*)\}", r"<sup>\1</sup>", s)
    s = re.sub(r"\\textbf\{([^}]*)\}",   r"<b>\1</b>",   s)
    s = re.sub(r"\\textit\{([^}]*)\}",   r"<i>\1</i>",   s)
    s = re.sub(r"\\emph\{([^}]*)\}",     r"<i>\1</i>",   s)
    s = re.sub(r"\\bfseries\s*",         "",              s)
    s = re.sub(r"\\color\{[^}]+\}\s*",   "",              s)
    s = re.sub(r"\\small\s*",            "",              s)
    s = re.sub(r"\{([^{}]*)\}",          r"\1",           s)  # strip remaining braces
    s = re.sub(r"[{}]",                  "",              s)  # strip any leftover stray braces
    s = s.replace("\\ ", " ")
    s = s.replace("\\,", "\u202f")   # narrow no-break space
    s = s.replace("\\;", " ")
    s = s.replace("\\!", "")
    s = s.replace("--", "–")
    s = s.replace("---", "—")
    s = s.replace("~", "\u00a0")
    # Strip leftover lone backslash commands
    s = re.sub(r"\\[a-zA-Z]+\*?\s*", "", s)
    s = s.strip()
    return s

def strip_tex(s: str) -> str:
    """Strip all TeX markup, returning plain text."""
    return tex_to_html_inline(s)

# ─── Brace-aware argument extractor ──────────────────────────────────────────

def extract_args(text: str, n: int) -> tuple[list[str], str]:
    """
    Given text starting just after a macro name, extract n brace-delimited
    arguments. Returns (list_of_args, remaining_text).
    """
    args = []
    pos = 0
    for _ in range(n):
        # skip whitespace / newlines before '{'
        while pos < len(text) and text[pos] in " \t\n\r%":
            if text[pos] == "%":
                while pos < len(text) and text[pos] != "\n":
                    pos += 1
            else:
                pos += 1
        if pos >= len(text) or text[pos] != "{":
            args.append("")
            continue
        pos += 1  # skip opening '{'
        # Skip a TeX line comment immediately after '{' (e.g. '{%\n  content…')
        if pos < len(text) and text[pos] == "%":
            while pos < len(text) and text[pos] != "\n":
                pos += 1
            if pos < len(text):
                pos += 1  # consume the newline
        depth = 1
        start = pos
        while pos < len(text) and depth > 0:
            if text[pos] == "{":
                depth += 1
            elif text[pos] == "}":
                depth -= 1
            pos += 1
        args.append(text[start:pos - 1])
    return args, text[pos:]

# ─── TeX body parser ─────────────────────────────────────────────────────────

def parse_tex(tex_path: Path) -> dict:
    """
    Parse the CV TeX file and return a structured dict with all content.
    """
    src = tex_path.read_text(encoding="utf-8")

    # Work only inside \begin{document}...\end{document}
    doc_match = re.search(r"\\begin\{document\}(.*?)\\end\{document\}", src, re.DOTALL)
    if not doc_match:
        raise ValueError("Could not find \\begin{document}")
    body = doc_match.group(1)

    # ── Header ───────────────────────────────────────────────────────────────
    name_m    = re.search(r"\\bfseries\\color\{white\}\s*([^\}\\]+)", body)
    subtitle_m = re.search(r"\\Large\\color\{[^}]+\}\s*((?:[^\}\\]|\\.)*)", body)
    name     = name_m.group(1).strip()    if name_m    else "Marion Holvoet"
    subtitle = subtitle_m.group(1).strip() if subtitle_m else ""
    subtitle = subtitle.replace("\\textbar", "|").replace("\\ ", " ").replace("\\&", "&").strip()
    subtitle = re.sub(r"  +", " ", subtitle)

    # ── Split into LEFT / RIGHT columns ──────────────────────────────────────
    switch_pos = body.find("\\switchcolumn")
    end_pos    = body.find("\\end{paracol}")
    left_body  = body[:switch_pos]   if switch_pos != -1 else ""
    right_body = body[switch_pos:end_pos] if switch_pos != -1 else ""

    # ── Parse left column sections ───────────────────────────────────────────
    left_sections = _parse_left(left_body)

    # ── Parse right column sections ──────────────────────────────────────────
    right_sections = _parse_right(right_body)

    # ── Other / footer ───────────────────────────────────────────────────────
    nationalities_m = re.search(r"\\textbf\{Nationalities:\}\s*([^\\\n.]+)", body)
    permits_m       = re.search(r"\\textbf\{Permits:\}\s*([^\\\n.]+)", body)
    nationalities = nationalities_m.group(1).strip() if nationalities_m else ""
    permits       = permits_m.group(1).strip()       if permits_m       else ""

    hobbies_m = re.search(r"\\rsection\{Hobbies\}.*?\{\\small\\color\{dark\}\s*(.*?)\}", body, re.DOTALL)
    hobbies   = hobbies_m.group(1).strip() if hobbies_m else ""
    # Convert \enskip\textperiodcentered\enskip  →  ·
    hobbies   = re.sub(r"\\enskip\\textperiodcentered\\enskip", " · ", hobbies)
    hobbies   = strip_tex(hobbies)

    return {
        "name":         name.strip(),
        "subtitle":     subtitle.strip(),
        "left":         left_sections,
        "right":        right_sections,
        "hobbies":      hobbies,
        "nationalities": nationalities,
        "permits":      permits,
    }


def _parse_left(text: str) -> dict:
    """Parse left-column sections from TeX snippet."""
    result = {
        "profile":       "",
        "contact":       [],   # list of (icon_hint, display, href_or_None)
        "languages":     [],   # list of (name, level)
        "cert_sidebar":  {},   # {title, title_href, sub, sub_href, date}
        "skills":        [],   # list of str
        "traits":        [],   # list of str
    }

    # Profile text
    m = re.search(r"\\lsection\{Profile\}(.*?)\\lsection\{Contact\}", text, re.DOTALL)
    if m:
        raw = re.sub(r"\{\\small\\color\{dark\}\s*", "", m.group(1))
        raw = re.sub(r"\}", "", raw, count=1)
        # Convert \par into a paragraph break placeholder before stripping TeX
        raw = re.sub(r"\\par\\vspace\{[^}]+\}\s*", "\x00PAR\x00", raw)
        raw = re.sub(r"\\par\b\s*", "\x00PAR\x00", raw)
        # Collapse plain newlines to spaces (within a paragraph), then restore breaks
        paragraphs = raw.split("\x00PAR\x00")
        paragraphs = [strip_tex(p).replace("\n", " ").strip() for p in paragraphs]
        paragraphs = [p for p in paragraphs if p]
        result["profile"] = "<br/><br/>".join(paragraphs)

    # Contact items — phone, email, linkedin
    phone_m = re.search(r"\\faPhone\\\s*(.*?)\}?\\par", text)
    if phone_m:
        result["contact"].append(("phone", strip_tex(phone_m.group(1)).strip("}"), None))

    for href_m in re.finditer(r"\\href\{([^}]+)\}\{([^}]+)\}", text):
        url   = href_m.group(1)
        label = strip_tex(href_m.group(2))
        if "mailto" in url:
            result["contact"].append(("email", label, url))
        else:
            result["contact"].append(("linkedin", label, url))

    # Languages
    for m in re.finditer(r"\\langitem\{([^}]+)\}\{([^}]+)\}", text):
        result["languages"].append((m.group(1).strip(), m.group(2).strip()))

    # Certifications sidebar
    cert_title_m = re.search(r"\\textbf\{([^}]+)\}", text[text.find("\\lsection{Certifications}"):])
    cert_date_m  = re.search(r"\\textit\{Issued:\s*([^}]+)\}",    text)
    cert_sub_m   = re.search(r"\\color\{muted\}(.*?)\\textit",     text, re.DOTALL)
    cert_title   = strip_tex(cert_title_m.group(1)) if cert_title_m else ""
    cert_date    = cert_date_m.group(1).strip()      if cert_date_m  else ""
    cert_sub_raw = cert_sub_m.group(1)               if cert_sub_m   else ""
    cert_sub_raw = re.sub(r"\\\\", "<br/>", cert_sub_raw)
    cert_sub_raw = re.sub(r"\[\d+pt\]", "", cert_sub_raw)
    cert_sub     = strip_tex(cert_sub_raw).strip()
    result["cert_sidebar"] = {
        "title":      cert_title,
        "title_href": "https://certificates.future-network-cert.com/56605bf8-3f87-4795-b6a8-a35f88ad6722#acc.14ITxLiW",
        "sub":        cert_sub,
        "sub_href":   "https://www.isaqb.org/certifications/cpsa-certifications/cpsa-foundation-level/",
        "date":       cert_date,
    }

    # Skills
    skills_start = text.find("\\lsection{Key Skills}")
    skills_end   = text.find("\\lsection{Personal Traits}")
    if skills_start != -1 and skills_end != -1:
        skills_block = text[skills_start:skills_end]
        result["skills"] = [strip_tex(m.group(1)) for m in re.finditer(r"\\skillitem\{([^}]+)\}", skills_block)]

    # Traits
    traits_start = text.find("\\lsection{Personal Traits}")
    if traits_start != -1:
        traits_block = text[traits_start:]
        result["traits"] = [strip_tex(m.group(1)) for m in re.finditer(r"\\skillitem\{([^}]+)\}", traits_block)]

    return result


def _parse_right(text: str) -> dict:
    """Parse right-column sections from TeX snippet."""
    result = {
        "experience":    [],   # list of exp dicts
        "education":     [],   # list of edu dicts
        "cert_bullets":  [],   # list of str
    }

    # Experience entries
    pos = 0
    while True:
        m = re.search(r"\\expentry", text[pos:])
        if not m:
            break
        pos += m.start() + len("\\expentry")
        args, text_after = extract_args(text[pos:], 4)
        pos += len(text[pos:]) - len(text_after)
        title   = strip_tex(args[0])
        company_raw = args[1].replace("\\,|\\,", " | ").replace("\\,", "\u202f")
        company = strip_tex(company_raw)
        dates   = strip_tex(args[2])
        items   = [strip_tex(i.strip()) for i in re.findall(r"\\item\s+(.*?)(?=\\item|$)", args[3], re.DOTALL)]
        items   = [i for i in items if i]
        result["experience"].append({"title": title, "company": company, "dates": dates, "items": items})

    # Education entries
    pos = 0
    while True:
        m = re.search(r"\\eduentry", text[pos:])
        if not m:
            break
        pos += m.start() + len("\\eduentry")
        args, text_after = extract_args(text[pos:], 4)
        pos += len(text[pos:]) - len(text_after)
        degree  = strip_tex(args[0])
        inst    = strip_tex(args[1].replace("\\,", "\u202f"))
        year    = strip_tex(args[2])
        desc    = strip_tex(args[3])
        result["education"].append({"degree": degree, "institution": inst, "year": year, "desc": desc})

    # Certification bullets (right column)
    cert_block_m = re.search(r"\\rsection\{Certifications\}(.*?)\\rsection\{Hobbies\}", text, re.DOTALL)
    if cert_block_m:
        cert_block = cert_block_m.group(1)
        result["cert_bullets"] = [
            strip_tex(i.strip())
            for i in re.findall(r"\\item\s+(.*?)(?=\\item|\}|$)", cert_block, re.DOTALL)
            if i.strip()
        ]

    return result

# ─── Company / institution URL map ───────────────────────────────────────────

COMPANY_URLS = {
    "Metrolab Technology SA": "https://www.metrolab.com",
    "Spacetek Technology AG":  "https://www.spacetek.ch",
    "Ottobock":                "https://www.ottobock.com",
    "INRIA":                   "https://www.inria.fr",
    "LIRMM":                   "https://www.lirmm.fr",
    "Montpellier University":  "https://www.umontpellier.fr",
}

def company_html(raw: str) -> str:
    """Wrap known company/institution names in links."""
    for name, url in COMPANY_URLS.items():
        if name in raw:
            raw = raw.replace(name, f'<a href="{url}" target="_blank" rel="noopener">{name}</a>')
    return raw

# ─── French translations (static) ────────────────────────────────────────────
# These are stable — update here if you rename sections or add new content.

FR = {
    # header
    "subtitle": "Ingénieure Logiciel &nbsp;|&nbsp; Architecture &amp; Systèmes MedTech",
    # left column section titles
    "Profile":        "Profil",
    "Contact":        "Contact",
    "Languages":      "Langues",
    "Certifications": "Certifications",
    "Key Skills":     "Compétences Clés",
    "Personal Traits":"Qualités Personnelles",
    # profile paragraph
    "profile": (
        "Ingénieure logiciel spécialisée dans les systèmes embarqués et backend, avec un Master en "
        "Ingénierie des Dispositifs Médicaux et la certification iSAQB&nbsp;CPSA-F. Axée sur l'architecture "
        "logicielle, la conception système et le développement rigoureux dans des environnements à exigences "
        "qualité élevées.<br/><br/>"
    ),
    # language names / levels
    "English": "Anglais",  "French": "Français",  "German": "Allemand",
    "Native":  "Natif",
    # cert sidebar
    "cert_sub_fr": "Professionnelle Certifiée<br/>en Architecture Logicielle<br/>Niveau Fondation",
    "cert_date_fr": "Délivré : Septembre 2024",
    # skills / traits (order-matched to EN list)
    "skills_fr": [
        "C++ / Go / Python / JavaScript",
        "Architecture Logicielle",
        "Conception Système",
        "Embedded Linux / ARM / x86",
        "CMake / Git / Docker",
        "Yocto / Mender",
        "REST API / HTTPS",
        "GoogleTest / Pytest / CI/CD",
        "Qt / Svelte / HDF5",
        "GitHub Copilot",
    ],
    "traits_fr": [
        "Penseuse positive",
        "Esprit orienté solutions",
        "Indépendante et travailleuse",
        "Communicatrice claire",
        "Apprentissage rapide",
        "Axée sur la qualité",
        "Esprit d'équipe collaboratif",
    ],
    # right column: experience titles (EN → FR)
    "exp_titles": {
        "Software Engineer":          "Ingénieure Logiciel",
        "Research Engineer":          "Ingénieure de Recherche",
        "Software Engineering Intern":"Stagiaire Ingénierie Logiciel",
        "Research Intern":            "Stagiaire Chercheuse",
    },
    # experience company locations
    "Switzerland": "Suisse",
    "Germany":     "Allemagne",
    # experience dates (EN → FR)
    "exp_dates": {
        "October 2023 – Present":         "Octobre 2023 – Présent",
        "April 2021 – September 2023":    "Avril 2021 – Septembre 2023",
        "September 2020 – March 2021":    "Septembre 2020 – Mars 2021",
        "February – August 2020":         "Février – Août 2020",
        "April – July 2019":              "Avril – Juillet 2019",
    },
    # experience bullet translations (keyed by EN text, trimmed)
    "exp_bullets": {
        "Architecture & System Design:": "Architecture &amp; Conception Système :",
        "Embedded & Backend Development:": "Développement Embarqué &amp; Backend :",
        "Cross-Platform Systems:": "Systèmes Multi-Plateformes :",
        "Tooling & Practices:": "Outils &amp; Pratiques :",
    },
    # full bullet FR translations (list-index matched per company)
    "exp_items_fr": {
        "Metrolab Technology SA": [
            "<b>Architecture et amp; Conception du système :</b> Contribution aux discussions sur l'architecture logicielle. Rédaction d'un document d'architecture pour un système de développement innovant, couvrant les décisions de conception, l'évolutivité et la maintenabilité à long terme.",
            "<b>Intégré et intégré Développement backend :</b> Firmware et composants backend dans C++ pour le déploiement en production. Images Linux personnalisées avec Yocto. Traitement du signal avec les bibliothèques Boost.",
            "<b>Systèmes multiplateformes :</b> extension d'une application C++/Qt. Gestion des builds multiplateformes sur Linux / Windows / MacOS sur les architectures ARM et x86.",
            "<b>Outillage et amp; Pratiques :</b> Contrôle de version avec Git et Perforce. Administratrice GitLab. Environnements de développement basés sur Linux avec systèmes de construction basés sur CMake. Lancement de pipelines CI/CD avec des images Docker personnalisées.",
        ],
        "Spacetek Technology AG": [
            "Développement de logiciels embarqués en C et C++ avec CMake. Images Linux personnalisées avec Yocto. Déploiement OTA avec Mender.",
            "Développement d'API RESTful dans Go sur HTTPS. Gestion des lacs de données avec HDF5.",
            "Traitement du signal en temps réel dans Python et C++ pour les signaux bruités. Développement SDK.",
            "Développement front-end avec Qt (C++) et Svelte (JavaScript).",
            "Test avec GoogleTest et Pytest. Pipelines GitLab CI/CD. Ajout de plus d'écriture juste pour vérifier la traduction automatique.",
        ],
        "Ottobock_1": [
            "Contrôle moteur en boucle fermée pour prothèses haut de gamme en C++, Python et Node.js.",
            "Acquisition de données sur un réseau de capteurs (température, pression, courant via Modbus et I<sup>2</sup>C) avec analyse basée sur le machine learning.",
        ],
        "Ottobock_2": [
            "Interface graphique Python pour une imprimante 3D à grande échelle : calibrage de l'extrusion, surveillance du capteur de pression et contrôle du moteur pas à pas via Bluetooth vers un microcontrôleur ARMM4 (C++).",
        ],
        "INRIA": [
            "Application smartwatch portable (Tizen) pour l'acquisition de données. Quantification et analyse des tremblements liés à la maladie de Parkinson.",
        ],
    },
    # education degree FR
    "edu_degrees_fr": {
        "M.Eng. Biomedical / Medical Device Engineering": "M.Eng. Biomédical / Ingénierie des Dispositifs Médicaux",
        "B.Sc. Electronic Engineering": "Licence Génie Électronique",
        "Scientific Baccalaureate":     "Baccalauréat Scientifique",
    },
    "edu_institutions_fr": {
        "Montpellier University": "Université de Montpellier",
    },
    "edu_descs_fr": {
        "M.Eng. Biomedical / Medical Device Engineering": (
            "Master of Engineering en Ingénierie des Dispositifs Médicaux — Sciences Numériques pour la Santé. "
            "Spécialisation en Ingénierie des Dispositifs de Santé."
        ),
        "B.Sc. Electronic Engineering": (
            "Licence en Génie Électronique. Projet de fin d'études : robot araignée contrôlé par STM32 "
            "(mécanique, électronique et firmware)."
        ),
        "Scientific Baccalaureate": "Spécialité Physique et Chimie.",
    },
    # right column section titles
    "Professional Experience": "Expérience Professionnelle",
    "Education":               "Formation",
    # cert right column
    "cert_right_title_fr": "iSAQB® Professionnelle Certifiée en Architecture Logicielle",
    "cert_right_sub_fr":   "Niveau Fondation (CPSA-F)",
    "cert_right_date_fr":  "Septembre 2024",
    "cert_bullets_fr": [
        "Les bases de l'architecture logicielle et le rôle et les tâches des architectes logiciels",
        "Les exigences d'architecture, les objectifs d'architecture et les objectifs de qualité non fonctionnels",
        "Composants, blocs de construction, interfaces et dépendances",
        "Préoccupations transversales et concepts techniques",
        "Documentation et communication des architectures",
    ],
    # hobbies / other
    "hobbies_fr": "Escalade &nbsp;·&nbsp; Randonnée &nbsp;·&nbsp; Ski / Snowboard &nbsp;·&nbsp; Batterie",
    "Hobbies":    "Loisirs",
    "Other":      "Autres",
    "other_fr": (
        "<b>Nationalités :</b> France, Nouvelle-Zélande, États-Unis d'Amérique.<br/>"
        "<b>Permis :</b> Permis de conduire."
    ),
}

# ─── HTML generation ─────────────────────────────────────────────────────────

def _bi(en: str, fr: str) -> str:
    """Bilingual span pair."""
    return f'<span class="lang-en">{en}</span><span class="lang-fr">{fr}</span>'

def _section_title_left(en: str) -> str:
    fr = FR.get(en, en)
    if en == fr:
        return f'<span class="lsection-title">{en}</span>'
    return f'<span class="lsection-title">{_bi(en, fr)}</span>'

def _section_title_right(en: str) -> str:
    fr = FR.get(en, en)
    if en == fr:
        return f'<span class="rsection-title">{en}</span>'
    return (
        '<div class="rsection-head">'
        '<span class="rsection-bar"></span>'
        f'<span class="rsection-title">{_bi(en, fr)}</span>'
        '</div>'
    )


def html_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

def safe(s: str) -> str:
    """Escape plain text but preserve already-HTML content."""
    # If it already looks like HTML (has tags), pass through
    if re.search(r"<[a-zA-Z/]", s):
        return s
    return html_escape(s)

def bullet_html(item_en: str, item_fr: str) -> str:
    return (
        f'          <li>\n'
        f'            <span class="lang-en">{item_en}</span>\n'
        f'            <span class="lang-fr">{item_fr}</span>\n'
        f'          </li>'
    )


def render_html(data: dict) -> str:
    left  = data["left"]
    right = data["right"]

    # ── Contact icons ─────────────────────────────────────────────────────────
    contact_items = []
    for icon_hint, label, href in left["contact"]:
        if icon_hint == "phone":
            icon = "&#9990;"
            inner = safe(label)
        elif icon_hint == "email":
            icon = "&#9993;"
            inner = f'<a href="{href}">{safe(label)}</a>'
        else:
            icon = "in"
            inner = f'<a href="{href}" target="_blank" rel="noopener">{safe(label)}</a>'
        contact_items.append(
            f'        <li>\n'
            f'          <span class="contact-icon">{icon}</span>\n'
            f'          {inner}\n'
            f'        </li>'
        )
    contact_html = "\n".join(contact_items)

    # ── Languages ─────────────────────────────────────────────────────────────
    lang_items = []
    for name, level in left["languages"]:
        name_fr  = FR.get(name, name)
        level_fr = FR.get(level, level)
        if name_fr == name:
            name_span = name
        else:
            name_span = _bi(name, name_fr)
        if level_fr == level:
            level_span = level
        else:
            level_span = _bi(level, level_fr)
        lang_items.append(
            f'        <li>\n'
            f'          <span class="lang-name">{name_span}</span>\n'
            f'          <span class="lang-level">{level_span}</span>\n'
            f'        </li>'
        )
    lang_html = "\n".join(lang_items)

    # ── Skills / Traits ───────────────────────────────────────────────────────
    def skill_items_html(items_en, items_fr):
        rows = []
        for i, en in enumerate(items_en):
            fr = items_fr[i] if i < len(items_fr) else en
            if en == fr:
                rows.append(f'        <li><span class="skill-bullet">&#9632;</span>{safe(en)}</li>')
            else:
                rows.append(f'        <li><span class="skill-bullet">&#9632;</span>{_bi(safe(en), safe(fr))}</li>')
        return "\n".join(rows)

    skills_html = skill_items_html(left["skills"], FR["skills_fr"])
    traits_html = skill_items_html(left["traits"], FR["traits_fr"])

    # ── Cert sidebar ──────────────────────────────────────────────────────────
    cs = left["cert_sidebar"]
    cert_sidebar_html = (
        f'      <div class="cert-sidebar">\n'
        f'        <div class="cert-title"><a href="{cs["title_href"]}" target="_blank" rel="noopener">{safe(cs["title"])}</a></div>\n'
        f'        <div class="cert-sub">\n'
        f'          <a href="{cs["sub_href"]}" target="_blank" rel="noopener" style="color:inherit;text-decoration:none;border-bottom:1px dotted var(--muted);">\n'
        f'          <span class="lang-en">Certified Professional for<br/>\n'
        f'          Software Architecture<br/>\n'
        f'          Foundation Level</span>\n'
        f'          <span class="lang-fr">{FR["cert_sub_fr"]}</span>\n'
        f'          </a>\n'
        f'        </div>\n'
        f'        <div class="cert-date" style="margin-top:4px;">\n'
        f'          <span class="lang-en">Issued: {safe(cs["date"])}</span>\n'
        f'          <span class="lang-fr">{FR["cert_date_fr"]}</span>\n'
        f'        </div>\n'
        f'      </div>'
    )

    # ── Experience entries ────────────────────────────────────────────────────
    ottobock_idx = 0
    exp_html_parts = []
    for exp in right["experience"]:
        title_en  = exp["title"]
        title_fr  = FR["exp_titles"].get(title_en, title_en)
        dates_en  = exp["dates"]
        dates_fr  = FR["exp_dates"].get(dates_en, dates_en)
        company   = exp["company"]
        # Strip country from company string for the lookup key
        company_key = company.split(" | ")[0].strip()

        # Pick FR bullets
        if "Metrolab" in company:
            fr_bullets = FR["exp_items_fr"]["Metrolab Technology SA"]
        elif "Spacetek" in company:
            fr_bullets = FR["exp_items_fr"]["Spacetek Technology AG"]
        elif "INRIA" in company or "LIRMM" in company:
            fr_bullets = FR["exp_items_fr"]["INRIA"]
        elif "Ottobock" in company:
            ottobock_idx += 1
            fr_bullets = FR["exp_items_fr"][f"Ottobock_{ottobock_idx}"]
        else:
            fr_bullets = []

        # Translate country in company string
        company_display = company
        for en_loc, fr_loc in [("Switzerland", FR["Switzerland"]), ("Germany", FR["Germany"])]:
            company_display = company_display  # keep en for HTML, use FR span

        # Build bilingual company line
        for en_loc, fr_loc in [("Switzerland", FR["Switzerland"]), ("Germany", FR["Germany"]), ("France", "France")]:
            if en_loc in company:
                company_en = company.replace(en_loc, en_loc)
                company_fr = company.replace(en_loc, fr_loc)
                break
        else:
            company_en = company_fr = company

        company_en_html = company_html(company_en)
        company_fr_html = company_html(company_fr)

        # Bullets
        bullets = []
        for j, item_en in enumerate(exp["items"]):
            # Convert **bold:** patterns
            item_en_html = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", safe(item_en))
            # Handle TeX \textbf already converted to <b>
            item_fr_html = fr_bullets[j] if j < len(fr_bullets) else safe(item_en)
            bullets.append(bullet_html(item_en_html, item_fr_html))

        bullets_str = "\n".join(bullets)
        exp_html_parts.append(textwrap.dedent(f"""\
      <div class="exp-entry">
        <div class="exp-header">
          <span class="exp-title">
            {_bi(title_en, title_fr)}
          </span>
          <span class="exp-dates">
            {_bi(dates_en, dates_fr)}
          </span>
        </div>
        <div class="exp-company">{_bi(company_en_html, company_fr_html)}</div>
        <ul class="exp-desc">
{bullets_str}
        </ul>
      </div>"""))

    exp_html = "\n\n      ".join(exp_html_parts)

    # ── Education entries ─────────────────────────────────────────────────────
    edu_html_parts = []
    for edu in right["education"]:
        degree_en = edu["degree"]
        degree_fr = FR["edu_degrees_fr"].get(degree_en, degree_en)
        inst_en   = edu["institution"]
        inst_parts = inst_en.split("\u202f|\u202f") if "\u202f|\u202f" in inst_en else inst_en.split(" | ")
        inst_name_en = inst_parts[0].strip() if inst_parts else inst_en
        inst_loc     = inst_parts[1].strip() if len(inst_parts) > 1 else ""
        inst_name_fr = FR["edu_institutions_fr"].get(inst_name_en, inst_name_en)
        inst_en_html = f'<a href="{COMPANY_URLS.get(inst_name_en, "#")}" target="_blank" rel="noopener">{inst_name_en}</a>'
        inst_fr_html = f'<a href="{COMPANY_URLS.get(inst_name_en, "#")}" target="_blank" rel="noopener">{inst_name_fr}</a>'
        inst_loc_html = f" &nbsp;|&nbsp; {inst_loc}" if inst_loc else ""
        desc_en = safe(edu["desc"])
        desc_fr = FR["edu_descs_fr"].get(degree_en, desc_en)
        year    = edu["year"]
        edu_html_parts.append(textwrap.dedent(f"""\
      <div class="edu-entry">
        <div class="edu-header">
          <span class="edu-degree">
            {_bi(degree_en, degree_fr)}
          </span>
          <span class="edu-year">{year}</span>
        </div>
        <div class="edu-institution">{_bi(inst_en_html + inst_loc_html, inst_fr_html + inst_loc_html)}</div>
        <div class="edu-desc">
          {_bi(desc_en, desc_fr)}
        </div>
      </div>"""))

    edu_html = "\n\n      ".join(edu_html_parts)

    # ── Cert right column ─────────────────────────────────────────────────────
    cert_bullets_en = right["cert_bullets"]
    cert_bullets_fr = FR["cert_bullets_fr"]
    cert_bullets_html = "\n".join(
        bullet_html(safe(en), fr)
        for en, fr in zip(cert_bullets_en, cert_bullets_fr + [""] * len(cert_bullets_en))
        if en
    )
    cert_right_html = textwrap.dedent(f"""\
      <div class="cert-right-entry">
        <div class="cert-right-header">
          <span class="cert-right-title">
            <span class="lang-en"><a href="https://certificates.future-network-cert.com/56605bf8-3f87-4795-b6a8-a35f88ad6722#acc.14ITxLiW" target="_blank" rel="noopener" style="color:inherit;text-decoration:none;">iSAQB&reg; Certified Professional for Software Architecture</a></span>
            <span class="lang-fr"><a href="https://certificates.future-network-cert.com/56605bf8-3f87-4795-b6a8-a35f88ad6722#acc.14ITxLiW" target="_blank" rel="noopener" style="color:inherit;text-decoration:none;">{FR["cert_right_title_fr"]}</a></span>
          </span>
          <span class="cert-right-date">
            <span class="lang-en">September 2024</span><span class="lang-fr">{FR["cert_right_date_fr"]}</span>
          </span>
        </div>
        <div class="cert-right-sub">
          <a href="https://www.isaqb.org/certifications/cpsa-certifications/cpsa-foundation-level/" target="_blank" rel="noopener" style="color:inherit;text-decoration:none;border-bottom:1px dotted var(--muted);"><span class="lang-en">Foundation Level (CPSA-F)</span><span class="lang-fr">{FR["cert_right_sub_fr"]}</span></a>
        </div>
        <ul class="cert-right-desc">
{cert_bullets_html}
        </ul>
      </div>""")

    # ── Hobbies ───────────────────────────────────────────────────────────────
    hobbies_en  = data["hobbies"].replace("·", "&middot;")
    hobbies_fr  = FR["hobbies_fr"]

    # ── Other ─────────────────────────────────────────────────────────────────
    nat = safe(data["nationalities"])
    per = safe(data["permits"])
    other_en = f"<b>Nationalities:</b> {nat}.<br/><b>Permits:</b> {per}."
    other_fr = FR["other_fr"]

    # ── Subtitle ──────────────────────────────────────────────────────────────
    _sub = data["subtitle"]
    subtitle_en = _sub.replace("&", "&amp;").replace("|", "&nbsp;|&nbsp;")
    subtitle_fr = FR["subtitle"]

    # ══════════════════════════════════════════════════════════════════════════
    # Full HTML document
    # ══════════════════════════════════════════════════════════════════════════
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate" />
  <meta http-equiv="Pragma" content="no-cache" />
  <meta http-equiv="Expires" content="0" />
  <title>Marion Holvoet — CV</title>
  <style>
    /* ── Reset & Base ──────────────────────────────────────────────── */
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
      font-size: 10pt;
      line-height: 1.55;
      color: #1C2B2B;
      background: #fff;
    }}

    /* ── Colour palette ────────────────────────────────────────────── */
    :root {{
      --headerbg:   #12343B;
      --accent:     #0F7F74;
      --accentlight:#7DC8C2;
      --sidebarbg:  #EAF4F3;
      --dark:       #1C2B2B;
      --muted:      #4A6E6A;
    }}

    /* ── Page wrapper (A4-ish) ─────────────────────────────────────── */
    .page {{
      max-width: 850px;
      margin: 0 auto;
      background: #fff;
      box-shadow: 0 2px 20px rgba(0,0,0,0.15);
    }}

    /* ══════════════════════════════════════════════════════════════
       HEADER
    ══════════════════════════════════════════════════════════════ */
    .header {{
      background: var(--headerbg);
      padding: 22px 28px 0 28px;
      position: relative;
    }}

    .header-inner {{
      display: flex;
      align-items: center;
      gap: 18px;
      padding-bottom: 18px;
    }}

    .header-photo {{
      flex-shrink: 0;
      width: 72px;
      height: 72px;
      border-radius: 50%;
      border: 2.5px solid var(--accent);
      object-fit: cover;
      background: var(--accent);
    }}

    .header-photo-placeholder {{
      flex-shrink: 0;
      width: 72px;
      height: 72px;
      border-radius: 50%;
      border: 2.5px solid var(--accent);
      background: var(--accent);
      opacity: 0.4;
    }}

    .header-text h1 {{
      font-size: 26pt;
      font-weight: 700;
      color: #fff;
      letter-spacing: -0.5px;
    }}

    .header-rule {{
      height: 1px;
      width: 140px;
      background: var(--accentlight);
      margin: 6px 0;
    }}

    .header-text .subtitle {{
      font-size: 13pt;
      color: rgba(255,255,255,0.88);
    }}

    .header-accent-strip {{
      height: 5px;
      background: var(--accent);
    }}

    /* ══════════════════════════════════════════════════════════════
       BODY — two columns
    ══════════════════════════════════════════════════════════════ */
    .body {{
      display: flex;
      align-items: stretch;
    }}

    /* ── Left column (33%) ─────────────────────────────────────────── */
    .left-col {{
      width: 33%;
      flex-shrink: 0;
      background: var(--sidebarbg);
      padding: 18px 16px 24px 18px;
    }}

    /* ── Right column (67%) ────────────────────────────────────────── */
    .right-col {{
      flex: 1;
      padding: 18px 24px 24px 20px;
    }}

    /* ══════════════════════════════════════════════════════════════
       SECTION HEADINGS
    ══════════════════════════════════════════════════════════════ */

    .lsection {{
      margin-top: 18px;
      margin-bottom: 6px;
    }}

    .lsection:first-child {{ margin-top: 4px; }}

    .lsection-title {{
      font-size: 7.5pt;
      font-weight: 700;
      color: var(--accent);
      text-transform: uppercase;
      letter-spacing: 0.06em;
      display: block;
      margin-bottom: 3px;
    }}

    .lsection-rule {{
      height: 0.5px;
      background: var(--accentlight);
    }}

    .rsection {{
      display: flex;
      flex-direction: column;
      margin-top: 20px;
      margin-bottom: 8px;
    }}

    .rsection:first-child {{ margin-top: 4px; }}

    .rsection-head {{
      display: flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 3px;
    }}

    .rsection-bar {{
      width: 4px;
      height: 1.2em;
      background: var(--accent);
      flex-shrink: 0;
    }}

    .rsection-title {{
      font-size: 12pt;
      font-weight: 700;
      color: var(--dark);
    }}

    .rsection-rule {{
      height: 0.7px;
      background: var(--accentlight);
    }}

    /* ══════════════════════════════════════════════════════════════
       LEFT COLUMN CONTENT
    ══════════════════════════════════════════════════════════════ */
    .profile-text {{
      font-size: 8.5pt;
      color: var(--dark);
      margin-top: 5px;
    }}

    .contact-list {{
      list-style: none;
      margin-top: 5px;
    }}

    .contact-list li {{
      font-size: 8.5pt;
      color: var(--dark);
      display: flex;
      align-items: center;
      gap: 6px;
      margin-bottom: 4px;
    }}

    .contact-list a {{
      color: var(--dark);
      text-decoration: none;
    }}

    .contact-list a:hover {{ text-decoration: underline; }}

    .contact-icon {{
      color: var(--accent);
      font-size: 9pt;
      width: 14px;
      text-align: center;
      flex-shrink: 0;
    }}

    .lang-list {{
      list-style: none;
      margin-top: 5px;
    }}

    .lang-list li {{
      display: flex;
      justify-content: space-between;
      font-size: 8.5pt;
      margin-bottom: 3px;
    }}

    .lang-name {{ font-weight: 700; color: var(--dark); }}
    .lang-level {{ color: var(--muted); }}

    .cert-sidebar {{
      margin-top: 5px;
      font-size: 8.5pt;
    }}

    .cert-sidebar .cert-title {{
      font-weight: 700;
      color: var(--dark);
    }}

    .cert-sidebar .cert-sub {{
      color: var(--muted);
    }}

    .cert-sidebar .cert-date {{
      font-style: italic;
      color: var(--muted);
    }}

    .skill-list {{
      list-style: none;
      margin-top: 5px;
    }}

    .skill-list li {{
      font-size: 8.5pt;
      color: var(--dark);
      display: flex;
      align-items: baseline;
      gap: 6px;
      margin-bottom: 2px;
    }}

    .skill-bullet {{
      color: var(--accent);
      font-size: 7pt;
      flex-shrink: 0;
    }}

    /* ══════════════════════════════════════════════════════════════
       RIGHT COLUMN CONTENT
    ══════════════════════════════════════════════════════════════ */

    .exp-entry {{
      margin-bottom: 14px;
    }}

    .exp-header {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      flex-wrap: wrap;
      gap: 4px;
    }}

    .exp-title {{
      font-weight: 700;
      color: var(--accent);
      font-size: 10pt;
    }}

    .exp-dates {{
      font-size: 8.5pt;
      color: var(--muted);
      font-style: italic;
      white-space: nowrap;
    }}

    .exp-company {{
      font-size: 9pt;
      font-weight: 700;
      color: var(--dark);
      margin-bottom: 5px;
    }}

    .exp-desc {{
      list-style: disc;
      padding-left: 1.4em;
      margin-top: 4px;
    }}

    .exp-desc li {{
      font-size: 8.5pt;
      color: var(--dark);
      margin-bottom: 3px;
    }}

    .edu-entry {{
      margin-bottom: 14px;
    }}

    .edu-header {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      flex-wrap: wrap;
      gap: 4px;
    }}

    .edu-degree {{
      font-weight: 700;
      color: var(--dark);
      font-size: 10pt;
    }}

    .edu-year {{
      font-size: 8.5pt;
      color: var(--muted);
      font-style: italic;
      white-space: nowrap;
    }}

    .edu-institution {{
      font-size: 8.5pt;
      color: var(--muted);
      margin-bottom: 3px;
    }}

    .edu-desc {{
      font-size: 8.5pt;
      color: var(--dark);
    }}

    .cert-right-entry {{
      margin-bottom: 14px;
    }}

    .cert-right-header {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      flex-wrap: wrap;
      gap: 4px;
    }}

    .cert-right-title {{
      font-weight: 700;
      color: var(--accent);
      font-size: 10pt;
    }}

    .cert-right-date {{
      font-size: 8.5pt;
      color: var(--muted);
      font-style: italic;
      white-space: nowrap;
    }}

    .cert-right-sub {{
      font-size: 9pt;
      font-weight: 700;
      color: var(--dark);
      margin-bottom: 5px;
    }}

    .cert-right-desc {{
      list-style: disc;
      padding-left: 1.4em;
      margin-top: 4px;
    }}

    .cert-right-desc li {{
      font-size: 8.5pt;
      color: var(--dark);
      margin-bottom: 3px;
    }}

    .small-text {{
      font-size: 8.5pt;
      color: var(--dark);
    }}

    .small-text b {{ color: var(--dark); }}

    /* ── Language toggle ───────────────────────────────────────────── */
    .lang-toggle {{
      position: absolute;
      top: 14px;
      right: 20px;
      display: flex;
      gap: 8px;
    }}
    #lang-btn, #pdf-btn {{
      background: transparent;
      border: 1.5px solid var(--accentlight);
      color: var(--accentlight);
      padding: 4px 12px;
      border-radius: 4px;
      font-size: 8.5pt;
      font-weight: 700;
      cursor: pointer;
      letter-spacing: 0.08em;
      font-family: inherit;
    }}
    #lang-btn:hover, #pdf-btn:hover {{ background: rgba(125,200,194,0.18); }}
    .lang-fr {{ display: none; }}

    /* ── Company / school links ─────────────────────────────────────── */
    .exp-company a, .edu-institution a {{
      color: inherit;
      text-decoration: none;
      border-bottom: 1px dotted var(--muted);
    }}
    .exp-company a:hover, .edu-institution a:hover {{
      color: var(--accent);
      border-bottom-color: var(--accent);
    }}

    /* ── Print styles ───────────────────────────────────────────────── */
    @page {{ margin: 1.5cm 1.8cm 1.5cm 1.2cm; }}
    @media print {{
      body {{ background: #fff; print-color-adjust: exact; -webkit-print-color-adjust: exact; }}
      .page {{ box-shadow: none; max-width: 100%; }}
      .lang-toggle {{ display: none; }}
      a, a:visited {{
        color: inherit !important;
        text-decoration: none !important;
        border-bottom: none !important;
        pointer-events: none;
      }}
      a::after {{ content: none !important; }}
      .exp-entry, .edu-entry, .cert-right-entry, .cert-sidebar,
      .rsection, .lsection {{
        break-inside: avoid;
        page-break-inside: avoid;
      }}
      .rsection, .lsection {{
        break-after: avoid;
        page-break-after: avoid;
      }}
    }}
  </style>
</head>
<body>
<div class="page">

  <!-- ═══════════════════════ HEADER ════════════════════════════ -->
  <header class="header">
    <div class="lang-toggle">
      <button id="pdf-btn" onclick="downloadPDF()">
        <span class="lang-en">PDF</span><span class="lang-fr">PDF</span>
      </button>
      <button id="lang-btn" onclick="toggleLang()">FR</button>
    </div>
    <div class="header-inner">
      <img class="header-photo" src="resources/photo.jpg" alt="Marion Holvoet"
           onerror="this.style.display='none';this.nextElementSibling.style.display='block';" />
      <div class="header-photo-placeholder" style="display:none;"></div>
      <div class="header-text">
        <h1>{data["name"]}</h1>
        <div class="header-rule"></div>
        <span class="subtitle">
          <span class="lang-en">{subtitle_en}</span>
          <span class="lang-fr">{subtitle_fr}</span>
        </span>
      </div>
    </div>
  </header>
  <div class="header-accent-strip"></div>

  <!-- ═══════════════════════ BODY ══════════════════════════════ -->
  <div class="body">

    <!-- ─────────────────── LEFT COLUMN ─────────────────────── -->
    <aside class="left-col">

      <!-- Profile -->
      <div class="lsection">
        {_section_title_left("Profile")}
        <div class="lsection-rule"></div>
      </div>
      <p class="profile-text">
        <span class="lang-en">{safe(left["profile"])}</span>
        <span class="lang-fr">{FR["profile"]}</span>
      </p>

      <!-- Contact -->
      <div class="lsection">
        <span class="lsection-title">Contact</span>
        <div class="lsection-rule"></div>
      </div>
      <ul class="contact-list">
{contact_html}
      </ul>

      <!-- Languages -->
      <div class="lsection">
        {_section_title_left("Languages")}
        <div class="lsection-rule"></div>
      </div>
      <ul class="lang-list">
{lang_html}
      </ul>

      <!-- Certifications -->
      <div class="lsection">
        <span class="lsection-title">Certifications</span>
        <div class="lsection-rule"></div>
      </div>
{cert_sidebar_html}

      <!-- Key Skills -->
      <div class="lsection">
        {_section_title_left("Key Skills")}
        <div class="lsection-rule"></div>
      </div>
      <ul class="skill-list">
{skills_html}
      </ul>

      <!-- Personal Traits -->
      <div class="lsection">
        {_section_title_left("Personal Traits")}
        <div class="lsection-rule"></div>
      </div>
      <ul class="skill-list">
{traits_html}
      </ul>

    </aside>

    <!-- ─────────────────── RIGHT COLUMN ────────────────────── -->
    <main class="right-col">

      <!-- Professional Experience -->
      <div class="rsection">
        <div class="rsection-head">
          <span class="rsection-bar"></span>
          <span class="rsection-title">
            {_bi("Professional Experience", FR["Professional Experience"])}
          </span>
        </div>
        <div class="rsection-rule"></div>
      </div>

      {exp_html}

      <!-- Education -->
      <div class="rsection">
        <div class="rsection-head">
          <span class="rsection-bar"></span>
          <span class="rsection-title">
            {_bi("Education", FR["Education"])}
          </span>
        </div>
        <div class="rsection-rule"></div>
      </div>

      {edu_html}

      <!-- Certifications -->
      <div class="rsection">
        <div class="rsection-head">
          <span class="rsection-bar"></span>
          <span class="rsection-title">Certifications</span>
        </div>
        <div class="rsection-rule"></div>
      </div>

      {cert_right_html}

      <!-- Hobbies -->
      <div class="rsection">
        <div class="rsection-head">
          <span class="rsection-bar"></span>
          <span class="rsection-title">
            {_bi("Hobbies", FR["Hobbies"])}
          </span>
        </div>
        <div class="rsection-rule"></div>
      </div>
      <p class="small-text" style="margin-top:6px;">
        <span class="lang-en">{hobbies_en}</span>
        <span class="lang-fr">{hobbies_fr}</span>
      </p>

      <!-- Other -->
      <div class="rsection">
        <div class="rsection-head">
          <span class="rsection-bar"></span>
          <span class="rsection-title">
            {_bi("Other", FR["Other"])}
          </span>
        </div>
        <div class="rsection-rule"></div>
      </div>
      <p class="small-text" style="margin-top:6px;">
        <span class="lang-en">{other_en}</span>
        <span class="lang-fr">{other_fr}</span>
      </p>

    </main>
  </div><!-- .body -->

</div><!-- .page -->

  <div id="inapp-banner" style="display:none;position:fixed;bottom:0;left:0;right:0;background:#12343B;color:#fff;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;font-size:9pt;padding:12px 16px;z-index:9999;align-items:center;justify-content:space-between;gap:12px;">
    <span>To save as PDF, <a id="inapp-open-link" href="#" target="_blank" rel="noopener" style="color:var(--accentlight,#7DC8C2);text-decoration:underline;">open in browser &#x2197;</a></span>
    <button onclick="document.getElementById('inapp-banner').style.display='none'" style="background:transparent;border:1px solid rgba(255,255,255,0.5);color:#fff;padding:4px 10px;border-radius:4px;cursor:pointer;font-family:inherit;font-size:9pt;white-space:nowrap;">Got it</button>
  </div>

<script>
  let currentLang = 'en';
  function downloadPDF() {{
    const ua = navigator.userAgent || '';
    const inApp = /FBAN|FBAV|Instagram|LinkedInApp|Twitter|Snapchat|Line\/|MicroMessenger/.test(ua);
    if (inApp) {{
      const banner = document.getElementById('inapp-banner');
      document.getElementById('inapp-open-link').href = window.location.href;
      banner.style.display = 'flex';
    }} else {{
      window.print();
    }}
  }}
  function toggleLang() {{
    currentLang = currentLang === 'en' ? 'fr' : 'en';
    if (currentLang === 'fr') {{
      document.querySelectorAll('.lang-fr').forEach(el => {{ el.style.display = 'inline'; }});
      document.querySelectorAll('.lang-en').forEach(el => {{ el.style.display = 'none'; }});
    }} else {{
      document.querySelectorAll('.lang-en').forEach(el => {{ el.style.display = ''; }});
      document.querySelectorAll('.lang-fr').forEach(el => {{ el.style.display = ''; }});
    }}
    document.getElementById('lang-btn').textContent = currentLang === 'en' ? 'FR' : 'EN';
    document.documentElement.lang = currentLang;
  }}
</script>
</body>
</html>"""

# ─── Entry point ─────────────────────────────────────────────────────────────

def regenerate(translate: bool = False, force: bool = False):
    try:
        if translate:
            from scripts.auto_translate import run as translate_run
            updates = translate_run(force=force)
            # Update the in-memory FR dict so render_html uses fresh translations
            FR["skills_fr"]    = updates["skills_fr"]
            FR["traits_fr"]    = updates["traits_fr"]
            FR["exp_items_fr"] = updates["exp_items_fr"]
        data = parse_tex(TEX_FILE)
        html = render_html(data)
        HTML_FILE.write_text(html, encoding="utf-8")
        print(f"[OK] {HTML_FILE.name} regenerated.")
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback; traceback.print_exc()

if __name__ == "__main__":
    if "--translate" in sys.argv or "--translate-force" in sys.argv:
        force = "--translate-force" in sys.argv
        regenerate(translate=True, force=force)
        sys.exit(0)

    if "--once" in sys.argv:
        regenerate(translate=True)
        sys.exit(0)

    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
    except ImportError:
        print("watchdog not installed. Run:  pip install watchdog")
        sys.exit(1)

    class TexHandler(FileSystemEventHandler):
        def __init__(self):
            self._last = 0
        def on_modified(self, event):
            if Path(event.src_path).resolve() == TEX_FILE.resolve():
                now = time.time()
                if now - self._last > 1:   # debounce 1 s
                    self._last = now
                    regenerate(translate=True)

    print(f"Watching {TEX_FILE.name} — press Ctrl+C to stop.")
    regenerate(translate=True)   # run once on start

    observer = Observer()
    observer.schedule(TexHandler(), str(TEX_FILE.parent), recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
